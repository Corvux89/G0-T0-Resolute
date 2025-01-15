import json
import logging

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import BigInteger, Column, Integer, String, and_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import FromClause

from Resolute.compendium import Compendium
from Resolute.helpers.general_helpers import get_webhook
from Resolute.models import metadata
from Resolute.models.categories.categories import LevelTier
from Resolute.models.objects.adventures import Adventure, AdventureSchema, get_adventures_by_dm_query, get_character_adventures_query
from Resolute.models.objects.arenas import Arena, ArenaSchema, get_arena_by_host_query, get_character_arena_query
from Resolute.models.objects.characters import CharacterSchema, PlayerCharacter, PlayerCharacterClassSchema, RenownSchema, get_active_player_characters, get_all_player_characters, get_character_class, get_character_renown
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import get_log_count_by_player_and_activity
from Resolute.models.objects.ref_objects import NPC

log = logging.getLogger(__name__)

class Player(object):
    def __init__(self, id: int, guild_id: int, **kwargs):
        self._db: aiopg.sa.Engine

        self.id = id
        self.guild_id = guild_id
        self.handicap_amount: int = kwargs.get('handicap_amount', 0)
        self.cc: int = kwargs.get('cc', 0)
        self.div_cc: int = kwargs.get('div_cc', 0)
        self.points: int = kwargs.get('points', 0)
        self.activity_points: int = kwargs.get('activity_points', 0)
        self.activity_level: int = kwargs.get('activity_level', 0)
        self.statistics: str = kwargs.get('statistics', "{}")

        # Virtual Attributes
        self.characters: list[PlayerCharacter] = []
        self.member: discord.Member = kwargs.get('member', None)
        self.completed_rps: int = None
        self.completed_arenas: int = None
        self.needed_rps: int = None
        self.needed_arenas: int = None
        self.guild: PlayerGuild = kwargs.get('guild')
        self.arenas: list[Arena] = []
        self.adventures: list[Adventure] = []

    @property
    def highest_level_character(self) -> PlayerCharacter:
        if hasattr(self, "characters") and self.characters:
            return max(self.characters, key=lambda char: char.level)
        return None
    
    def has_character_in_tier(self, compendium: Compendium, tier: int) -> bool:
        if hasattr(self, "characters") and self.characters:
            for character in self.characters:
                level_tier: LevelTier = compendium.get_object(LevelTier, character.level)
                if level_tier.tier == tier:
                    return True
        return False
    
    def get_channel_character(self, channel: discord.TextChannel | discord.Thread | discord.ForumChannel) -> PlayerCharacter:
        for char in self.characters:
            if channel.id in char.channels:
                return char
            
    def get_primary_character(self) -> PlayerCharacter:
        for char in self.characters:
            if char.primary_character:
                return char
            
    async def get_webhook_character(self, channel: discord.TextChannel | discord.Thread | discord.ForumChannel) -> PlayerCharacter:
        if character := self.get_channel_character(channel):
            return character
        elif character := self.get_primary_character():
            character.channels.append(channel.id)
            await character.upsert()
            return character
        
        character = self.characters[0]
        character.primary_character = True
        character.channels.append(channel.id)
        await character.upsert()
        return character


    async def send_webhook_message(self, ctx: discord.ApplicationContext, character: PlayerCharacter, content: str):
        webhook = await get_webhook(ctx.channel)
        
        if isinstance(ctx.channel, discord.Thread):
            await webhook.send(username=f"[{character.level}] {character.name} // {self.member.display_name}",
                            avatar_url=self.member.display_avatar.url if not character.avatar_url else character.avatar_url,
                            content=content,
                            thread=ctx.channel)
        else:
            await webhook.send(username=f"[{character.level}] {character.name} // {self.member.display_name}",
                            avatar_url=self.member.display_avatar.url if not character.avatar_url else character.avatar_url,
                            content=content)

    
    async def update_command_count(self, command: str):
        stats = json.loads(self.statistics if self.statistics else "{}")
        if "commands" not in stats:
            stats["commands"] = {}

        if command not in stats["commands"]:
            stats["commands"][command] = 0

        stats["commands"][command] += 1

        self.statistics = json.dumps(stats)

        async with self._db.acquire() as conn:
            await conn.execute(upsert_player_query(self))
    
    async def update_post_stats(self, character: PlayerCharacter | NPC, post: discord.Message, **kwargs):
        content = kwargs.get('content', post.content)
        retract = kwargs.get('retract', False)

        stats = json.loads(self.statistics)

        current_date = post.created_at.strftime('%Y-%m-%d')

        if isinstance(character, PlayerCharacter):
            key="say"
            id=character.id   
        else:
            key="npc"
            id=character.key

        if key not in stats:
            stats[key] = {}

        if str(id) not in stats[key]:
            stats[key][str(id)] = {}

        if current_date not in stats[key][str(id)]:
            stats[key][str(id)][current_date] = {
                "num_lines": 0,
                "num_words": 0,
                "num_characters": 0,
                "count": 0
            }

        daily_stats = stats[key][str(id)][current_date]

        lines = content.splitlines()
        words = content.split()
        characters = len(content)

        if retract:
            daily_stats["num_lines"] -= len(lines)
            daily_stats["num_words"] -= len(words)
            daily_stats["num_characters"] -= characters
            daily_stats["count"] -= 1
        else:
            daily_stats["num_lines"] += len(lines)
            daily_stats["num_words"] += len(words)
            daily_stats["num_characters"] += characters
            daily_stats["count"] += 1

        self.statistics = json.dumps(stats)

        async with self._db.acquire() as conn:
            await conn.execute(upsert_player_query(self))

    async def remove_arena_board_post(self, ctx: discord.ApplicationContext | discord.Interaction):
        def predicate(message: discord.Message):
            if message.author.bot:
                return message.embeds[0].footer.text == f"{self.id}"
            
            return message.author == self.member

        if self.guild.arena_board_channel:
            if not self.guild.arena_board_channel.permissions_for(ctx.guild.me).manage_messages:
                return log.warning(f"Bot does not have permission to manage arena board messages in {self.guild.guild.name} [{self.guild.guild.id}]")
            
            try:
                deleted_message = await self.guild.arena_board_channel.purge(check=predicate)
                log.info(f"{len(deleted_message)} message{'s' if len(deleted_message)>1 else ''} by {self.member.name} deleted from #{self.guild.arena_board_channel.name}")
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    await ctx.send(f'Warning: deleting users\'s post(s) from {self.guild.arena_board_channel.mention} failed')
                else:
                    log.error(error)
    
