import sqlalchemy as sa

from marshmallow import Schema, post_load, fields
from sqlalchemy import Column, Integer, String, BOOLEAN

from Resolute.models import metadata


class CompendiumObject:
    def __init__(self, key: str, obj, table: sa.Table, schema: Schema) -> None:
        self.key = key
        self.obj = obj
        self.table = table
        self.schema = schema


class Rarity(object):
    c_rarity_table = sa.Table(
        "c_rarity",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class RaritySchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_rarity(self, data, **kwargs):
            return Rarity(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CharacterClass(object):
    c_character_class_table = sa.Table(
        "c_character_class",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class CharacterClassSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_character_class(self, data, **kwargs):
            return CharacterClass(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CharacterArchetype(object):
    c_character_archetype_table = sa.Table(
        "c_character_archetype",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("parent", Integer, nullable=False),  # ref: > c_character_class.id
        Column("value", String, nullable=False),
    )

    class CharacterArchetypeSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        parent = fields.Integer(data_key="parent", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_character_subclass(self, data, **kwargs):
            return CharacterArchetype(**data)

    def __init__(self, id, parent, value):
        self.id = id
        self.parent = parent
        self.value = value


class CharacterSpecies(object):
    c_character_species_table = sa.Table(
        "c_character_species",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class CharacterSpeciesSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_character_race(self, data, **kwargs):
            return CharacterSpecies(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ArenaTier(object):
    c_arena_tier_table = sa.Table(
        "c_arena_tier",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("avg_level", Integer, nullable=False),
        Column("max_phases", Integer, nullable=False),
    )

    class ArenaTierSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        avg_level = fields.Integer(data_key="avg_level", required=True)
        max_phases = fields.Integer(data_key="max_phases", required=True)

        @post_load
        def make_c_arena_tier(self, data, **kwargs):
            return ArenaTier(**data)

    def __init__(self, id, avg_level, max_phases):
        self.id = id
        self.avg_level = avg_level
        self.max_phases = max_phases


class Activity(object):
    c_activity_table = sa.Table(
        "c_activity",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
        Column("cc", Integer, nullable=True),
        Column("diversion", BOOLEAN, nullable=False),
        Column("points", Integer, nullable=False),
    )

    class ActivitySchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)
        cc = fields.Integer(data_key="cc", required=False, allow_none=True)
        diversion = fields.Boolean(data_key="diversion", required=True)
        points = fields.Integer(data_key="points", required=False, allow_none=False)

        @post_load
        def make_c_activity(self, data, **kwargs):
            return Activity(**data)

    def __init__(self, id, value, cc, diversion, points):
        self.id = id
        self.value = value
        self.cc = cc
        self.diversion = diversion
        self.points = points


class DashboardType(object):
    c_dashboard_type_table = sa.Table(
        "c_dashboard_type",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class DashboardTypeSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_dashboard_type(self, data, **kwargs):
            return DashboardType(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CodeConversion(object):
    c_code_conversion_table = sa.Table(
        "c_code_conversion",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )

    class CodeConversionSchema(Schema):
        id = fields.Integer(data_key="id", require=True)
        value = fields.Integer(data_key="value", required=True)

        @post_load
        def make_code_conversion(self, data, **kwargs):
            return CodeConversion(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ArenaType(object):
    c_arena_type_table = sa.Table(
        "c_arena_type",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
    )

    class ArenaTypeSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_arena_type(self, data, **kwargs):
            return ArenaType(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class TransactionType(object):
    c_transaction_type_table = sa.Table(
        "c_transaction_type",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
        Column("currency", String, nullable=False),
    )

    class TransactionTypeSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)
        currency = fields.String(data_key="currency", required=True)

        @post_load
        def make_transaction_type(self, data, **kwargs):
            return TransactionType(**data)

    def __init__(self, id, value, currency):
        self.id = id
        self.value = value
        self.currency = currency


class TransactionSubType(object):
    c_transaction_subtype_table = sa.Table(
        "c_transaction_subtype",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent", Integer, nullable=False),
        Column("value", String, nullable=False),
    )

    class TransactionSubTypeSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)
        parent = fields.Integer(data_key="parent", required=True)

        @post_load
        def make_transaction_subtype(self, data, **kwargs):
            return TransactionSubType(**data)

    def __init__(self, id, value, parent):
        self.id = id
        self.parent = parent
        self.value = value


class LevelCost(object):
    c_level_cost_table = sa.Table(
        "c_level_costs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("cc", Integer, nullable=False),
    )

    class LevelCostSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        cc = fields.Integer(data_key="cc", required=True)

        @post_load
        def make_level_cost(self, data, **kwargs):
            return LevelCost(**data)

    def __init__(self, id, cc):
        self.id = id
        self.cc = cc


class Faction(object):
    c_factions = sa.Table(
        "c_factions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
    )

    class FactionSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_faction(self, data, **kwargs):
            return Faction(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ActivityPoints(object):
    c_activity_points = sa.Table(
        "c_activity_points",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("points", Integer, nullable=False),
    )

    class ActivityPointsSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        points = fields.Integer(data_key="points", required=True)

        @post_load
        def make_activity_points(self, data, **kwargs):
            return ActivityPoints(**data)

    def __init__(self, id, points):
        self.id = id
        self.points = points


class LevelTier(object):
    c_level_tier = sa.Table(
        "c_level_tier",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("tier", Integer, nullable=False),
    )

    class LevelTierSchema(Schema):
        id = fields.Integer(data_key="id", required=True)
        tier = fields.Integer(data_key="tier", required=True)

        @post_load
        def make_level_tier(self, data, **kwargs):
            return LevelTier(**data)

    def __init__(self, id, tier):
        self.id = id
        self.tier = tier


CATEGORY_LIST = [
    CompendiumObject("rarity", Rarity, Rarity.c_rarity_table, Rarity.RaritySchema),
    CompendiumObject(
        "character_class",
        CharacterClass,
        CharacterClass.c_character_class_table,
        CharacterClass.CharacterClassSchema,
    ),
    CompendiumObject(
        "archetype",
        CharacterArchetype,
        CharacterArchetype.c_character_archetype_table,
        CharacterArchetype.CharacterArchetypeSchema,
    ),
    CompendiumObject(
        "species",
        CharacterSpecies,
        CharacterSpecies.c_character_species_table,
        CharacterSpecies.CharacterSpeciesSchema,
    ),
    CompendiumObject(
        "arena_tier", ArenaTier, ArenaTier.c_arena_tier_table, ArenaTier.ArenaTierSchema
    ),
    CompendiumObject(
        "activity", Activity, Activity.c_activity_table, Activity.ActivitySchema
    ),
    CompendiumObject(
        "dashboard_type",
        DashboardType,
        DashboardType.c_dashboard_type_table,
        DashboardType.DashboardTypeSchema,
    ),
    CompendiumObject(
        "cc_conversion",
        CodeConversion,
        CodeConversion.c_code_conversion_table,
        CodeConversion.CodeConversionSchema,
    ),
    CompendiumObject(
        "arena_type", ArenaType, ArenaType.c_arena_type_table, ArenaType.ArenaTypeSchema
    ),
    CompendiumObject(
        "transaction_type",
        TransactionType,
        TransactionType.c_transaction_type_table,
        TransactionType.TransactionTypeSchema,
    ),
    CompendiumObject(
        "transaction_subtype",
        TransactionSubType,
        TransactionSubType.c_transaction_subtype_table,
        TransactionSubType.TransactionSubTypeSchema,
    ),
    CompendiumObject(
        "level_cost", LevelCost, LevelCost.c_level_cost_table, LevelCost.LevelCostSchema
    ),
    CompendiumObject("faction", Faction, Faction.c_factions, Faction.FactionSchema),
    CompendiumObject(
        "activity_points",
        ActivityPoints,
        ActivityPoints.c_activity_points,
        ActivityPoints.ActivityPointsSchema,
    ),
    CompendiumObject(
        "level_tier", LevelTier, LevelTier.c_level_tier, LevelTier.LevelTierSchema
    ),
]
