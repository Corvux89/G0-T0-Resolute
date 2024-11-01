import discord
import sqlalchemy as sa
import json

from marshmallow import Schema, fields, post_load
from sqlalchemy import Column, Integer, BigInteger, and_, update, String
from sqlalchemy.sql import FromClause
from sqlalchemy.dialects.postgresql import insert

from Resolute.bot import G0T0Bot
from Resolute.models import metadata
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.npc import NPC

class Player(object):
    characters: list[PlayerCharacter]

    def __init__(self, id: int, guild_id: int, **kwargs):
        self.id = id
        self.guild_id = guild_id
        self.handicap_amount: int = kwargs.get('handicap_amount', 0)
        self.cc: int = kwargs.get('cc', 0)
        self.div_cc: int = kwargs.get('div_cc', 0)
        self.points: int = kwargs.get('points', 0)
        self.activity_points: int = kwargs.get('activity_points', 0)
        self.activity_level: int = kwargs.get('activity_level', 0)
        self.statistics: str = kwargs.get('statistics', "")

        # Virtual Attributes
        self.characters: list[PlayerCharacter] = []
        self.member: discord.Member = None
        self.completed_rps: int = None
        self.completed_arenas: int = None
        self.needed_rps: int = None
        self.needed_arenas: int = None

    @property
    def highest_level_character(self) -> PlayerCharacter:
        if hasattr(self, "characters") and self.characters:
            return max(self.characters, key=lambda char: char.level)
        return None
    
    def get_channel_character(self, channel: discord.TextChannel) -> PlayerCharacter:
        for char in self.characters:
            if channel.id in char.channels:
                return char
            
    def get_primary_character(self) -> PlayerCharacter:
        for char in self.characters:
            if char.primary_character:
                return char       
    
    async def update_command_count(self, bot: G0T0Bot, command: str):
        stats = json.loads(self.statistics)
        if "commands" not in stats:
            stats["commands"] = {}

        if command not in stats["commands"]:
            stats["commands"][command] = 0

        stats["commands"][command] += 1

        self.statistics = json.dumps(stats)

        async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(self))

    async def update_post_stats(self, bot: G0T0Bot, character: PlayerCharacter | NPC, post: str, retract: bool = False):
        stats = json.loads(self.statistics)

        if isinstance(character, PlayerCharacter):
            key="say"   
        else:
            key="npc"

        if key not in stats:
            stats[key] = {}

        if f"{character.id}" not in stats[key]:
            stats[key][f"{character.id}"] = {}


        if "num_lines" not in stats[key][f"{character.id}"]:
            stats[key][f"{character.id}"]["num_lines"] = 0

        if "num_words" not in stats[key][f"{character.id}"]:
            stats[key][f"{character.id}"]["num_words"] = 0

        if "num_characters" not in stats[key][f"{character.id}"]:
            stats[key][f"{character.id}"]["num_characters"] = 0

        if "count" not in stats[key][f"{character.id}"]:
            stats[key][f"{character.id}"]["count"] = 0

        lines = post.splitlines()
        words = post.split()
        characters = len(post)

        if retract:
            stats[key][f"{character.id}"]["num_lines"] -= len(lines)
            stats[key][f"{character.id}"]["num_words"] -= len(words)
            stats[key][f"{character.id}"]["num_characters"] -= characters
            stats[key][f"{character.id}"]["count"] -= 1
        else:
            stats[key][f"{character.id}"]["num_lines"] += len(lines)
            stats[key][f"{character.id}"]["num_words"] += len(words)
            stats[key][f"{character.id}"]["num_characters"] += characters
            stats[key][f"{character.id}"]["count"] += 1

        self.statistics = json.dumps(stats)

        async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(self))

        

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
    id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    handicap_amount = fields.Integer()
    cc = fields.Integer()
    div_cc = fields.Integer()
    points = fields.Integer()
    activity_points = fields.Integer()
    activity_level = fields.Integer()
    statistics = fields.String()

    @post_load
    def make_discord_player(self, data, **kwargs):
        return Player(**data)
    

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