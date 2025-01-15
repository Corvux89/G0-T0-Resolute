import bisect
from datetime import datetime, timezone
from statistics import mode

import discord
import sqlalchemy as sa
import aiopg.sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import TIMESTAMP, BigInteger, Column, Integer, and_, null
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql.selectable import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories import ArenaTier, ArenaType
from Resolute.models.objects.characters import PlayerCharacter


class Arena(object):    
    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, channel_id: int, host_id: int, tier: ArenaTier, type: ArenaType, **kwargs):
        self._db = db
        self._compendium = compendium

        self.id = kwargs.get('id')
        self.channel_id = channel_id
        self.tier = tier
        self.type = type
        self.host_id = host_id
        self.completed_phases = kwargs.get('completed_phases', 0)
        self.characters: list[int] = kwargs.get('characters', [])
        self.created_ts = kwargs.get('created_ts', datetime.now(timezone.utc))
        self.end_ts = kwargs.get('end_ts')
        self.player_characters: list[PlayerCharacter] = []
        self.pin_message_id = kwargs.get('pin_message_id')

        self.channel: discord.TextChannel = kwargs.get('channel')

    def update_tier(self):
        if self.player_characters:
            avg_level = mode(c.level for c in self.player_characters)
            tiers = list(self._compendium.arena_tier[0].values())
            levels = sorted([t.avg_level for t in tiers])

            if avg_level > levels[-1]:
                self.tier = tiers[-1]
            else:
                tier = bisect.bisect(levels, avg_level)
                self.tier = self._compendium.get_object(ArenaTier, tier)

    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_arena_query(self))
            row = await results.first()

        if row is None:
            return None
        
        arena = await ArenaSchema(self._db, self._compendium).load(row)

        return arena
    
    async def close(self):
        self.end_ts = datetime.now(timezone.utc)

        await self.upsert()

        if message := await self.channel.fetch_message(self.pin_message_id):
            await message.delete(reason="Closing Arena")
        
    
    
arenas_table = sa.Table(
    "arenas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("channel_id", BigInteger, nullable=False),
    Column("pin_message_id", BigInteger, nullable=False),
    Column("host_id", BigInteger, nullable=False),  # ref: > characters.player_id
    Column("tier", Integer, nullable=False, default=1),  # ref: > c_arena_tier.id
    Column("type", Integer, nullable=False, default=1),  # ref: > c_arena_type.id
    Column("completed_phases", Integer, nullable=False, default=0),
    Column("created_ts", TIMESTAMP(timezone=timezone.utc)),
    Column("end_ts", TIMESTAMP(timezone=timezone.utc), nullable=True, default=null()),
    Column("characters", ARRAY(Integer), nullable=True)
)

class ArenaSchema(Schema):
    db: aiopg.sa.Engine
    compendium: Compendium

    id = fields.Integer(data_key="id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    pin_message_id = fields.Integer(data_key="pin_message_id", required=True)
    host_id = fields.Integer(data_key="host_id", required=True)
    tier = fields.Method(None, "load_tier")
    type = fields.Method(None, "load_type")
    completed_phases = fields.Integer(data_key="completed_phases", required=True, default=0)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)
    characters = fields.List(fields.Integer, required=False, allow_none=True, default=[])

    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.compendium = compendium

    @post_load
    async def make_arena(self, data, **kwargs):
        arena = Arena(self.db, self.compendium, **data)
        arena.channel = self.bot.get_channel(data.get('channel_id'))
        await self.get_characters(arena)
        return arena

    def load_tier(self, value):
        return self.compendium.get_object(ArenaTier, value)

    def load_type(self, value):
        return self.compendium.get_object(ArenaType, value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    
    async def get_characters(self, arena: Arena):
        for char in arena.characters:
            arena.player_characters.append(await self.bot.get_character(char))


def get_arena_by_channel_query(channel_id: int) -> FromClause:
    return arenas_table.select().where(
        and_(arenas_table.c.channel_id == channel_id, arenas_table.c.end_ts == null())
    )

def get_arena_by_host_query(member_id: int) -> FromClause:
    return arenas_table.select().where(
        and_(arenas_table.c.host_id == member_id, arenas_table.c.end_ts == null())
    )

def get_character_arena_query(char_id: int) -> FromClause:
    return arenas_table.select().where(
        and_(arenas_table.c.characters.contains([char_id]), arenas_table.c.end_ts == null())
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
            "end_ts": arena.end_ts
        }

        update_statement = arenas_table.update().where(arenas_table.c.id == arena.id).values(**update_dict).returning(arenas_table)
        return update_statement
    
    return arenas_table.insert().values(
        channel_id=arena.channel_id,
        pin_message_id=arena.pin_message_id,
        host_id=arena.host_id,
        tier=arena.tier.id,
        type=arena.type.id,
        characters=arena.characters,
        created_ts=arena.created_ts,
        completed_phases=arena.completed_phases
    ).returning(arenas_table)



        