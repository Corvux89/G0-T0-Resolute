import sqlalchemy as sa

from marshmallow import Schema, post_load, fields
from sqlalchemy import Column, Integer, String, BOOLEAN
from sqlalchemy.sql.selectable import FromClause

from Resolute.models import metadata

def get_category_table(table: sa.Table) -> FromClause:
    return table.select()

class CompendiumObject:
    def __init__(self, key:str, obj,  table: sa.Table, schema: Schema) -> None:
        self.key = key
        self.obj = obj
        self.table = table
        self.schema = schema

# Rarity
c_rarity_table = sa.Table(
    "c_rarity",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

class Rarity(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class RaritySchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_rarity(self, data, **kwargs):
        return Rarity(**data)
    
rarity = CompendiumObject("rarity", Rarity, c_rarity_table, RaritySchema)

# Character Class
c_character_class_table = sa.Table(
    "c_character_class",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

class CharacterClass(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class CharacterClassSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_class(self, data, **kwargs):
        return CharacterClass(**data)
    
char_class = CompendiumObject("character_class", CharacterClass, c_character_class_table, CharacterClassSchema)
    
# Character Archetypes    
c_character_archetype_table = sa.Table(
    "c_character_archetype",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("parent", Integer, nullable=False),  # ref: > c_character_class.id
    Column("value", String, nullable=False)
)

class CharacterArchetype(object):
    def __init__(self, id, parent, value):
        self.id = id
        self.parent = parent
        self.value = value

class CharacterArchetypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    parent = fields.Integer(data_key="parent", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_subclass(self, data, **kwargs):
        return CharacterArchetype(**data)

char_archetype = CompendiumObject("archetype", CharacterArchetype, c_character_archetype_table, CharacterArchetypeSchema)

# Character Species
c_character_species_table = sa.Table(
    "c_character_species",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

class CharacterSpecies(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class CharacterSpeciesSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_race(self, data, **kwargs):
        return CharacterSpecies(**data)

char_species = CompendiumObject("species", CharacterSpecies, c_character_species_table, CharacterSpeciesSchema)

# Arena Tier
c_arena_tier_table = sa.Table(
    "c_arena_tier",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("avg_level", Integer, nullable=False),
    Column("max_phases", Integer, nullable=False)
)

class ArenaTier(object):
    def __init__(self, id, avg_level, max_phases):
        self.id = id
        self.avg_level = avg_level
        self.max_phases = max_phases

class ArenaTierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    avg_level = fields.Integer(data_key="avg_level", required=True)
    max_phases = fields.Integer(data_key="max_phases", required=True)

    @post_load
    def make_c_arena_tier(self, data, **kwargs):
        return ArenaTier(**data)

arena_tier = CompendiumObject("arena_tier", ArenaTier, c_arena_tier_table, ArenaTierSchema)

# Activity
c_activity_table = sa.Table(
    "c_activity",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False),
    Column("cc",Integer, nullable=True),
    Column("diversion", BOOLEAN, nullable=False),
    Column("points", Integer, nullable=False)
)

class Activity(object):
    def __init__(self, id, value, cc, diversion, points):
        self.id = id
        self.value = value
        self.cc = cc
        self.diversion = diversion
        self.points = points

class ActivitySchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    cc = fields.Integer(data_key="cc", required=False, allow_none=True)
    diversion = fields.Boolean(data_key="diversion", required=True)
    points = fields.Integer(data_key="points", required=False, allow_none=False)

    @post_load
    def make_c_activity(self, data, **kwargs):
        return Activity(**data)

activity = CompendiumObject("activity", Activity, c_activity_table, ActivitySchema)

# Dashboard Type
c_dashboard_type_table = sa.Table(
    "c_dashboard_type",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False),
)

class DashboardType(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class DashboardTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_dashboard_type(self, data, **kwargs):
        return DashboardType(**data)

dashboard_type = CompendiumObject("dashboard_type", DashboardType, c_dashboard_type_table, DashboardTypeSchema)

# Code Conversion
c_code_conversion_table = sa.Table(
    "c_code_conversion",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("value", Integer, nullable=False)
)

class CodeConversion(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class CodeConversionSchema(Schema):
    id = fields.Integer(data_key="id", require=True)
    value = fields.Integer(data_key="value", required=True)

    @post_load
    def make_code_conversion(self, data, **kwargs):
        return CodeConversion(**data)

cc_conversion = CompendiumObject("cc_conversion", CodeConversion, c_code_conversion_table, CodeConversionSchema)

# Arena Type
c_arena_type_table = sa.Table(
    "c_arena_type",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("value", String, nullable=False)
)

class ArenaType(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class ArenaTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_arena_type(self, data, **kwargs):
        return ArenaType(**data)

arena_type = CompendiumObject("arena_type", ArenaType, c_arena_type_table, ArenaTypeSchema)

# Transaction Type
c_transaction_type_table = sa.Table(
    "c_transaction_type",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("value", String, nullable=False),
    Column("currency", String, nullable=False)
)

class TransactionType(object):
    def __init__(self, id, value, currency):
        self.id = id
        self.value = value
        self.currency = currency

class TransactionTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    currency = fields.String(data_key="currency", required=True)

    @post_load
    def make_transaction_type(self, data, **kwargs):
        return TransactionType(**data)
    
transaction_type = CompendiumObject("transaction_type", TransactionType, c_transaction_type_table, TransactionTypeSchema)

# Transaction Subtype
c_transaction_subtype_table = sa.Table(
    "c_transaction_subtype",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("parent", Integer, nullable=False),
    Column("value", String, nullable=False)
)

class TransactionSubType(object):
    def __init__(self, id, value, parent):
        self.id = id
        self.parent = parent
        self.value = value

class TransactionSubTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    parent = fields.Integer(data_key="parent", required=True)

    @post_load
    def make_transaction_subtype(self, data, **kwargs):
        return TransactionSubType(**data)
    
transaction_subtype = CompendiumObject("transaction_subtype", TransactionSubType, c_transaction_subtype_table, TransactionSubTypeSchema)

# Level Costs
c_level_cost_table = sa.Table(
    "c_level_costs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("cc", Integer, nullable=False)
)

class LevelCost(object):
    def __init__(self, id, cc):
        self.id = id
        self.cc = cc

class LevelCostSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    cc = fields.Integer(data_key="cc", required=True)

    @post_load
    def make_level_cost(self, data, **kwargs):
        return LevelCost(**data)
    
level_cost = CompendiumObject("level_cost", LevelCost, c_level_cost_table, LevelCostSchema)

# Factions
c_factions = sa.Table(
    "c_factions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("value", String, nullable=False)
)

class Faction(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class FactionSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_faction(self, data, **kwargs):
        return Faction(**data)
    
faction = CompendiumObject("faction", Faction, c_factions, FactionSchema)

# Activity Points
c_activity_points = sa.Table(
    "c_activity_points",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("points", Integer, nullable=False)
)

class ActivityPoints(object):
    def __init__(self, id, points):
        self.id = id
        self.points = points

class ActivityPointsSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    points = fields.Integer(data_key="points", required=True)

    @post_load
    def make_activity_points(self, data, **kwargs):
        return ActivityPoints(**data)
    
activity_points = CompendiumObject("activity_points", ActivityPoints, c_activity_points, ActivityPointsSchema)

# Level Tiers
c_level_tier = sa.Table(
    "c_level_tier",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("tier", Integer, nullable=False)
)

class LevelTier(object):
    def __init__(self, id, tier):
        self.id = id
        self.tier = tier

class LevelTierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    tier = fields.Integer(data_key="tier", required=True)

    @post_load
    def make_level_tier(self, data, **kwargs):
        return LevelTier(**data)
    
level_tier = CompendiumObject("level_tier", LevelTier, c_level_tier, LevelTierSchema)
