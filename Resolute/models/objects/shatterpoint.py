from __future__ import annotations
from typing import TYPE_CHECKING

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY, insert


from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.guilds import PlayerGuild

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class Shatterpoint(object):
    """
    Represents a Shatterpoint object which is used to manage and interact with shatterpoints in a Discord guild.
    Attributes:
        _db (aiopg.sa.Engine): The database engine used for database operations.
        guild_id (int): The ID of the Discord guild.
        name (str): The name of the shatterpoint.
        base_cc (int): The base command currency (cc) for the shatterpoint.
        channels (list[int]): A list of channel IDs associated with the shatterpoint.
        busy (bool): A flag indicating whether the shatterpoint is busy.
        players (list[ShatterpointPlayer]): A list of players associated with the shatterpoint.
        renown (list[ShatterpointRenown]): A list of renown objects associated with the shatterpoint.
    Methods:
        __init__(db: aiopg.sa.Engine, **kwargs):
            Initializes a new instance of the Shatterpoint class.
        upsert():
            Asynchronously inserts or updates the shatterpoint in the database.
        delete():
            Asynchronously deletes the shatterpoint and its associated players and renown from the database.
        scrape_channel(bot, channel: TextChannel|Thread|ForumChannel, guild: PlayerGuild, user: User):
            Asynchronously scrapes messages from a specified channel, updates player data, and persists changes to the database.
    """

    ref_gb_staging_table = sa.Table(
        "ref_gb_staging",
        metadata,
        sa.Column(
            "guild_id", sa.BigInteger, primary_key=True, nullable=False
        ),  # ref: > guilds.id
        sa.Column("name", sa.String, nullable=False),
        sa.Column("base_cc", sa.Integer, nullable=False),
        sa.Column("channels", ARRAY(sa.BigInteger), nullable=True, default=[]),
        sa.Column("busy_member", sa.BigInteger, nullable=True),
    )

    class ShatterPointSchema(Schema):
        bot: G0T0Bot = None

        guild_id = fields.Integer(required=True)
        name = fields.String(required=True)
        base_cc = fields.Integer(required=True)
        channels = fields.List(fields.Integer, load_default=[], required=False)
        busy_member = fields.Integer(required=False, allow_none=True)

        def __init__(self, bot: G0T0Bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        async def make_shatterpoint(self, data, **kwargs):
            shatterpoint = Shatterpoint(self.bot.db, **data)
            await self.get_players(shatterpoint)
            await self.get_renown(shatterpoint)
            self.get_channels(shatterpoint)
            if shatterpoint.busy_member:
                shatterpoint.busy_member = self.bot.get_user(shatterpoint.busy_member)
            return shatterpoint

        async def get_players(self, shatterpoint: "Shatterpoint") -> None:
            query = ShatterpointPlayer.ref_gb_staging_player_table.select().where(
                ShatterpointPlayer.ref_gb_staging_player_table.c.guild_id
                == shatterpoint.guild_id
            )

            shatterpoint.players = [
                await ShatterpointPlayer.ShatterPointPlayerSchema(self.bot).load(row)
                for row in await self.bot.query(query, QueryResultType.multiple)
            ]

        async def get_renown(self, shatterpoint: "Shatterpoint") -> None:
            query = ShatterpointRenown.ref_gb_renown_table.select().where(
                ShatterpointRenown.ref_gb_renown_table.c.guild_id
                == shatterpoint.guild_id
            )

            shatterpoint.renown = [
                ShatterpointRenown.RefRenownSchema(
                    self.bot.db, self.bot.compendium
                ).load(row)
                for row in await self.bot.query(query, QueryResultType.multiple)
            ]

        def get_channels(self, shatterpoint: "Shatterpoint") -> None:
            channels = [
                self.bot.get_channel(c)
                for c in shatterpoint.channels
                if self.bot.get_channel(c)
            ]

            shatterpoint.channels = channels

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db
        self.guild_id = kwargs.get("guild_id")
        self.name = kwargs.get("name", "New Shatterpoint")
        self.base_cc = kwargs.get("base_cc", 0)
        self.channels: list[discord.abc.Messageable] = kwargs.get("channels", [])
        self.busy_member: discord.Member | discord.User = kwargs.get("busy_member")

        self.players: list[ShatterpointPlayer] = kwargs.get("players", [])
        self.renown: list[ShatterpointRenown] = kwargs.get("renown", [])

    async def upsert(self) -> None:

        update_dict = {
            "name": self.name,
            "base_cc": self.base_cc,
            "channels": [c.id for c in self.channels] if self.channels else [],
            "busy_member": (self.busy_member.id if self.busy_member else None),
        }

        insert_duct = {**update_dict, "guild_id": self.guild_id}

        query = (
            insert(Shatterpoint.ref_gb_staging_table)
            .values(**insert_duct)
            .returning(Shatterpoint.ref_gb_staging_table)
        )

        query = query.on_conflict_do_update(
            index_elements=["guild_id"], set_=update_dict
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def delete(self) -> None:
        shatterpoint_query = Shatterpoint.ref_gb_staging_table.delete().where(
            Shatterpoint.ref_gb_staging_table.c.guild_id == self.guild_id
        )

        player_query = ShatterpointPlayer.ref_gb_staging_player_table.delete().where(
            ShatterpointPlayer.ref_gb_staging_player_table.c.guild_id == self.guild_id
        )

        renown_query = ShatterpointRenown.ref_gb_renown_table.delete().where(
            ShatterpointRenown.ref_gb_renown_table.c.guild_id == self.guild_id
        )

        async with self._db.acquire() as conn:
            await conn.execute(shatterpoint_query)
            await conn.execute(player_query)
            await conn.execute(renown_query)

    async def scrape_channel(
        self,
        bot: G0T0Bot,
        channel: discord.TextChannel | discord.Thread | discord.ForumChannel,
        guild: PlayerGuild,
        user: discord.User,
    ) -> None:
        messages: list[discord.Message] = []
        channels = self.channels

        def get_char_name_from_message(message: discord.Message) -> str:
            try:
                char_name = (
                    message.author.name.split(" // ")[0].split("] ", 1)[1].strip()
                )
            except:
                return None

            return char_name

        try:
            while True:
                last_message: discord.Message = messages[-1] if messages else None
                batch = await channel.history(limit=600, before=last_message).flatten()

                if not batch:
                    break

                messages.extend(batch)
        except Exception as e:
            print(e)

        print(len(messages))
        characters = await guild.get_all_characters(bot.compendium)

        for message in messages:
            player: ShatterpointPlayer = None
            if not message.author.bot:
                player = next(
                    (p for p in self.players if p.player_id == message.author.id),
                    ShatterpointPlayer(
                        bot.db,
                        guild_id=self.guild_id,
                        player_id=message.author.id,
                        cc=self.base_cc,
                    ),
                )
            elif (char_name := get_char_name_from_message(message)) and (
                character := next(
                    (c for c in characters if c.name.lower() == char_name.lower()), None
                )
            ):
                player = next(
                    (p for p in self.players if p.player_id == character.player_id),
                    ShatterpointPlayer(
                        bot.db,
                        guild_id=self.guild_id,
                        player_id=character.player_id,
                        cc=self.base_cc,
                    ),
                )
                if character.id not in player.characters:
                    player.characters.append(character.id)

            if player:
                player.num_messages += 1

                if message.channel not in player.channels:
                    player.channels.append(message.channel)

                if player.player_id not in [p.player_id for p in self.players]:
                    self.players.append(player)

        if message.channel not in channels:
            channels.append(message.channel)

        shatterpoint: Shatterpoint = await bot.get_shatterpoint(self.guild_id)
        shatterpoint.busy_member = None
        for c in channels:
            if c not in shatterpoint.channels:
                shatterpoint.channels.append(c)

        await shatterpoint.upsert()
        for p in self.players:
            await p.upsert()

        await user.send(
            f"**{shatterpoint.name}**: Finished scraping {len(messages):,} messages in {channel.jump_url}"
        )


class ShatterpointPlayer(object):
    """
    Represents a player in the Shatterpoint game.
    Attributes:
        _db (aiopg.sa.Engine): The database engine.
        guild_id (Optional[int]): The ID of the guild the player belongs to.
        player_id (Optional[int]): The ID of the player.
        cc (Optional[int]): The player's command center level.
        update (bool): Flag indicating whether the player should be updated. Defaults to True.
        active (bool): Flag indicating whether the player is active. Defaults to True.
        num_messages (int): The number of messages the player has sent. Defaults to 0.
        channels (list[int]): List of channel IDs the player is associated with. Defaults to an empty list.
        characters (list[int]): List of character IDs the player owns. Defaults to an empty list.
        renown_override (Optional[int]): Override value for the player's renown.
        player_characters (list[PlayerCharacter]): List of PlayerCharacter objects associated with the player. Defaults to an empty list.
    Methods:
        upsert(): Inserts or updates the player record in the database.
    """

    ref_gb_staging_player_table = sa.Table(
        "ref_gb_staging_player",
        metadata,
        sa.Column(
            "guild_id", sa.BigInteger, nullable=False
        ),  # ref: > ref_gb_staging.id
        sa.Column(
            "player_id", sa.BigInteger, nullable=False
        ),  # ref: > characters.player_id
        sa.Column("cc", sa.Integer, nullable=False),
        sa.Column("update", sa.BOOLEAN, nullable=False, default=True),
        sa.Column("active", sa.BOOLEAN, nullable=False, default=True),
        sa.Column("num_messages", sa.Integer, nullable=False, default=0),
        sa.Column("channels", ARRAY(sa.BigInteger), nullable=True, default=[]),
        sa.Column("characters", ARRAY(sa.Integer), nullable=False, default=[]),
        sa.Column("renown_override", sa.Integer, nullable=True),
    )

    class ShatterPointPlayerSchema(Schema):
        bot: G0T0Bot = None

        guild_id = fields.Integer(required=True)
        player_id = fields.Integer(required=True)
        cc = fields.Integer(required=True)
        update = fields.Boolean(required=True)
        active = fields.Boolean(required=True)
        num_messages = fields.Integer(required=True)
        channels = fields.List(fields.Integer, load_default=[], required=False)
        characters = fields.List(fields.Integer, required=True)
        renown_override = fields.Integer(required=False, allow_none=True)
        sa.PrimaryKeyConstraint("guild_id", "player_id")

        def __init__(self, bot: G0T0Bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        async def make_globPlayer(self, data, **kwargs):
            player = ShatterpointPlayer(self.bot.db, **data)
            guild = self.bot.get_guild(player.guild_id)

            await self.get_characters(player)
            self.get_channels(player)
            player.member = guild.get_member(player.player_id)
            return player

        async def get_characters(self, player: "ShatterpointPlayer"):
            player.player_characters = [
                await self.bot.get_character(c) for c in player.characters
            ]

        def get_channels(self, player: "ShatterpointPlayer") -> None:
            channels = [
                self.bot.get_channel(c)
                for c in player.channels
                if self.bot.get_channel(c)
            ]

            player.channels = channels

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db

        self.guild_id = kwargs.get("guild_id")
        self.player_id = kwargs.get("player_id")
        self.cc = kwargs.get("cc")
        self.update = kwargs.get("update", True)
        self.active = kwargs.get("active", True)
        self.num_messages = kwargs.get("num_messages", 0)
        self.channels: list[discord.abc.Messageable] = kwargs.get("channels", [])
        self.characters: list[int] = kwargs.get("characters", [])
        self.renown_override: int = kwargs.get("renown_override")

        self.player_characters: list[PlayerCharacter] = kwargs.get(
            "player_characters", []
        )

        self.member: discord.Member = kwargs.get("member")

    async def upsert(self) -> None:
        update_dict = {
            "cc": self.cc,
            "renown_override": self.renown_override,
            "num_messages": self.num_messages,
            "channels": [c.id for c in self.channels] if self.channels else [],
            "update": self.update,
            "active": self.active,
            "characters": self.characters,
        }

        insert_dict = {
            **update_dict,
            "guild_id": self.guild_id,
            "player_id": self.player_id,
        }

        query = (
            insert(ShatterpointPlayer.ref_gb_staging_player_table)
            .values(**insert_dict)
            .returning(ShatterpointPlayer.ref_gb_staging_player_table)
        )

        query = query.on_conflict_do_update(
            index_elements=["guild_id", "player_id"], set_=update_dict
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)


class ShatterpointRenown(object):
    ref_gb_renown_table = sa.Table(
        "ref_gb_renown",
        metadata,
        sa.Column("guild_id", sa.Integer, nullable=False),
        sa.Column("faction", sa.Integer, nullable=False),
        sa.Column("renown", sa.Integer, nullable=False, default=0),
        sa.PrimaryKeyConstraint("guild_id", "faction"),
    )

    class RefRenownSchema(Schema):
        compendium: Compendium
        db: aiopg.sa.Engine
        guild_id = fields.Integer(required=True)
        faction = fields.Method(None, "load_faction")
        renown = fields.Integer(required=True)

        def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
            self.compendium = compendium
            self.db = db
            super().__init__(**kwargs)

        def load_faction(self, value: int) -> Faction:
            return self.compendium.get_object(Faction, value)

        @post_load
        def make_gbrenown(self, data, **kwargs):
            return ShatterpointRenown(self.db, **data)

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db
        self.guild_id = kwargs.get("guild_id")
        self.faction: Faction = kwargs.get("faction")
        self.renown = kwargs.get("renown", 0)

    async def upsert(self) -> None:
        update_dict = {"renown": self.renown}

        insert_dict = {
            **update_dict,
            "guild_id": self.guild_id,
            "faction": self.faction.id,
        }

        query = (
            insert(ShatterpointRenown.ref_gb_renown_table)
            .values(**insert_dict)
            .returning(ShatterpointRenown.ref_gb_renown_table)
        )

        query = query.on_conflict_do_update(
            index_elements=["guild_id", "faction"], set_=update_dict
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def delete(self) -> None:
        query = ShatterpointRenown.ref_gb_renown_table.delete().where(
            sa.and_(
                ShatterpointRenown.ref_gb_renown_table.c.guild_id == self.guild_id,
                ShatterpointRenown.ref_gb_renown_table.c.faction == self.faction.id,
            )
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)
