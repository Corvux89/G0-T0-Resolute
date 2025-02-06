from discord import ApplicationContext, Thread
from marshmallow import Schema, fields, post_load
import sqlalchemy as sa
from sqlalchemy import BigInteger, Column, Integer, String, and_, null
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.sql import FromClause, TableClause
import Resolute.helpers.general_helpers as gh
from Resolute.models import metadata



import aiopg.sa

class NPC(object):
    def __init__(self, db: aiopg.sa.Engine, guild_id: int, key: str, name: str, **kwargs):
        self._db = db
        self.guild_id: int = guild_id
        self.key: str = key
        self.name: str = name
        self.avatar_url: str = kwargs.get('avatar_url')
        self.roles: list[int] = kwargs.get('roles', [])
        self.adventure_id: int = kwargs.get('adventure_id')

    async def delete(self):
        async with self._db.acquire() as conn:
            await conn.execute(delete_npc_query(self))

    async def upsert(self):
        async with self._db.acquire() as conn:
            await conn.execute(upsert_npc_query(self))

    async def send_webhook_message(self, ctx: ApplicationContext, content: str):
        webhook = await gh.get_webhook(ctx.channel)

        if isinstance(ctx.channel, Thread):
            await webhook.send(username=self.name,
                               avatar_url=self.avatar_url if self.avatar_url else None,
                               content=content,
                               thread=ctx.channel)
            
        else:
            await webhook.send(username=self.name,
                               avatar_url=self.avatar_url if self.avatar_url else None,
                               content=content)


npc_table = sa.Table(
    "ref_npc",
    metadata,
    Column("guild_id", Integer, nullable=False),
    Column("key", String, nullable=False),
    Column("name", String, nullable=False),
    Column("avatar_url", String, nullable=True),
    Column("roles", ARRAY(BigInteger), nullable=False),
    Column("adventure_id", Integer, nullable=True),
    sa.PrimaryKeyConstraint("guild_id", "key")
)


class NPCSchema(Schema):
    db: aiopg.sa.Engine

    guild_id=fields.Integer(required=True)
    key=fields.String(required=True)
    name=fields.String(required=True)
    avatar_url=fields.String(required=False, allow_none=True)
    roles=fields.List(fields.Integer, required=True)
    adventure_id=fields.Integer(required=False, allow_none=True)

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        super().__init__(**kwargs)
        self.db = db


    @post_load
    def make_npc(self, data, **kwargs):
        npc = NPC(self.db, **data)
        return npc


def get_npc_query(guild_id: int, key: str) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.key == key)
    )


def get_guild_npcs_query(guild_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.adventure_id == null())
    ).order_by(npc_table.c.key.asc())


def get_adventure_npcs_query(adventure_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.adventure_id == adventure_id)
    ).order_by(npc_table.c.key.asc())


def upsert_npc_query(npc: NPC):
    insert_dict = {
        "key": npc.key,
        "guild_id": npc.guild_id,
        "name": npc.name,
        "avatar_url": npc.avatar_url,
        "adventure_id": npc.adventure_id,
        "roles": npc.roles
    }

    statement = insert(npc_table).values(insert_dict)

    statement = statement.on_conflict_do_update(
        index_elements=['guild_id', 'key'],
        set_={
            'name': statement.excluded.name,
            'avatar_url': statement.excluded.avatar_url,
            'adventure_id': statement.excluded.adventure_id,
            'roles': statement.excluded.roles
        }
    )

    return statement.returning(npc_table)


def delete_npc_query(npc: NPC) -> TableClause:
    return npc_table.delete().where(
        and_(npc_table.c.guild_id == npc.guild_id, npc_table.c.key == npc.key)
    )
