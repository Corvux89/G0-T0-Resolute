import sqlalchemy as sa

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, null, TIMESTAMP, and_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import FromClause
from marshmallow import Schema, fields, post_load

from Resolute.models import metadata
from Resolute.compendium import Compendium
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.characters import PlayerCharacter


class Adventure(object):
    def __init__(self, guild_id: int, name: str, role_id: int, category_channel_id: int, **kwargs):
        self.id = kwargs.get('id')
        self.guild_id = guild_id
        self.name: str = name
        self.role_id = role_id
        self.category_channel_id = category_channel_id
        self.dms: list[int] = kwargs.get('dms', [])
        self.characters: list[int] = kwargs.get('characters', [])
        self.cc = kwargs.get('cc')
        self.player_characters: list[PlayerCharacter] = []
        self.created_ts = kwargs.get('created_ts', datetime.now(timezone.utc))
        self.end_ts = kwargs.get('end_ts')

adventures_table = sa.Table(
    "adventures",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("guild_id", BigInteger, nullable=False),
    Column("name", String, nullable=False),
    Column("role_id", BigInteger, nullable=False),
    Column("dms", ARRAY(BigInteger), nullable=False),  # ref: <> characters.player_id
    Column("category_channel_id", BigInteger, nullable=False),
    Column("cc", Integer, nullable=False, default=0),
    Column("created_ts", TIMESTAMP(timezone=timezone.utc)),
    Column("end_ts", TIMESTAMP(timezone=timezone.utc), nullable=True, default=null()),
    Column("characters", ARRAY(Integer), nullable=False)
)

class AdventureSchema(Schema):
    compendium: Compendium
    id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    name = fields.String(required=True)
    role_id = fields.Integer(required=True)
    dms = fields.List(fields.Integer, required=True)
    category_channel_id = fields.Integer(required=True)
    cc = fields.Integer(data_key="cc", required=True)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)
    characters = fields.List(fields.Integer, required=False, allow_none=True, default=[])

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_adventure(self, data, **kwargs):
        return Adventure(**data)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    

def upsert_adventure_query(adventure: Adventure):
    if hasattr(adventure, "id") and adventure.id is not None:
        update_dict = {
            "guild_id": adventure.guild_id,
            "name": adventure.name,
            "role_id": adventure.role_id,
            "dms": adventure.dms,
            "category_channel_id": adventure.category_channel_id,
            "cc": adventure.cc,
            "created_ts": adventure.created_ts,
            "end_ts": adventure.end_ts,
            "characters": adventure.characters
        }

        update_statment = adventures_table.update().where(adventures_table.c.id == adventure.id).values(**update_dict).returning(adventures_table)
        return update_statment
    
    return adventures_table.insert().values(
        guild_id=adventure.guild_id,
        name=adventure.name,
        role_id=adventure.role_id,
        dms=adventure.dms,
        category_channel_id=adventure.category_channel_id,
        cc=adventure.cc,
        created_ts=adventure.created_ts
    ).returning(adventures_table)
    
def get_character_adventures_query(char_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.characters.contains([char_id]), adventures_table.c.end_ts == null())
    ).order_by(adventures_table.c.id.asc())

def get_adventures_by_dm_query(member_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.dms.contains([member_id]), adventures_table.c.end_ts == null())
    ).order_by(adventures_table.c.id.asc())

def get_adventure_by_role_query(role_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.role_id == role_id, adventures_table.c.end_ts == null())
    )

def get_adventure_by_category_channel_query(category_channel_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.category_channel_id == category_channel_id, adventures_table.c.end_ts == null())
    )