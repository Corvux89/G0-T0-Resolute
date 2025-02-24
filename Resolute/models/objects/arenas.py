import bisect
from datetime import datetime, timezone
from statistics import mode

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql.selectable import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories import ArenaTier, ArenaType
from Resolute.models.objects.characters import PlayerCharacter


class Arena(object):
    """
    Represents an arena in the game.
    Attributes:
        _db (aiopg.sa.Engine): The database engine.
        _compendium (Compendium): The compendium containing game data.
        id (int): The unique identifier of the arena.
        channel_id (int): The ID of the channel associated with the arena.
        tier (ArenaTier): The tier of the arena.
        type (ArenaType): The type of the arena.
        host_id (int): The ID of the host of the arena.
        completed_phases (int): The number of completed phases in the arena.
        characters (list[int]): The list of character IDs in the arena.
        created_ts (datetime): The timestamp when the arena was created.
        end_ts (datetime): The timestamp when the arena ended.
        player_characters (list[PlayerCharacter]): The list of player characters in the arena.
        pin_message_id (int): The ID of the pinned message in the channel.
        channel (TextChannel): The text channel associated with the arena.
    Methods:
        update_tier(): Updates the tier of the arena based on the average level of player characters.
        upsert(): Inserts or updates the arena in the database.
        close(): Closes the arena, updates the end timestamp, and deletes the pinned message in the channel.
    """

    def __init__(
        self,
        db: aiopg.sa.Engine,
        compendium: Compendium,
        channel_id: int,
        host_id: int,
        tier: ArenaTier,
        type: ArenaType,
        **kwargs,
    ):
        self._db = db
        self._compendium = compendium

        self.id = kwargs.get("id")
        self.channel_id = channel_id
        self.tier = tier
        self.type = type
        self.host_id = host_id
        self.completed_phases = kwargs.get("completed_phases", 0)
        self.characters: list[int] = kwargs.get("characters", [])
        self.created_ts = kwargs.get("created_ts", datetime.now(timezone.utc))
        self.end_ts = kwargs.get("end_ts")
        self.player_characters: list[PlayerCharacter] = []
        self.pin_message_id = kwargs.get("pin_message_id")

        self.channel: discord.TextChannel = kwargs.get("channel")

    def update_tier(self) -> None:
        """
        Updates the tier of the arena based on the average level of player characters.
        The method calculates the average level of the player characters using the mode of their levels.
        It then determines the appropriate tier from the compendium based on this average level.
        If the average level exceeds the highest tier level, the highest tier is assigned.
        Otherwise, it finds the closest tier that matches or exceeds the average level and assigns it.
        Raises:
            ValueError: If there are no player characters to calculate the average level.
        """
        if self.player_characters:
            avg_level = mode(c.level for c in self.player_characters)
            tiers = list(self._compendium.arena_tier[0].values())
            levels = sorted([t.avg_level for t in tiers])

            if avg_level > levels[-1]:
                self.tier = tiers[-1]
            else:
                tier = bisect.bisect(levels, avg_level)
                self.tier = self._compendium.get_object(ArenaTier, tier)

    async def upsert(self) -> None:
        """
        Asynchronously upserts the current arena object into the database.
        This method acquires a connection from the database pool and executes
        an upsert operation using the `upsert_arena_query` function, which
        ensures that the current arena object is either inserted or updated
        in the database.
        Raises:
            Exception: If the database operation fails.
        """
        async with self._db.acquire() as conn:
            await conn.execute(upsert_arena_query(self))

    async def close(self) -> None:
        """
        Asynchronously closes the arena.
        This method performs the following actions:
        1. Sets the end timestamp to the current UTC time.
        2. Upserts the current state to the database.
        3. Fetches and deletes the pinned message in the channel, if it exists.
        Raises:
            discord.NotFound: If the pinned message is not found.
            discord.Forbidden: If the bot does not have permission to delete the message.
            discord.HTTPException: If deleting the message fails.
        """
        self.end_ts = datetime.now(timezone.utc)

        await self.upsert()

        if message := await self.channel.fetch_message(self.pin_message_id):
            await message.delete(reason="Closing Arena")