player_table = sa.Table(
    "players",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("guild_id", BigInteger, primary_key=True),
    Column("handicap_amount", Integer),
    Column("cc", Integer),
    Column("div_cc", Integer),
    Column("points", Integer),
    Column("activity_points", Integer),
    Column("activity_level", Integer),
    Column("statistics", String)
)

class PlayerSchema(Schema):
    bot = None
    inactive: bool
    id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    handicap_amount = fields.Integer()
    cc = fields.Integer()
    div_cc = fields.Integer()
    points = fields.Integer()
    activity_points = fields.Integer()
    activity_level = fields.Integer()
    statistics = fields.String(default="{}")

    def __init__(self, bot, inactive: bool, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.inactive = inactive

    @post_load
    async def make_discord_player(self, data, **kwargs):
        player = Player(**data)
        await self.get_characters(player)
        await self.get_player_quests(player)
        await self.get_adventures(player)
        player.member = self.bot.get_guild(player.guild_id).get_member(player.id)
        player.guild = await self.bot.get_player_guild(player.guild_id)
        player._db = self.bot.db
        return player
    
    async def get_characters(self, player: Player):
        async with self.bot.db.acquire() as conn:
            if self.inactive:
                results = await conn.execute(get_all_player_characters(player.id, player.guild_id))
            else:
                results = await conn.execute(get_active_player_characters(player.id, player.guild_id))
            rows = await results.fetchall()

        character_list: list[PlayerCharacter] = [await CharacterSchema(self.bot.db, self.bot.compendium).load(row) for row in rows]

        for character in character_list:
            async with self.bot.db.acquire() as conn:
                class_results = await conn.execute(get_character_class(character.id))
                class_rows = await class_results.fetchall()

                renown_results = await conn.execute(get_character_renown(character.id))
                renown_rows = await renown_results.fetchall()

            character.classes = [PlayerCharacterClassSchema(self.bot.db, self.bot.compendium).load(row) for row in class_rows]
            character.renown = [RenownSchema(self.bot.db, self.bot.compendium).load(row) for row in renown_rows]
        
        player.characters = character_list

    async def get_player_quests(self, player: Player):
        if len(player.characters) == 0 or (player.highest_level_character and player.highest_level_character.level >= 3):
            return
        
        rp_activity = self.bot.compendium.get_activity("RP")
        arena_activity = self.bot.compendium.get_activity("ARENA")
        arena_host_activity = self.bot.compendium.get_activity("ARENA_HOST")

        async with self.bot.db.acquire() as conn:
            rp_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, rp_activity.id))
            areana_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, arena_activity.id))
            arena_host_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, arena_host_activity.id))
            player.completed_rps = await rp_result.scalar()
            player.completed_arenas = await areana_result.scalar() + await arena_host_result.scalar()

        player.needed_rps = 1 if player.highest_level_character.level == 1 else 2
        player.needed_arenas = 1 if player.highest_level_character.level == 1 else 2

    async def get_adventures(self, player: Player):
        rows = []

        async with self.bot.db.acquire() as conn:
            dm_adventures = await conn.execute(get_adventures_by_dm_query(player.id))
            rows = await dm_adventures.fetchall()

        for character in player.characters:
            async with self.bot.db.acquire() as conn:
                player_adventures = await conn.execute(get_character_adventures_query(character.id))
                rows.extend(await player_adventures.fetchall())

        player.adventures.extend([await AdventureSchema(self.bot.db, self.bot.compendium).load(row) for row in rows])

    async def get_arenas(self, player: Player):
        rows =[]

        async with self.bot.db.acquire() as conn:
            host_arenas = await conn.execute(get_arena_by_host_query(player.id))
            rows = await host_arenas.fetchall()

        for character in player.characters:
            async with self.bot.db.acquire() as conn:
                player_arenas = await conn.execute(get_character_arena_query(character.id))
                rows.extend(await player_arenas.fetchall())

        player.arenas.extend(ArenaSchema(self.bot.db, self.bot.compendium).load(row) for row in rows)
        
    

