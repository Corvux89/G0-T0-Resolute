from __future__ import annotations
import operator
from typing import TYPE_CHECKING

import json
import logging
from timeit import default_timer as timer

import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import insert

from Resolute.helpers.general_helpers import get_selection
from Resolute.models.embeds.logs import LogEmbed
from Resolute.compendium import Compendium
from Resolute.helpers import get_webhook
from Resolute.models import metadata
from Resolute.models.categories.categories import (
    Activity,
    ActivityPoints,
    ArenaType,
    LevelTier,
)
from Resolute.models.embeds.arenas import ArenaStatusEmbed
from Resolute.models.objects.enum import ApplicationType, ArenaPostType, QueryResultType
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.arenas import Arena

from Resolute.models.objects.characters import (
    PlayerCharacter,
    PlayerCharacterClass,
    CharacterRenown,
)
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot
    from .npc import NonPlayableCharacter

log = logging.getLogger(__name__)


class Player(object):
    """
    Represents a player in the game.
    Attributes:
        id (int): The player's ID.
        guild_id (int): The ID of the guild the player belongs to.
        handicap_amount (int): The player's handicap amount. Defaults to 0.
        cc (int): The player's CC. Defaults to 0.
        div_cc (int): The player's division CC. Defaults to 0.
        points (int): The player's points. Defaults to 0.
        activity_points (int): The player's activity points. Defaults to 0.
        activity_level (int): The player's activity level. Defaults to 0.
        statistics (str): The player's statistics in JSON format. Defaults to "{}".
        characters (list[PlayerCharacter]): The player's characters.
        member (Member): The player's member object.
        completed_rps (int): The number of completed RPs by the player.
        completed_arenas (int): The number of completed arenas by the player.
        needed_rps (int): The number of RPs needed by the player.
        needed_arenas (int): The number of arenas needed by the player.
        guild (PlayerGuild): The player's guild object.
        arenas (list[Arena]): The player's arenas.
        adventures (list[Adventure]): The player's adventures.
    Methods:
        highest_level_character: Returns the player's highest level character.
        has_character_in_tier(compendium, tier): Checks if the player has a character in the specified tier.
        get_channel_character(channel): Returns the player's character associated with the specified channel.
        get_primary_character: Returns the player's primary character.
        get_webhook_character(channel): Returns the player's character associated with the specified channel or the primary character.
        send_webhook_message(ctx, character, content): Sends a webhook message as the specified character.
        update_command_count(command): Updates the player's command count statistics.
        update_post_stats(character, post, **kwargs): Updates the player's post statistics.
        remove_arena_board_post(ctx): Removes the player's arena board post.
        add_to_arena(interaction, character, arena): Adds the player's character to the specified arena.
        can_join_arena(arena_type, character): Checks if the player can join the specified arena.
        create_character(type, new_character, new_class, **kwargs): Creates a new character for the player.
    """

    player_table = sa.Table(
        "players",
        metadata,
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("guild_id", sa.BigInteger, primary_key=True),
        sa.Column("handicap_amount", sa.Integer),
        sa.Column("cc", sa.Integer),
        sa.Column("div_cc", sa.Integer),
        sa.Column("points", sa.Integer),
        sa.Column("activity_points", sa.Integer),
        sa.Column("activity_level", sa.Integer),
        sa.Column("statistics", sa.String),
    )

    class PlayerSchema(Schema):
        bot: G0T0Bot = None
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

        def __init__(self, bot: G0T0Bot, inactive: bool, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot
            self.inactive = inactive

        @post_load
        async def make_discord_player(self, data, **kwargs):
            player = Player(self.bot, **data)
            await self.get_characters(player)
            await self.get_player_quests(player)
            await self.get_adventures(player)
            await self.get_arenas(player)
            player.member = self.bot.get_guild(player.guild_id).get_member(player.id)
            player.guild = await PlayerGuild.get_player_guild(self.bot, player.guild_id)
            return player

        async def get_characters(self, player: "Player") -> None:
            if self.inactive:
                query = PlayerCharacter.characters_table.select().where(
                    sa.and_(
                        PlayerCharacter.characters_table.c.player_id == player.id,
                        PlayerCharacter.characters_table.c.guild_id == player.guild_id,
                    )
                )
            else:
                query = PlayerCharacter.characters_table.select().where(
                    sa.and_(
                        PlayerCharacter.characters_table.c.player_id == player.id,
                        PlayerCharacter.characters_table.c.guild_id == player.guild_id,
                        PlayerCharacter.characters_table.c.active == True,
                    )
                )

            rows = await self.bot.query(query, QueryResultType.multiple)

            character_list: list[PlayerCharacter] = [
                await PlayerCharacter.CharacterSchema(
                    self.bot.db, self.bot.compendium
                ).load(row)
                for row in rows
            ]

            for character in character_list:
                renown_query = (
                    CharacterRenown.renown_table.select()
                    .where(CharacterRenown.renown_table.c.character_id == character.id)
                    .order_by(CharacterRenown.renown_table.c.id.asc())
                )

                class_query = (
                    PlayerCharacterClass.character_class_table.select()
                    .where(
                        sa.and_(
                            PlayerCharacterClass.character_class_table.c.character_id
                            == character.id,
                            PlayerCharacterClass.character_class_table.c.active == True,
                        )
                    )
                    .order_by(PlayerCharacterClass.character_class_table.c.id.asc())
                )

                character.classes = [
                    PlayerCharacterClass.PlayerCharacterClassSchema(
                        self.bot.db, self.bot.compendium
                    ).load(row)
                    for row in await self.bot.query(
                        class_query, QueryResultType.multiple
                    )
                ]
                character.renown = [
                    CharacterRenown.RenownSchema(self.bot.db, self.bot.compendium).load(
                        row
                    )
                    for row in await self.bot.query(
                        renown_query, QueryResultType.multiple
                    )
                ]

            player.characters = character_list

        async def get_player_quests(self, player: "Player") -> None:
            from .logs import DBLog

            if len(player.characters) == 0 or (
                player.highest_level_character
                and player.highest_level_character.level >= 3
            ):
                return

            def build_query(activity: Activity):
                query = (
                    sa.select([sa.func.count()])
                    .select_from(DBLog.log_table)
                    .where(
                        sa.and_(
                            DBLog.log_table.c.player_id == player.id,
                            DBLog.log_table.c.guild_id == player.guild_id,
                            DBLog.log_table.c.invalid == False,
                            DBLog.log_table.c.activity == activity.id,
                        )
                    )
                )
                return query

            rp_activity = self.bot.compendium.get_activity("RP")
            arena_activity = self.bot.compendium.get_activity("ARENA")
            arena_host_activity = self.bot.compendium.get_activity("ARENA_HOST")

            player.completed_rps = await self.bot.query(
                build_query(rp_activity), QueryResultType.scalar
            )
            player.completed_arenas = await self.bot.query(
                build_query(arena_activity), QueryResultType.scalar
            ) + await self.bot.query(
                build_query(arena_host_activity), QueryResultType.scalar
            )

            player.needed_rps = 1 if player.highest_level_character.level == 1 else 2
            player.needed_arenas = 1 if player.highest_level_character.level == 1 else 2

        async def get_adventures(self, player: "Player") -> None:
            dm_query = (
                Adventure.adventures_table.select()
                .where(
                    sa.and_(
                        Adventure.adventures_table.c.dms.contains([player.id]),
                        Adventure.adventures_table.c.end_ts == sa.null(),
                    )
                )
                .order_by(Adventure.adventures_table.c.id.asc())
            )

            rows = await self.bot.query(dm_query, QueryResultType.multiple)

            for character in player.characters:
                char_query = (
                    Adventure.adventures_table.select()
                    .where(
                        sa.and_(
                            Adventure.adventures_table.c.characters.contains(
                                [character.id]
                            ),
                            Adventure.adventures_table.c.end_ts == sa.null(),
                        )
                    )
                    .order_by(Adventure.adventures_table.c.id.asc())
                )

                rows.extend(await self.bot.query(char_query, QueryResultType.multiple))

            player.adventures.extend(
                [await Adventure.AdventureSchema(self.bot).load(row) for row in rows]
            )

        async def get_arenas(self, player: "Player") -> None:
            rows = []

            host_arena_query = Arena.arenas_table.select().where(
                sa.and_(
                    Arena.arenas_table.c.host_id == player.id,
                    Arena.arenas_table.c.end_ts == sa.null(),
                )
            )

            rows = await self.bot.query(host_arena_query, QueryResultType.multiple)

            for character in player.characters:
                char_query = Arena.arenas_table.select().where(
                    sa.and_(
                        Arena.arenas_table.c.characters.contains([character.id]),
                        Arena.arenas_table.c.end_ts == sa.null(),
                    )
                )

                rows.extend(await self.bot.query(char_query, QueryResultType.multiple))

            arenas = [await Arena.ArenaSchema(self.bot).load(row) for row in rows]

            player.arenas.extend(arenas)

    def __init__(self, bot: G0T0Bot, id: int, guild_id: int, **kwargs):
        self._bot = bot

        self.id = id
        self.guild_id = guild_id
        self.handicap_amount: int = kwargs.get("handicap_amount", 0)
        self.cc: int = kwargs.get("cc", 0)
        self.div_cc: int = kwargs.get("div_cc", 0)
        self.points: int = kwargs.get("points", 0)
        self.activity_points: int = kwargs.get("activity_points", 0)
        self.activity_level: int = kwargs.get("activity_level", 0)
        self.statistics: str = kwargs.get("statistics", "{}")

        # Virtual Attributes
        self.characters: list[PlayerCharacter] = []
        self.member: discord.Member = kwargs.get("member", None)
        self.completed_rps: int = None
        self.completed_arenas: int = None
        self.needed_rps: int = None
        self.needed_arenas: int = None
        self.guild: PlayerGuild = kwargs.get("guild")
        self.arenas: list[Arena] = []
        self.adventures: list[Adventure] = []

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} guild={self.guild_id!r} name={self.member.display_name if self.member else ''!r}>"

    @property
    def highest_level_character(self) -> PlayerCharacter:
        if hasattr(self, "characters") and self.characters:
            return max(self.characters, key=lambda char: char.level)
        return None

    @property
    def discord_url(self) -> str:
        return f"https://discordapp.com/users/{self.id}"

    def has_character_in_tier(self, compendium: Compendium, tier: int) -> bool:
        if hasattr(self, "characters") and self.characters:
            for character in self.characters:
                level_tier: LevelTier = compendium.get_object(
                    LevelTier, character.level
                )
                if level_tier.tier == tier:
                    return True
        return False

    def get_channel_character(
        self, channel: discord.TextChannel | discord.Thread | discord.ForumChannel
    ) -> PlayerCharacter:
        for char in self.characters:
            if channel.id in char.channels:
                return char

    def get_primary_character(self) -> PlayerCharacter:
        for char in self.characters:
            if char.primary_character:
                return char

    async def get_webhook_character(
        self, channel: discord.TextChannel | discord.Thread | discord.ForumChannel
    ) -> PlayerCharacter:
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

    async def send_webhook_message(
        self, ctx: discord.ApplicationContext, character: PlayerCharacter, content: str
    ) -> None:
        webhook = await get_webhook(ctx.channel)

        if isinstance(ctx.channel, discord.Thread):
            await webhook.send(
                username=f"[{character.level}] {character.name} // {self.member.display_name}",
                avatar_url=(
                    self.member.display_avatar.url
                    if not character.avatar_url
                    else character.avatar_url
                ),
                content=content,
                thread=ctx.channel,
            )
        else:
            await webhook.send(
                username=f"[{character.level}] {character.name} // {self.member.display_name}",
                avatar_url=(
                    self.member.display_avatar.url
                    if not character.avatar_url
                    else character.avatar_url
                ),
                content=content,
            )

    async def edit_webhook_message(
        self, ctx: discord.ApplicationContext, message_id: int, content: str
    ) -> None:
        webhook = await get_webhook(ctx.channel)

        if isinstance(ctx.channel, (discord.Thread, discord.ForumChannel)):
            await webhook.edit_message(message_id, content=content, thread=ctx.channel)
        else:
            await webhook.edit_message(message_id, content=content)

    async def update_command_count(self, command: str) -> None:
        stats = json.loads(self.statistics if self.statistics else "{}")
        if "commands" not in stats:
            stats["commands"] = {}

        if command not in stats["commands"]:
            stats["commands"][command] = 0

        stats["commands"][command] += 1

        self.statistics = json.dumps(stats)

        await self.upsert()

    async def update_post_stats(
        self,
        character: PlayerCharacter | NonPlayableCharacter,
        post: discord.Message,
        **kwargs,
    ) -> None:
        content = kwargs.get("content", post.content)
        retract = kwargs.get("retract", False)

        stats = json.loads(self.statistics)

        current_date = post.created_at.strftime("%Y-%m-%d")

        if isinstance(character, PlayerCharacter):
            key = "say"
            id = character.id
        else:
            key = "npc"
            id = character.key

        if key not in stats:
            stats[key] = {}

        if str(id) not in stats[key]:
            stats[key][str(id)] = {}

        if current_date not in stats[key][str(id)]:
            stats[key][str(id)][current_date] = {
                "num_lines": 0,
                "num_words": 0,
                "num_characters": 0,
                "count": 0,
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

        await self.upsert()

    async def remove_arena_board_post(
        self, ctx: discord.ApplicationContext | discord.Interaction
    ) -> None:
        def predicate(message: discord.Message):
            if message.author.bot:
                return message.embeds[0].footer.text == f"{self.id}"

            return message.author == self.member

        if self.guild.arena_board_channel:
            if not self.guild.arena_board_channel.permissions_for(
                ctx.guild.me
            ).manage_messages:
                return log.warning(
                    f"Bot does not have permission to manage arena board messages in {self.guild.guild.name} [{self.guild.guild.id}]"
                )

            try:
                deleted_message = await self.guild.arena_board_channel.purge(
                    check=predicate
                )
                log.info(
                    f"{len(deleted_message)} message{'s' if len(deleted_message)>1 else ''} by {self.member.name} deleted from #{self.guild.arena_board_channel.name}"
                )
            except Exception as error:
                if isinstance(error, discord.HTTPException):
                    await ctx.send(
                        f"Warning: deleting users's post(s) from {self.guild.arena_board_channel.mention} failed"
                    )
                else:
                    log.error(error)

    async def add_to_arena(
        self,
        interaction: discord.Interaction | discord.ApplicationContext,
        character: PlayerCharacter,
        arena: Arena,
    ) -> None:
        if character.id in arena.characters:
            raise G0T0Error("character already in the arena")
        elif not self.can_join_arena(arena.type, character):
            raise G0T0Error(
                f"Character is already in an {arena.type.value.lower()} arena"
            )

        if self.id in {c.player_id for c in arena.player_characters}:
            remove_char = next(
                (c for c in arena.player_characters if c.player_id == self.id), None
            )
            arena.player_characters.remove(remove_char)

        await self.remove_arena_board_post(interaction)
        await interaction.channel.send(
            f"{self.member.mention} has joined the arena with {character.name}"
        )

        arena.player_characters.append(character)

        arena.update_tier()

        await arena.upsert()
        await ArenaStatusEmbed(interaction, arena).update()

    def can_join_arena(
        self, arena_type: ArenaType = None, character: PlayerCharacter = None
    ) -> bool:
        participating_arenas = [
            a
            for a in self.arenas
            if any([c.id in a.characters for c in self.characters])
        ]
        filtered_arenas = []

        if len(participating_arenas) >= 2:
            return False
        elif (
            arena_type
            and arena_type.value == "NARRATIVE"
            and self.guild.member_role
            and self.guild.member_role not in self.member.roles
        ):
            return False

        if arena_type:
            filtered_arenas = [
                a for a in participating_arenas if a.type.id == arena_type.id
            ]

        if character and (
            arena := next(
                (a for a in filtered_arenas if character.id in a.characters), None
            )
        ):
            return False

        return True

    async def create_character(
        self,
        type: ApplicationType,
        new_character: PlayerCharacter,
        new_class: PlayerCharacterClass,
        **kwargs,
    ) -> PlayerCharacter:
        start = timer()

        old_character: PlayerCharacter = kwargs.get("old_character")

        # Character Setup
        new_character.player_id = self.id
        new_character.guild_id = self.guild_id

        if type in [ApplicationType.freeroll, ApplicationType.death]:
            if not old_character:
                raise G0T0Error("Missing required information to process this request")

            new_character.reroll = True
            old_character.active = False

            if type == ApplicationType.freeroll:
                new_character.freeroll_from = old_character.id
            else:
                self.handicap_amount = 0

            await old_character.upsert()

        new_character = await new_character.upsert()

        # Class setup
        new_class.character_id = new_character.id
        new_class = await new_class.upsert()

        new_character.classes.append(new_class)

        end = timer()

        log.info(f"Time to create character {new_character.id}: [ {end-start:.2f} ]s")

        return new_character

    async def upsert(self, **kwargs) -> "Player":
        inactive = kwargs.get("inactive", False)

        update_dict = {
            "handicap_amount": self.handicap_amount,
            "cc": self.cc,
            "div_cc": self.div_cc,
            "points": self.points,
            "activity_points": self.activity_points,
            "activity_level": self.activity_level,
            "statistics": self.statistics,
        }

        insert_dict = {
            **update_dict,
            "id": self.id,
            "guild_id": self.guild_id,
        }

        query = (
            insert(Player.player_table)
            .values(**insert_dict)
            .returning(Player.player_table)
        )

        query = query.on_conflict_do_update(
            index_elements=["id", "guild_id"], set_=update_dict
        )

        row = await self._bot.query(query)

        player = await Player.PlayerSchema(self._bot, inactive).load(row)

        return player

    async def fetch(self, **kwargs):
        inactive = kwargs.get("inactive", False)

        query = Player.player_table.select().where(
            sa.and_(
                Player.player_table.c.id == self.id,
                Player.player_table.c.guild_id == self.guild_id,
            )
        )

        row = await self._bot.query(query)

        if row is None:
            return None

        player = await Player.PlayerSchema(self._bot, inactive).load(row)

        return player

    async def get_stats(self, bot: G0T0Bot) -> dict:
        from .logs import DBLog

        new_character_activity = bot.compendium.get_activity("NEW_CHARACTER")
        activities = [
            x
            for x in bot.compendium.activity[0].values()
            if x.value in ["RP", "ARENA", "ARENA_HOST", "GLOBAL", "SNAPSHOT"]
        ]
        columns = [
            sa.func.sum(
                sa.case([(DBLog.log_table.c.activity == act.id, 1)], else_=0)
            ).label(f"Activity {act.value}")
            for act in activities
        ]

        query = (
            sa.select(
                DBLog.log_table.c.player_id,
                sa.func.count(DBLog.log_table.c.id).label("#"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("debt"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc < 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("credit"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    == new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("starting"),
                *columns,
            )
            .group_by(DBLog.log_table.c.player_id)
            .where(
                sa.and_(
                    DBLog.log_table.c.player_id == self.id,
                    DBLog.log_table.c.guild_id == self.guild_id,
                    DBLog.log_table.c.invalid == False,
                )
            )
        )

        row = await bot.query(query)

        return dict(row)

    @staticmethod
    async def get_player(
        bot: G0T0Bot, player_id: int, guild_id: int = None, **kwargs
    ) -> "Player":
        inactive = kwargs.get("inactive", False)
        lookup_only = kwargs.get("lookup_only", False)
        ctx = kwargs.get("ctx")

        player = None

        if guild_id:
            query = Player.player_table.select().where(
                sa.and_(
                    Player.player_table.c.id == player_id,
                    Player.player_table.c.guild_id == guild_id,
                )
            )
        else:
            query = Player.player_table.select().where(
                Player.player_table.c.id == player_id
            )

        rows = await bot.query(query, QueryResultType.multiple)

        # Not found
        if not rows:
            if lookup_only:
                return None
            elif guild_id:
                # Single guild -> Create new player
                player = await Player(bot, player_id, guild_id).upsert(
                    inactive=inactive
                )
            else:
                if ctx:
                    # Check for guilds the player is in
                    guilds = [g for g in bot.guilds if g.get_member(player_id)]

                    # One guild in common
                    if len(guilds) == 1:
                        player = await Player(bot, player_id, guilds[0].id).upsert(
                            inactive=inactive
                        )
                        return player

                    # Multiple guilds in common
                    elif len(guilds) > 1:

                        try:
                            await ctx.defer()
                        except:
                            pass

                        guild = await get_selection(
                            ctx,
                            guilds,
                            True,
                            True,
                            None,
                            False,
                            "Which guild is this command for?\n",
                        )

                        if guild:
                            player = await Player(bot, player_id, guild.id).upsert(
                                inactive=inactive
                            )
                        else:
                            raise G0T0Error("No guild selected/found.")
                    else:
                        raise G0T0Error("Unable to find player")
                else:
                    raise G0T0Error("Unable to find guild")

        # Player(s) found in db
        else:
            # One match found
            if len(rows) == 1:
                player = await Player.PlayerSchema(bot, inactive).load(rows[0])

            # Multiple matches
            else:
                if ctx:
                    guilds = [g for g in bot.guilds if g.get_member(player_id)]

                    if len(guilds) == 1:
                        row = filter(
                            lambda p: p["guild_id"] == str(guilds[0].id), guilds
                        )
                        player = await Player.PlayerSchema(bot, inactive).load(row)
                        # player = await Player.get_player(bot, player_id, guilds[0].id, **kwargs)

                    else:
                        choices = [g.name for g in guilds]
                        try:
                            await ctx.defer()
                        except:
                            pass
                        choice = await get_selection(
                            ctx,
                            choices,
                            True,
                            True,
                            None,
                            False,
                            "Which guild is this command for?\n",
                        )

                        if choice and (
                            guild := next((g for g in guilds if g.name == choice), None)
                        ):
                            player = await Player.get_player(
                                bot, player_id, guild.id, **kwargs
                            )
                        else:
                            raise G0T0Error("Unable to find player")
                else:
                    raise G0T0Error("Unable to find player")
        return player

    async def update_activity_points(
        self, bot: G0T0Bot, increment: bool = True
    ) -> None:
        if increment:
            self.activity_points += 1
        else:
            self.activity_points = max(self.activity_points - 1, 0)

        points = sorted(
            bot.compendium.activity_points[0].values(), key=operator.attrgetter("id")
        )
        activity_point: ActivityPoints = None

        for point in points:
            point: ActivityPoints
            if self.activity_points >= point.points:
                activity_point = point
            elif self.activity_points < point.points:
                break

        if (activity_point and self.activity_level != activity_point.id) or (
            increment == False and not activity_point
        ):
            from .logs import DBLog

            revert = (
                True
                if not activity_point
                or (activity_point and self.activity_level > activity_point.id)
                else False
            )
            self.activity_level = activity_point.id if activity_point else 0

            activity_log = await DBLog.create(
                bot,
                None,
                self,
                bot.user,
                "ACTIVITY_REWARD",
                notes=f"Activity Level {self.activity_level+1 if revert else self.activity_level}{' [REVERSION]' if revert else ''}",
                cc=-1 if revert else 0,
                silent=True,
            )

            if self.guild.activity_points_channel and not revert:
                await self.guild.activity_points_channel.send(
                    embed=LogEmbed(activity_log), content=f"{self.member.mention}"
                )

            if self.guild.staff_channel and revert:
                await self.guild.staff_channel.send(embed=LogEmbed(activity_log))
                await self.member.send(embed=LogEmbed(activity_log))

        else:
            await self.upsert()

    async def manage_player_tier_roles(self, bot: G0T0Bot, reason: str = None) -> None:
        # Primary Role handling
        if self.highest_level_character and self.highest_level_character.level >= 3:
            if (
                self.guild.member_role
                and self.guild.member_role not in self.member.roles
            ):
                await self.member.add_roles(self.guild.member_role, reason=reason)

        # Character Tier Roles
        if self.guild.entry_role:
            if self.has_character_in_tier(bot.compendium, 1):
                if self.guild.entry_role not in self.member.roles:
                    await self.member.add_roles(self.guild.entry_role, reason=reason)
            elif self.guild.entry_role in self.member.roles:
                await self.member.remove_roles(self.guild.entry_role, reason=reason)

        if self.guild.tier_2_role:
            if self.has_character_in_tier(bot.compendium, 2):
                if self.guild.tier_2_role not in self.member.roles:
                    await self.member.add_roles(self.guild.tier_2_role, reason=reason)
            elif self.guild.tier_2_role in self.member.roles:
                await self.member.remove_roles(self.guild.tier_2_role, reason=reason)

        if self.guild.tier_3_role:
            if self.has_character_in_tier(bot.compendium, 3):
                if self.guild.tier_3_role not in self.member.roles:
                    await self.member.add_roles(self.guild.tier_3_role, reason=reason)
            elif self.guild.tier_3_role in self.member.roles:
                await self.member.remove_roles(self.guild.tier_3_role, reason=reason)

        if self.guild.tier_4_role:
            if self.has_character_in_tier(bot.compendium, 4):
                if self.guild.tier_4_role not in self.member.roles:
                    await self.member.add_roles(self.guild.tier_4_role, reason=reason)
            elif self.guild.tier_4_role in self.member.roles:
                await self.member.remove_roles(self.guild.tier_4_role, reason=reason)

        if self.guild.tier_5_role:
            if self.has_character_in_tier(bot.compendium, 5):
                if self.guild.tier_5_role not in self.member.roles:
                    await self.member.add_roles(self.guild.tier_5_role, reason=reason)
            elif self.guild.tier_5_role in self.member.roles:
                await self.member.remove_roles(self.guild.tier_5_role, reason=reason)

        if self.guild.tier_6_role:
            if self.has_character_in_tier(bot.compendium, 6):
                if self.guild.tier_6_role not in self.member.roles:
                    await self.member.add_roles(self.guild.tier_6_role, reason=reason)
            elif self.guild.tier_6_role in self.member.roles:
                await self.member.remove_roles(self.guild.tier_6_role, reason=reason)


class ArenaPost(object):
    """
    Represents a post in the arena associated with a player and their characters.
    Attributes:
        player (Player): The player associated with the arena post.
        characters (list[PlayerCharacter]): A list of characters associated with the player requesting the arena.
        type (ArenaPostType): The type of the arena post. Defaults to ArenaPostType.COMBAT.
        message (Message): An optional message associated with the arena post.
    Args:
        player (Player): The player associated with the arena post.
        characters (list[PlayerCharacter], optional): A list of characters associated with the player. Defaults to an empty list.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """

    def __init__(
        self, player: Player, characters: list[PlayerCharacter] = [], *args, **kwargs
    ):
        self.player = player
        self.characters = characters
        self.type: ArenaPostType = kwargs.get("type", ArenaPostType.COMBAT)

        self.message: discord.Message = kwargs.get("message")


class RPPost(object):
    """
    A class to represent a role-playing post.
    Attributes
    ----------
    character : PlayerCharacter
        The character associated with the post.
    note : str, optional
        An optional note associated with the post.
    Methods
    -------
    __init__(character: PlayerCharacter, *args, **kwargs)
        Initializes the RPPost with a character and optional note.
    """

    def __init__(self, character: PlayerCharacter, *args, **kwargs):
        self.character = character
        self.note = kwargs.get("note")