arenas_table = sa.Table(
    "arenas",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement="auto"),
    sa.Column("channel_id", sa.BigInteger, nullable=False),
    sa.Column("pin_message_id", sa.BigInteger, nullable=False),
    sa.Column("host_id", sa.BigInteger, nullable=False),  # ref: > characters.player_id
    sa.Column("tier", sa.Integer, nullable=False, default=1),  # ref: > c_arena_tier.id
    sa.Column("type", sa.Integer, nullable=False, default=1),  # ref: > c_arena_type.id
    sa.Column("completed_phases", sa.Integer, nullable=False, default=0),
    sa.Column("created_ts", sa.TIMESTAMP(timezone=timezone.utc)),
    sa.Column(
        "end_ts", sa.TIMESTAMP(timezone=timezone.utc), nullable=True, default=sa.null()
    ),
    sa.Column("characters", ARRAY(sa.Integer), nullable=True),
)


class ArenaSchema(Schema):
    bot = None

    id = fields.Integer(data_key="id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    pin_message_id = fields.Integer(data_key="pin_message_id", required=True)
    host_id = fields.Integer(data_key="host_id", required=True)
    tier = fields.Method(None, "load_tier")
    type = fields.Method(None, "load_type")
    completed_phases = fields.Integer(
        data_key="completed_phases", required=True, default=0
    )
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)
    characters = fields.List(
        fields.Integer, required=False, allow_none=True, default=[]
    )

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    async def make_arena(self, data, **kwargs):
        arena = Arena(self.bot.db, self.bot.compendium, **data)
        arena.channel = self.bot.get_channel(data.get("channel_id"))
        await self.get_characters(arena)
        return arena

    def load_tier(self, value):
        return self.bot.compendium.get_object(ArenaTier, value)

    def load_type(self, value):
        return self.bot.compendium.get_object(ArenaType, value)

    def load_timestamp(
        self, value
    ):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            tzinfo=timezone.utc,
        )

    async def get_characters(self, arena: Arena):
        for char in arena.characters:
            arena.player_characters.append(await self.bot.get_character(char))


def get_arena_by_channel_query(channel_id: int) -> FromClause:
    return arenas_table.select().where(
        sa.and_(
            arenas_table.c.channel_id == channel_id, arenas_table.c.end_ts == sa.null()
        )
    )


def get_arena_by_host_query(member_id: int) -> FromClause:
    return arenas_table.select().where(
        sa.and_(arenas_table.c.host_id == member_id, arenas_table.c.end_ts == sa.null())
    )


def get_character_arena_query(char_id: int) -> FromClause:
    return arenas_table.select().where(
        sa.and_(
            arenas_table.c.characters.contains([char_id]),
            arenas_table.c.end_ts == sa.null(),
        )
    )


def upsert_arena_query(arena: Arena):
    if hasattr(arena, "id") and arena.id is not None:
        update_dict = {
            "pin_message_id": arena.pin_message_id,
            "host_id": arena.host_id,
            "tier": arena.tier.id,
            "type": arena.type.id,
            "characters": arena.characters,
            "completed_phases": arena.completed_phases,
            "end_ts": arena.end_ts,
        }

        update_statement = (
            arenas_table.update()
            .where(arenas_table.c.id == arena.id)
            .values(**update_dict)
            .returning(arenas_table)
        )
        return update_statement

    return (
        arenas_table.insert()
        .values(
            channel_id=arena.channel_id,
            pin_message_id=arena.pin_message_id,
            host_id=arena.host_id,
            tier=arena.tier.id,
            type=arena.type.id,
            characters=arena.characters,
            created_ts=arena.created_ts,
            completed_phases=arena.completed_phases,
        )
        .returning(arenas_table)
    )
