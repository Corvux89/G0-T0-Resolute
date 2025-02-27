from __future__ import annotations
from typing import TYPE_CHECKING

from datetime import datetime, timezone

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY
from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects import RelatedList
from Resolute.models.objects.npc import NPC
from Resolute.models.objects.characters import PlayerCharacter

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class Adventure(object):
    """
    Represents an adventure in the system.
    Attributes:
        adventures_table (Table): SQLAlchemy table definition for adventures.
        _db (aiopg.sa.Engine): Database engine.
        id (int): Unique identifier for the adventure.
        guild_id (int): Identifier for the guild associated with the adventure.
        name (str): Name of the adventure.
        category_channel (discord.CategoryChannel): Discord category channel for the adventure.
        role (discord.Role): Discord role associated with the adventure.
        role_id (int): Identifier for the role.
        category_channel_id (int): Identifier for the category channel.
        dms (list[int]): List of Dungeon Master IDs.
        characters (list[int]): List of character IDs.
        cc (int): Custom attribute, purpose not specified.
        player_characters (list[PlayerCharacter]): List of player characters.
        created_ts (datetime): Timestamp when the adventure was created.
        end_ts (datetime): Timestamp when the adventure ended.
        factions (list[Faction]): List of factions associated with the adventure.
        npcs (list[NPC]): List of NPCs in the adventure.
    Methods:
        __init__(db, guild_id, name, role, category_channel, **kwargs): Initializes an Adventure instance.
        upsert(): Asynchronously upserts an adventure record in the database.
        update_dm_permissions(member, remove=False): Updates the Dungeon Master's permissions for the adventure.
        get_npc(**kwargs): Retrieves an NPC based on the provided criteria.
    """

    adventures_table = sa.Table(
        "adventures",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement="auto"),
        sa.Column("guild_id", sa.BigInteger, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("role_id", sa.BigInteger, nullable=False),
        sa.Column(
            "dms", ARRAY(sa.BigInteger), nullable=False
        ),  # ref: <> characters.player_id
        sa.Column("category_channel_id", sa.BigInteger, nullable=False),
        sa.Column("cc", sa.Integer, nullable=False, default=0),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=timezone.utc)),
        sa.Column(
            "end_ts",
            sa.TIMESTAMP(timezone=timezone.utc),
            nullable=True,
            default=sa.null(),
        ),
        sa.Column("characters", ARRAY(sa.Integer), nullable=False),
        sa.Column("factions", ARRAY(sa.Integer), nullable=False),
    )

    class AdventureSchema(Schema):
        bot: G0T0Bot = None

        id = fields.Integer(required=True)
        guild_id = fields.Integer(required=True)
        name = fields.String(required=True)
        role_id = fields.Integer(required=True)
        dms = fields.List(fields.Integer, required=True)
        category_channel_id = fields.Integer(required=True)
        cc = fields.Integer(data_key="cc", required=True)
        created_ts = fields.Method(None, "load_timestamp")
        end_ts = fields.Method(None, "load_timestamp", allow_none=True)
        characters = fields.List(
            fields.Integer, required=False, allow_none=True, default=[]
        )
        factions = fields.Method(None, "load_factions")

        def __init__(self, bot: G0T0Bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        async def make_adventure(self, data, **kwargs) -> "Adventure":
            guild = self.bot.get_guild(data["guild_id"])
            adventure = Adventure(
                self.bot.db,
                **data,
                role=guild.get_role(data["role_id"]),
                category_channel=self.bot.get_channel(data["category_channel_id"]),
            )
            await self.get_characters(adventure)
            await self.get_npcs(adventure)
            return adventure

        def load_timestamp(
            self, value: datetime
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

        def load_factions(self, value):
            factions = []
            for f in value:
                factions.append(self.bot.compendium.get_object(Faction, f))
            return factions

        async def get_characters(self, adventure: "Adventure") -> None:
            if adventure.characters:
                for char_id in adventure.characters:
                    if char := await self.bot.get_character(char_id):
                        adventure._player_characters.append(char)

        async def get_npcs(self, adventure: "Adventure") -> None:
            query = NPC.npc_table.select().where(
                sa.and_(NPC.npc_table.c.adventure_id == adventure.id)
            )

            async with self.bot.db.acquire() as conn:
                results = await conn.execute(query)
                rows = await results.fetchall()

            adventure.npcs = [NPC.NPCSchema(self.bot.db).load(row) for row in rows]

    def __init__(
        self,
        db: aiopg.sa.Engine,
        guild_id: int,
        name: str,
        role: discord.Role,
        category_channel: discord.CategoryChannel,
        **kwargs,
    ):
        self._db = db

        self.id = kwargs.get("id")
        self.guild_id = guild_id
        self.name: str = name
        self.role_id = role.id
        self.category_channel_id = category_channel.id
        self.dms: list[int] = kwargs.get("dms", [])
        self.characters: list[int] = kwargs.get("characters", [])
        self.cc = kwargs.get("cc", 0)
        self._player_characters: RelatedList(self, self.update_characters) = []
        self.created_ts = kwargs.get("created_ts", datetime.now(timezone.utc))
        self.end_ts = kwargs.get("end_ts")
        self.factions: list[Faction] = kwargs.get("factions", [])

        self._category_channel: discord.CategoryChannel = category_channel
        self._role: discord.Role = role

        # Virtual attributes
        self.npcs: list[NPC] = []

    def update_characters(self):
        self.characters = [c.id for c in self._player_characters]

    @property
    def player_characters(self) -> list[PlayerCharacter]:
        return self._player_characters

    @player_characters.setter
    def player_characters(self, value: list[PlayerCharacter]):
        self._player_characters = RelatedList(self, self.update_characters, value)
        self.update_characters()

    @property
    def category_channel(self) -> discord.CategoryChannel:
        return self._category_channel

    @category_channel.setter
    def category_channel(self, value: discord.CategoryChannel):
        self._category_channel = value
        self.category_channel_id = value.id

    @property
    def role(self) -> discord.Role:
        return self._role

    @role.setter
    def role(self, value: discord.Role):
        self.role = value
        self.role_id = value.id

    async def upsert(self) -> None:
        """
        Asynchronously upserts an adventure record in the database.
        This method acquires a connection from the database pool and executes
        an upsert query to insert or update the adventure record.
        Returns:
            None
        """
        update_dict = {
            "name": self.name,
            "role_id": self.role_id,
            "dms": self.dms,
            "category_channel_id": self.category_channel_id,
            "cc": self.cc,
            "end_ts": self.end_ts,
            "characters": self.characters,
            "factions": [f.id for f in self.factions],
        }

        insert_dict = {
            **update_dict,
            "guild_id": self.guild_id,
            "created_ts": self.created_ts,
        }

        if hasattr(self, "id") and self.id is not None:
            query = (
                self.adventures_table.update()
                .where(self.adventures_table.c.id == self.id)
                .values(**update_dict)
            )
        else:
            query = self.adventures_table.insert().values(**insert_dict)

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def update_dm_permissions(
        self, member: discord.Member, remove: bool = False
    ) -> None:
        """
        Updates the Dungeon Master's permissions for the adventure.
        This method adds or removes the specified role and permissions for the given member
        in the adventure's category and its channels.
        Args:
            member (Member): The member whose permissions are to be updated.
            remove (bool, optional): If True, removes the role and permissions from the member.
                                     If False, adds the role and permissions to the member.
                                     Defaults to False.
        Returns:
            None
        """
        if remove:
            if self.role in member.roles:
                await member.remove_roles(
                    self.role, reason=f"Removed from adventure {self.name}"
                )
        else:
            if self.role not in member.roles:
                await member.add_roles(
                    self.role, reason=f"Creating/Modifying adventure {self.name}"
                )

        category_overwrites = self.category_channel.overwrites
        if remove:
            del category_overwrites[member]
        else:
            category_overwrites[member] = discord.PermissionOverwrite(
                manage_messages=True
            )

        await self.category_channel.edit(overwrites=category_overwrites)

        for channel in self.category_channel.channels:
            overwrites = channel.overwrites
            if remove:
                del overwrites[member]
            else:
                overwrites[member] = discord.PermissionOverwrite(manage_messages=True)
            await channel.edit(overwrites=overwrites)

    def get_npc(self, **kwargs) -> NPC:
        if kwargs.get("key"):
            return next(
                (npc for npc in self.npcs if npc.key == kwargs.get("key")), None
            )
        elif kwargs.get("name"):
            return next(
                (
                    npc
                    for npc in self.npcs
                    if npc.name.lower() == kwargs.get("name").lower()
                ),
                None,
            )

        return None
