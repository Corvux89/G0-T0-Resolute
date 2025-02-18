import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.sql import FromClause, TableClause

import Resolute.helpers.general_helpers as gh
from Resolute.models import metadata


class NPC(object):
    """
    Represents a Non-Player Character (NPC) in the system.
    Attributes:
        _db (aiopg.sa.Engine): The database engine.
        guild_id (int): The ID of the guild the NPC belongs to.
        key (str): A unique key identifier for the NPC.
        name (str): The name of the NPC.
        avatar_url (str, optional): The URL of the NPC's avatar image.
        roles (list[int], optional): A list of role IDs associated with the NPC.
        adventure_id (int, optional): The ID of the adventure the NPC is part of.
    Methods:
        delete():
            Deletes the NPC from the database.
        upsert():
            Inserts or updates the NPC in the database.
        send_webhook_message(ctx: ApplicationContext, content: str):
            Sends a message via webhook to the specified context.
    """

    def __init__(self, db: aiopg.sa.Engine, guild_id: int, key: str, name: str, **kwargs):
        self._db = db
        self.guild_id: int = guild_id
        self.key: str = key
        self.name: str = name
        self.avatar_url: str = kwargs.get('avatar_url')
        self.roles: list[int] = kwargs.get('roles', [])
        self.adventure_id: int = kwargs.get('adventure_id')

    async def delete(self) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(delete_npc_query(self))

    async def upsert(self) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(upsert_npc_query(self))

    async def send_webhook_message(self, ctx: discord.ApplicationContext, content: str) -> None:
        webhook = await gh.get_webhook(ctx.channel)

        if isinstance(ctx.channel, discord.Thread):
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
    sa.Column("guild_id", sa.Integer, nullable=False),
    sa.Column("key", sa.String, nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("avatar_url", sa.String, nullable=True),
    sa.Column("roles", ARRAY(sa.BigInteger), nullable=False),
    sa.Column("adventure_id", sa.Integer, nullable=True),
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
        sa.and_(npc_table.c.guild_id == guild_id, npc_table.c.key == key)
    )


def get_guild_npcs_query(guild_id: int) -> FromClause:
    return npc_table.select().where(
        sa.and_(npc_table.c.guild_id == guild_id, npc_table.c.adventure_id == sa.null())
    ).order_by(npc_table.c.key.asc())


def get_adventure_npcs_query(adventure_id: int) -> FromClause:
    return npc_table.select().where(
        sa.and_(npc_table.c.adventure_id == adventure_id)
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
        sa.and_(npc_table.c.guild_id == npc.guild_id, npc_table.c.key == npc.key)
    )
