import aiopg.sa
import discord
from discord.ext import commands
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import TableClause

import Resolute.helpers.general_helpers as gh
from Resolute.models import metadata
from Resolute.models.objects.enum import WebhookType


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

    npc_table = sa.Table(
        "ref_npc",
        metadata,
        sa.Column("guild_id", sa.Integer, nullable=False),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("avatar_url", sa.String, nullable=True),
        sa.Column("roles", ARRAY(sa.BigInteger), nullable=False),
        sa.Column("adventure_id", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("guild_id", "key"),
    )

    class NPCSchema(Schema):
        db: aiopg.sa.Engine

        guild_id = fields.Integer(required=True)
        key = fields.String(required=True)
        name = fields.String(required=True)
        avatar_url = fields.String(required=False, allow_none=True)
        roles = fields.List(fields.Integer, required=True)
        adventure_id = fields.Integer(required=False, allow_none=True)

        def __init__(self, db: aiopg.sa.Engine, **kwargs):
            super().__init__(**kwargs)
            self.db = db

        @post_load
        def make_npc(self, data, **kwargs):
            npc = NPC(self.db, **data)
            return npc

    def __init__(
        self, db: aiopg.sa.Engine, guild_id: int, key: str, name: str, **kwargs
    ):
        self._db = db
        self.guild_id: int = guild_id
        self.key: str = key
        self.name: str = name
        self.avatar_url: str = kwargs.get("avatar_url")
        self.roles: list[int] = kwargs.get("roles", [])
        self.adventure_id: int = kwargs.get("adventure_id")

    async def delete(self) -> None:
        query = NPC.npc_table.delete().where(
            sa.and_(
                NPC.npc_table.c.guild_id == self.guild_id,
                NPC.npc_table.c.key == self.key,
            )
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def upsert(self) -> None:
        insert_dict = {
            "key": self.key,
            "guild_id": self.guild_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "adventure_id": self.adventure_id,
            "roles": self.roles,
        }

        query = NPC.npc_table.insert().values(**insert_dict).returning(NPC.npc_table)

        query = query.on_conflict_do_update(
            index_elements=["guild_id", "key"],
            set_={
                "name": self.name,
                "avatar_url": self.avatar_url,
                "adventure_id": self.adventure_id,
                "roles": self.roles,
            },
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def send_webhook_message(
        self, ctx: discord.ApplicationContext, content: str
    ) -> None:
        webhook = await gh.get_webhook(ctx.channel)

        if isinstance(ctx.channel, discord.Thread):
            await webhook.send(
                username=self.name,
                avatar_url=self.avatar_url if self.avatar_url else None,
                content=content,
                thread=ctx.channel,
            )

        else:
            await webhook.send(
                username=self.name,
                avatar_url=self.avatar_url if self.avatar_url else None,
                content=content,
            )

    async def register_command(self, bot):
        async def npc_command(ctx):
            from Resolute.models.objects.webhook import G0T0Webhook

            await G0T0Webhook(
                ctx,
                type=WebhookType.adventure if self.adventure_id else WebhookType.npc,
            ).send()

        if bot.get_command(self.key) is None:
            bot.add_command(commands.Command(npc_command, name=self.key))