def get_player_query(player_id: int, guild_id: int = None) -> FromClause:

    if guild_id:
        return player_table.select().where(
            and_(player_table.c.id == player_id, player_table.c.guild_id == guild_id)
        )
    
    return player_table.select().where(
        and_(player_table.c.id == player_id)
    )

def reset_div_cc(guild_id: int):
    return update(player_table).where(player_table.c.guild_id == guild_id).values(div_cc=0, activity_points=0, activity_level=0)

def upsert_player_query(player: Player):
    insert_statement = insert(player_table).values(
        id=player.id,
        guild_id=player.guild_id,
        handicap_amount=player.handicap_amount,
        cc=player.cc,
        div_cc=player.div_cc,
        points=player.points,
        activity_points=player.activity_points,
        activity_level=player.activity_level,
        statistics=player.statistics
    ).returning(player_table)

    update_dict = {
        'id': player.id,
        'guild_id': player.guild_id,
        'handicap_amount': player.handicap_amount,
        'cc': player.cc,
        'div_cc': player.div_cc,
        'points': player.points,
        'activity_points': player.activity_points,
        'activity_level': player.activity_level,
        'statistics': player.statistics
    }

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['id', 'guild_id'],
        set_=update_dict
    )

    return upsert_statement


class RPPost(object):
    def __init__(self, character: PlayerCharacter, *args, **kwargs):
        self.character = character
        self.note = kwargs.get('note')