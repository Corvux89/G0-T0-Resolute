import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Numeric, BOOLEAN, BigInteger
from Resolute.models.db_tables.base import metadata

c_rarity_table = sa.Table(
    "c_rarity",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)


c_character_class_table = sa.Table(
    "c_character_class",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

c_character_archetype_table = sa.Table(
    "c_character_archetype",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("parent", Integer, nullable=False),  # ref: > c_character_class.id
    Column("value", String, nullable=False)
)

c_character_species_table = sa.Table(
    "c_character_species",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

c_global_modifier_table = sa.Table(
    "c_global_modifier",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False),
    Column("adjustment", Numeric(precision=5, scale=2), nullable=False),
    Column("max", Integer, nullable=False)
)

c_host_status_table = sa.Table(
    "c_host_status",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False)
)

c_arena_tier_table = sa.Table(
    "c_arena_tier",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("avg_level", Integer, nullable=False),
    Column("max_phases", Integer, nullable=False)
)

c_adventure_tier_table = sa.Table(
    "c_adventure_tier",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("avg_level", Integer, nullable=False),
)

c_activity_table = sa.Table(
    "c_activity",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False),
    Column("cc",Integer, nullable=True),
    Column("diversion", BOOLEAN, nullable=False)
)

c_dashboard_type_table = sa.Table(
    "c_dashboard_type",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("value", String, nullable=False),
)

c_level_caps_table = sa.Table(
    "c_level_caps",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("max_cc", Integer, nullable=False),
    Column("max_items", String, nullable=False),
    Column("max_consumable", String, nullable=False)
)


c_adventure_rewards_table = sa.Table(
    "c_adventure_rewards",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ep", Integer, nullable=False),
    Column("tier", Integer, nullable=False),
    Column("rarity", Integer, nullable=True)  # ref: > c_rarity.id
)

c_code_conversion_table = sa.Table(
    "c_code_conversion",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("value", Integer, nullable=False)
)

