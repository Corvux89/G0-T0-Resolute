from datetime import datetime, timezone

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import FromClause

from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.npc import NPC, NPCSchema, get_adventure_npcs_query


class Adventure(object):
    """
    A class to represent an adventure in a guild.
    Attributes:
    -----------
    id : int
        The unique identifier of the adventure.
    guild_id : int
        The unique identifier of the guild.
    name : str
        The name of the adventure.
    role_id : int
        The unique identifier of the role associated with the adventure.
    category_channel_id : int
        The unique identifier of the category channel associated with the adventure.
    dms : list[int]
        A list of IDs of the dungeon masters for the adventure.
    characters : list[int]
        A list of IDs of the characters in the adventure.
    cc : Any
        Custom attribute, purpose unspecified.
    player_characters : list[PlayerCharacter]
        A list of player characters in the adventure.
    created_ts : datetime
        The timestamp when the adventure was created.
    end_ts : datetime
        The timestamp when the adventure ended.
    factions : list[Faction]
        A list of factions involved in the adventure.
    npcs : list[NPC]
        A list of non-player characters in the adventure.
    category_channel : CategoryChannel
        The Discord category channel associated with the adventure.
    role : Role
        The Discord role associated with the adventure.
    Methods:
    --------
    __init__(self, db: aiopg.sa.Engine, guild_id: int, name: str, role_id: int, category_channel_id: int, **kwargs):
        Constructs all the necessary attributes for the adventure object.
    async upsert(self):
        Inserts or updates the adventure in the database.
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
        bot = None

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

        def __init__(self, bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        async def make_adventure(self, data, **kwargs):
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

        def load_factions(self, value):
            factions = []
            for f in value:
                factions.append(self.bot.compendium.get_object(Faction, f))
            return factions

        async def get_characters(self, adventure):
            if adventure.characters:
                for char_id in adventure.characters:
                    if char := await self.bot.get_character(char_id):
                        adventure.player_characters.append(char)

        async def get_npcs(self, adventure):
            async with self.bot.db.acquire() as conn:
                results = await conn.execute(get_adventure_npcs_query(adventure.id))
                rows = await results.fetchall()

            adventure.npcs = [NPCSchema(self.bot.db).load(row) for row in rows]

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
        self.category_channel: discord.CategoryChannel = category_channel
        self.role: discord.Role = role
        self.role_id = role.id
        self.category_channel_id = category_channel.id
        self.dms: list[int] = kwargs.get("dms", [])
        self.characters: list[int] = kwargs.get("characters", [])
        self.cc = kwargs.get("cc", 0)
        self.player_characters: list[PlayerCharacter] = []
        self.created_ts = kwargs.get("created_ts", datetime.now(timezone.utc))
        self.end_ts = kwargs.get("end_ts")
        self.factions: list[Faction] = kwargs.get("factions", [])

        # Virtual attributes
        self.npcs: list[NPC] = []

    async def upsert(self):
        """
        Asynchronously upserts an adventure record in the database.
        This method acquires a connection from the database pool and executes
        an upsert query to insert or update the adventure record.
        Returns:
            None
        """
        if hasattr(self, "id") and self.id is not None:
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

            query = (
                self.adventures_table.update()
                .where(self.adventures_table.c.id == self.id)
                .values(**update_dict)
                .returning(self.adventures_table)
            )
        else:
            query = (
                self.adventures_table.insert()
                .values(
                    guild_id=self.guild_id,
                    name=self.name,
                    role_id=self.role_id,
                    dms=self.dms,
                    category_channel_id=self.category_channel_id,
                    cc=self.cc,
                    created_ts=self.created_ts,
                    characters=self.characters,
                    factions=[f.id for f in self.factions],
                )
                .returning(self.adventures_table)
            )

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

    @staticmethod
    def get_character_adventures_query(char_id: int) -> FromClause:
        return (
            Adventure.adventures_table.select()
            .where(
                sa.and_(
                    Adventure.adventures_table.c.characters.contains([char_id]),
                    Adventure.adventures_table.c.end_ts == sa.null(),
                )
            )
            .order_by(Adventure.adventures_table.c.id.asc())
        )

    def get_adventures_by_dm_query(member_id: int) -> FromClause:
        return (
            Adventure.adventures_table.select()
            .where(
                sa.and_(
                    Adventure.adventures_table.c.dms.contains([member_id]),
                    Adventure.adventures_table.c.end_ts == sa.null(),
                )
            )
            .order_by(Adventure.adventures_table.c.id.asc())
        )

    def get_adventure_by_role_query(role_id: int) -> FromClause:
        return Adventure.adventures_table.select().where(
            sa.and_(
                Adventure.adventures_table.c.role_id == role_id,
                Adventure.adventures_table.c.end_ts == sa.null(),
            )
        )

    def get_adventure_by_category_channel_query(category_channel_id: int) -> FromClause:
        return Adventure.adventures_table.select().where(
            sa.and_(
                Adventure.adventures_table.c.category_channel_id == category_channel_id,
                Adventure.adventures_table.c.end_ts == sa.null(),
            )
        )
