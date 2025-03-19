from __future__ import annotations
from typing import TYPE_CHECKING

import aiopg.sa
import discord
from discord.ext import commands
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY, insert

import Resolute.helpers as gh
from Resolute.models import metadata
from Resolute.models.objects.enum import QueryResultType, WebhookType

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class NonPlayableCharacter(object):
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
            npc = NonPlayableCharacter(self.db, **data)
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
        query = NonPlayableCharacter.npc_table.delete().where(
            sa.and_(
                NonPlayableCharacter.npc_table.c.guild_id == self.guild_id,
                NonPlayableCharacter.npc_table.c.key == self.key,
            )
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def upsert(self) -> None:
        update_dict = {
            "name": self.name,
            "avatar_url": self.avatar_url,
            "adventure_id": self.adventure_id,
            "roles": self.roles,
        }

        insert_dict = {
            **update_dict,
            "key": self.key,
            "guild_id": self.guild_id,
        }

        query = (
            insert(NonPlayableCharacter.npc_table)
            .values(**insert_dict)
            .returning(NonPlayableCharacter.npc_table)
        )

        query = query.on_conflict_do_update(
            index_elements=["guild_id", "key"], set_=update_dict
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

    async def register_command(self, bot: G0T0Bot):
        async def npc_command(ctx):
            from Resolute.models.objects.webhook import G0T0Webhook

            await G0T0Webhook(
                ctx,
                type=WebhookType.adventure if self.adventure_id else WebhookType.npc,
            ).send()

        if bot.get_command(self.key) is None:
            cmd = commands.Command(npc_command, name=self.key)
            cmd.add_check(gh.dm_check)
            bot.add_command(cmd)

    @staticmethod
    async def get_all(bot: G0T0Bot) -> list["NonPlayableCharacter"]:
        query = NonPlayableCharacter.npc_table.select().order_by(
            NonPlayableCharacter.npc_table.c.key.asc()
        )

        npcs = [
            NonPlayableCharacter.NPCSchema(bot.db).load(row)
            for row in await bot.query(query, QueryResultType.multiple)
        ]

        return npcs
