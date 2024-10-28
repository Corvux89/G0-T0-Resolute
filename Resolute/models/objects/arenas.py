import discord
import sqlalchemy as sa

from sqlalchemy import Column, Integer, BigInteger, null, TIMESTAMP, and_, null
from datetime import datetime, timezone
from marshmallow import Schema, fields, post_load
from sqlalchemy.sql.selectable import FromClause
from sqlalchemy.dialects.postgresql import ARRAY

from Resolute.models import metadata
from Resolute.compendium import Compendium
from Resolute.models.categories import ArenaTier, ArenaType
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player


class Arena(object):
    players: list[Player] = []
    
    def __init__(self, channel_id: int, role_id: int, host_id: int, tier: ArenaTier, type: ArenaType, **kwargs):
        self.id = kwargs.get('id')
        self.channel_id = channel_id
        self.role_id = role_id
        self.tier = tier
        self.type = type
        self.host_id = host_id
        self.completed_phases = kwargs.get('completed_phases', 0)
        self.characters: list[int] = kwargs.get('characters', [])
        self.created_ts = kwargs.get('created_ts', datetime.now(timezone.utc))
        self.end_ts = kwargs.get('end_ts')
        self.player_characters: list[PlayerCharacter] = []
        self.pin_message_id = kwargs.get('pin_message_id')
    
arenas_table = sa.Table(
    "arenas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("channel_id", BigInteger, nullable=False),
    Column("pin_message_id", BigInteger, nullable=False),
    Column("role_id", BigInteger, nullable=False),
    Column("host_id", BigInteger, nullable=False),  # ref: > characters.player_id
    Column("tier", Integer, nullable=False, default=1),  # ref: > c_arena_tier.id
    Column("type", Integer, nullable=False, default=1),  # ref: > c_arena_type.id
    Column("completed_phases", Integer, nullable=False, default=0),
    Column("created_ts", TIMESTAMP(timezone=timezone.utc)),
    Column("end_ts", TIMESTAMP(timezone=timezone.utc), nullable=True, default=null()),
    Column("characters", ARRAY(Integer), nullable=True)
)

class ArenaSchema(Schema):
    compendium: Compendium
    id = fields.Integer(data_key="id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    pin_message_id = fields.Integer(data_key="pin_message_id", required=True)
    role_id = fields.Integer(data_key="role_id", required=True)
    host_id = fields.Integer(data_key="host_id", required=True)
    tier = fields.Method(None, "load_tier")
    type = fields.Method(None, "load_type")
    completed_phases = fields.Integer(data_key="completed_phases", required=True, default=0)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)
    characters = fields.List(fields.Integer, required=False, allow_none=True, default=[])

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_arena(self, data, **kwargs):
        return Arena(**data)

    def load_tier(self, value):
        return self.compendium.get_object(ArenaTier, value)

    def load_type(self, value):
        return self.compendium.get_object(ArenaType, value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)

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
            "role_id": arena.role_id,
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
        role_id=arena.role_id,
        host_id=arena.host_id,
        tier=arena.tier.id,
        type=arena.type.id,
        characters=arena.characters,
        created_ts=arena.created_ts,
        completed_phases=arena.completed_phases
    ).returning(arenas_table)

class ArenaPost(object):
    def __init__(self, player: Player, characters: list[PlayerCharacter] = [], *args, **kwargs):
        self.player = player
        self.characters = characters

        self.message: discord.Message = kwargs.get("message")



                
        