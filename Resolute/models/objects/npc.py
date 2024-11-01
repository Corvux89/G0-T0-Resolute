import sqlalchemy as sa

from Resolute.compendium import Compendium
from Resolute.models import metadata
from sqlalchemy import Column, Integer, String, null, and_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import FromClause
from marshmallow import Schema, fields, post_load

class NPC(object):
    def __init__(self, guild_id: int, key: str, name: str, **kwargs):
        self.id = kwargs.get('id')
        self.guild_id = guild_id
        self.key = key
        self.name = name
        self.avatar_url = kwargs.get('avatar_url')
        self.roles = kwargs.get('roles', [])
        self.adventure_id = kwargs.get('adventure_id')

npc_table = sa.Table(
    "npc",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("guild_id", Integer, nullable=False),
    Column("key", String, nullable=False),
    Column("name", String, nullable=False),
    Column("avatar_url", String, nullable=True),
    Column("roles", ARRAY(Integer), nullable=False),
    Column("adventure_id", Integer, nullable=True)
)

class NPCSchema(Schema):
    compendium: Compendium
    id=fields.Integer(required=True)
    guild_id=fields.Integer(required=True)
    key=fields.String(required=True)
    name=fields.String(required=True)
    avatar_url=fields.String(required=False, allow_none=True)
    roles=fields.List(fields.Integer, required=True)
    adventure_id=fields.Integer(required=False, allow_none=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @post_load
    def make_npc(self, data, **kwargs):
        return NPC(**data)
    
def upsert_npc_query(npc: NPC):
    if hasattr(npc, "id") and npc.id is not None:
        update_dict = {
            "key": npc.key,
            "name": npc.name,
            "avatar_url": npc.avatar_url,
            "adventure_id": npc.adventure_id,
            "roles": npc.roles
        }

        update_statement = npc_table.update().where(npc_table.c.id == npc.id).values(**update_dict).returning(npc_table)
        return update_statement
    
    return npc_table.insert().values(
        guild_id=npc.guild_id,
        key=npc.key,
        name=npc.name,
        avatar_url=npc.avatar_url,
        roles=npc.roles,
        adventure_id=npc.adventure_id
    ).returning(npc_table)

def get_npc(guild_id: int, key: str) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.key == key)
    )

def get_guild_npcs_query(guild_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.adventure_id == null())
    ).order_by(npc_table.c.id.asc())

def get_adventure_npcs_query(adventure_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.adventure_id == adventure_id)
    ).order_by(npc_table.c.id.asc())