import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import BOOLEAN, BigInteger, Column, Integer, String, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.selectable import FromClause, TableClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import PlayerCharacter


class Shatterpoint(object):
    def __init__(self, **kwargs):
        self.guild_id = kwargs.get('guild_id')
        self.name = kwargs.get('name', "New Shatterpoint")
        self.base_cc = kwargs.get('base_cc', 0)
        self.channels: list[int] = kwargs.get('channels', [])

        self.players: list[ShatterpointPlayer] = kwargs.get('players', [])
        self.renown: list[ShatterpointRenown] = kwargs.get('renown', [])
        

ref_gb_staging_table = sa.Table(
    "ref_gb_staging",
    metadata,
    Column("guild_id", BigInteger, primary_key=True, nullable=False),  # ref: > guilds.id
    Column("name", String, nullable=False),
    Column("base_cc", Integer, nullable=False),
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[]),
)

class ShatterPointSchema(Schema):
    guild_id = fields.Integer(required=True)
    name = fields.String(required=True)
    base_cc = fields.Integer(required=True)
    channels = fields.List(fields.Integer, load_default=[], required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @post_load
    def make_shatterpoint(self, data, **kwargs):
        return Shatterpoint(**data)

def upsert_shatterpoint_query(shatterpoint: Shatterpoint):
    insert_statement = insert(ref_gb_staging_table).values(
        guild_id=shatterpoint.guild_id,
        name=shatterpoint.name,
        base_cc=shatterpoint.base_cc,
        channels=shatterpoint.channels
    ).returning(ref_gb_staging_table)

    update_dict = {
        "name": shatterpoint.name,
        "base_cc": shatterpoint.base_cc,
        "channels": shatterpoint.channels
    }

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['guild_id'],
        set_=update_dict
    )

    return upsert_statement

def get_shatterpoint_query(guild_id: int) -> FromClause:
    return ref_gb_staging_table.select().where(
        ref_gb_staging_table.c.guild_id == guild_id
    )

def delete_shatterpoint_query(guild_id: int) -> TableClause:
    return ref_gb_staging_table.delete().where(ref_gb_staging_table.c.guild_id == guild_id)


class ShatterpointPlayer(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.guild_id = kwargs.get('guild_id')
        self.player_id = kwargs.get('player_id')
        self.cc = kwargs.get('cc')
        self.update = kwargs.get('update', True)
        self.active = kwargs.get('active', True)
        self.num_messages = kwargs.get('num_messages', 0)
        self.channels: list[int] = kwargs.get('channels', [])
        self.characters: list[int] = kwargs.get('characters', [])

        self.player_characters: list[PlayerCharacter] = []

ref_gb_staging_player_table = sa.Table(
    "ref_gb_staging_player",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("guild_id", BigInteger, nullable=False),  # ref: > ref_gb_staging.id
    Column("player_id", BigInteger, nullable=False),  # ref: > characters.player_id
    Column("cc", Integer, nullable=False),
    Column("update", BOOLEAN, nullable=False, default=True),
    Column("active", BOOLEAN, nullable=False, default=True),
    Column("num_messages", Integer, nullable=False, default=0),
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[]),
    Column("characters", sa.ARRAY(Integer), nullable=False, default=[])
)

class ShatterPointPlayerSchema(Schema):
    id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    player_id = fields.Integer(required=True)
    cc = fields.Integer(required=True)
    update = fields.Boolean(required=True)
    active = fields.Boolean(required=True)
    num_messages = fields.Integer(required=True)
    channels = fields.List(fields.Integer, load_default=[], required=False)
    characters = fields.List(fields.Integer, required=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @post_load
    def make_globEvent(self, data, **kwargs):
        return ShatterpointPlayer(**data)

def upsert_shatterpoint_player_query(spplayer: ShatterpointPlayer):
    if hasattr(spplayer, 'id') and spplayer.id is not None:
        update_dict = {
            "cc": spplayer.cc,
            "update": spplayer.update,
            "active": spplayer.active,
            "num_messages": spplayer.num_messages,
            "channels": spplayer.channels,
            "characters": spplayer.characters 
        }
        update_statement = ref_gb_staging_player_table.update().where(ref_gb_staging_player_table.c.id == spplayer.id).values(**update_dict).returning(ref_gb_staging_player_table)
        return update_statement
    
    return ref_gb_staging_player_table.insert().values(
        guild_id=spplayer.guild_id,
        player_id=spplayer.player_id,
        cc=spplayer.cc,
        update=spplayer.update,
        active=spplayer.active,
        num_messages=spplayer.num_messages,
        channels=spplayer.channels,
        characters=spplayer.characters
    ).returning(ref_gb_staging_player_table)

def get_all_shatterpoint_players_query(guild_id: int) -> FromClause:
    return ref_gb_staging_player_table.select().where(
        ref_gb_staging_player_table.c.guild_id == guild_id
    )

def delete_shatterpoint_players(guild_id: int) -> TableClause:
    return ref_gb_staging_player_table.delete().where(ref_gb_staging_player_table.c.guild_id == guild_id)

class ShatterpointRenown(object):
    def __init__(self, **kwargs):
        self.guild_id = kwargs.get('guild_id')
        self.faction: Faction = kwargs.get('faction')
        self.renown = kwargs.get('renown', 0)

ref_gb_renown_table = sa.Table(
    "ref_gb_renown",
    metadata,
    Column("guild_id", Integer, nullable=False),
    Column("faction", Integer, nullable=False),
    Column("renown", Integer, nullable=False, default=0),
    sa.PrimaryKeyConstraint("guild_id", "faction")
)

class RefRenownSchema(Schema):
    compendium: Compendium
    guild_id = fields.Integer(required=True)
    faction = fields.Method(None, "load_faction")
    renown = fields.Integer(required=True)

    def __init__(self, compendium: Compendium, **kwargs):
        self.compendium = compendium
        super().__init__(**kwargs)

    def load_faction(self, value):
        return self.compendium.get_object(Faction, value)

    @post_load
    def make_gbrenown(self, data, **kwargs):
        return ShatterpointRenown(**data)

def upsert_shatterpoint_renown_query(renown: ShatterpointRenown):
    insert_dict = {
        "guild_id": renown.guild_id,
        "faction": renown.faction.id,
        "renown": renown.renown
    }

    statement = insert(ref_gb_renown_table).values(insert_dict)

    statement = statement.on_conflict_do_update(
        index_elements=["guild_id", "faction"],
        set_={
            "renown": statement.excluded.renown
        }
    )

    return statement.returning(ref_gb_renown_table)

def get_shatterpoint_renown_query(guild_id: int) -> FromClause:
    return ref_gb_renown_table.select().where(
        ref_gb_renown_table.c.guild_id == guild_id
    )

def delete_specific_shatterpoint_renown_query(renown: ShatterpointRenown) -> TableClause:
    return ref_gb_renown_table.delete().where(
        and_(ref_gb_renown_table.c.guild_id == renown.guild_id, ref_gb_renown_table.c.faction == renown.faction.id)
    )

def delete_all_shatterpoint_renown_query(guild_id: int) -> TableClause:
    return ref_gb_renown_table.delete().where(
        ref_gb_renown_table.c.guild_id == guild_id
    )