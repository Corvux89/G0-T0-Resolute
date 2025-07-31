import sqlalchemy as sa

from marshmallow import Schema, post_load, fields
from sqlalchemy import Column, Integer, String, BOOLEAN, Float

from Resolute.models import metadata


class CompendiumObject:
    __key__: str
    __table__: sa.Table
    __Schema__: Schema


class Rarity(CompendiumObject):
    __key__ = "rarity"

    __table__ = sa.Table(
        "c_rarity",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_rarity(self, data, **kwargs):
            return Rarity(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CharacterClass(CompendiumObject):
    __key__ = "character_class"

    __table__ = sa.Table(
        "c_character_class",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_character_class(self, data, **kwargs):
            return CharacterClass(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CharacterArchetype(CompendiumObject):
    __key__ = "archetype"

    __table__ = sa.Table(
        "c_character_archetype",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("parent", Integer, nullable=False),  # ref: > c_character_class.id
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
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


class CharacterSpecies(CompendiumObject):
    __key__ = "species"

    __table__ = sa.Table(
        "c_character_species",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_character_race(self, data, **kwargs):
            return CharacterSpecies(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ArenaTier(CompendiumObject):
    __key__ = "arena_tier"

    __table__ = sa.Table(
        "c_arena_tier",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("avg_level", Integer, nullable=False),
        Column("max_phases", Integer, nullable=False),
    )

    class __Schema__(Schema):
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


class Activity(CompendiumObject):
    __key__ = "activity"

    __table__ = sa.Table(
        "c_activity",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
        Column("cc", Integer, nullable=True),
        Column("diversion", BOOLEAN, nullable=False),
        Column("points", Integer, nullable=False),
        Column("credit_ratio", Float, nullable=True),
        Column("level_up_token", BOOLEAN, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)
        cc = fields.Integer(data_key="cc", required=False, allow_none=True)
        diversion = fields.Boolean(data_key="diversion", required=True)
        points = fields.Integer(data_key="points", required=False, allow_none=False)
        credit_ratio = fields.Float(
            data_key="credit_ratio", required=False, allow_none=True
        )
        level_up_token = fields.Boolean()

        @post_load
        def make_c_activity(self, data, **kwargs):
            return Activity(**data)

    def __init__(self, id, value, cc, diversion, points, credit_ratio, level_up_token):
        self.id = id
        self.value = value
        self.cc = cc
        self.diversion = diversion
        self.points = points
        self.credit_ratio = credit_ratio
        self.level_up_token = level_up_token


class DashboardType(CompendiumObject):
    __key__ = "dashboart_type"

    __table__ = sa.Table(
        "c_dashboard_type",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement="auto"),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_c_dashboard_type(self, data, **kwargs):
            return DashboardType(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class CodeConversion(CompendiumObject):
    __key__ = "cc_conversion"

    __table__ = sa.Table(
        "c_code_conversion",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", require=True)
        value = fields.Integer(data_key="value", required=True)

        @post_load
        def make_code_conversion(self, data, **kwargs):
            return CodeConversion(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ArenaType(CompendiumObject):
    __key__ = "arena_type"

    __table__ = sa.Table(
        "c_arena_type",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_arena_type(self, data, **kwargs):
            return ArenaType(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class TransactionType(CompendiumObject):
    __key__ = "transaction_type"

    __table__ = sa.Table(
        "c_transaction_type",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
        Column("currency", String, nullable=False),
    )

    class __Schema__(Schema):
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


class TransactionSubType(CompendiumObject):
    __key__ = "transaction_subtype"

    __table__ = sa.Table(
        "c_transaction_subtype",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent", Integer, nullable=False),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
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


class LevelCost(CompendiumObject):
    __key__ = "level_cost"

    __table__ = sa.Table(
        "c_level_costs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("cc", Integer, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        cc = fields.Integer(data_key="cc", required=True)

        @post_load
        def make_level_cost(self, data, **kwargs):
            return LevelCost(**data)

    def __init__(self, id, cc):
        self.id = id
        self.cc = cc


class Faction(CompendiumObject):
    __key__ = "faction"

    __table__ = sa.Table(
        "c_factions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", String, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        value = fields.String(data_key="value", required=True)

        @post_load
        def make_faction(self, data, **kwargs):
            return Faction(**data)

    def __init__(self, id, value):
        self.id = id
        self.value = value


class ActivityPoints(CompendiumObject):
    __key__ = "activity_points"

    __table__ = sa.Table(
        "c_activity_points",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("points", Integer, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        points = fields.Integer(data_key="points", required=True)

        @post_load
        def make_activity_points(self, data, **kwargs):
            return ActivityPoints(**data)

    def __init__(self, id, points):
        self.id = id
        self.points = points


class LevelTier(CompendiumObject):
    __key__ = "level_tier"

    __table__ = sa.Table(
        "c_level_tier",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("tier", Integer, nullable=False),
    )

    class __Schema__(Schema):
        id = fields.Integer(data_key="id", required=True)
        tier = fields.Integer(data_key="tier", required=True)

        @post_load
        def make_level_tier(self, data, **kwargs):
            return LevelTier(**data)

    def __init__(self, id, tier):
        self.id = id
        self.tier = tier


CATEGORY_LIST = [
    Rarity,
    CharacterClass,
    CharacterArchetype,
    CharacterSpecies,
    ArenaTier,
    Activity,
    DashboardType,
    CodeConversion,
    ArenaType,
    TransactionType,
    TransactionSubType,
    LevelCost,
    Faction,
    ActivityPoints,
    LevelTier,
]
