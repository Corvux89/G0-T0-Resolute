from datetime import datetime, timezone

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import (TIMESTAMP, BigInteger, Column, Integer, String, and_,
                        null)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import CharacterSchema, PlayerCharacter, get_character_from_id
from Resolute.models.objects.ref_objects import NPC, NPCSchema, get_adventure_npcs_query


class Adventure(object):
    def __init__(self, db: aiopg.sa.Engine, guild_id: int, name: str, role_id: int, category_channel_id: int, **kwargs):
        self._db = db

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
        self.factions: list[Faction] = kwargs.get('factions', [])

        # Virtual attributes
        self.npcs: list[NPC] = []
        self.category_channel: discord.CategoryChannel = None
        self.role: discord.Role = None

    async def upsert(self):
        async with self._db.acquire() as conn:
            await conn.execute(upsert_adventure_query(self))

    async def update_dm_permissions(member: discord.Member, category_permissions: dict, role: discord):
        pass


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
    Column("characters", ARRAY(Integer), nullable=False),
    Column("factions", ARRAY(Integer), nullable=False)
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
    characters = fields.List(fields.Integer, required=False, allow_none=True, default=[])
    factions = fields.Method(None, "load_factions")

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    async def make_adventure(self, data, **kwargs):
        adventure = Adventure(self.bot.db, **data)
        await self.get_characters(adventure)
        await self.get_npcs(adventure)
        adventure.category_channel = self.bot.get_channel(adventure.category_channel_id)
        adventure.role = self.bot.get_role(adventure.role_id)
        return adventure

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    
    def load_factions(self, value):
        factions = []
        for f in value:
            factions.append(self.compendium.get_object(Faction, f))
        return factions
    
    async def get_characters(self, adventure: Adventure):
        if adventure.characters:
            for char_id in adventure.characters and (char := await self.bot.get_character(char_id)):
                adventure.player_characters.append(char)

    async def get_npcs(self, adventure: Adventure):
        async with self.bot.db.acquire() as conn:
            results = await conn.execute(get_adventure_npcs_query(adventure.id))
            rows = await results.fetchall()

        adventure.npcs = [NPCSchema(self.bot.db).load(row) for row in rows]

    

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
            "characters": adventure.characters,
            "factions": [f.id for f in adventure.factions]
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
        created_ts=adventure.created_ts,
        characters=adventure.characters,
        factions = [f.id for f in adventure.factions]
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