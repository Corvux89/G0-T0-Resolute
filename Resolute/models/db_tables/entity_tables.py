from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, Integer, BigInteger, String, BOOLEAN, DateTime, null, func
from Resolute.models.db_tables.base import metadata

arenas_table = sa.Table(
    "arenas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("channel_id", BigInteger, nullable=False),
    Column("pin_message_id", BigInteger, nullable=False),
    Column("role_id", BigInteger, nullable=False),
    Column("host_id", BigInteger, nullable=False),  # ref: > characters.player_id
    Column("tier", Integer, nullable=False, default=1),  # ref: > c_arena_tier.id
    Column("completed_phases", Integer, nullable=False, default=0),
    Column("created_ts", DateTime(timezone=False), nullable=False, default=datetime.utcnow),
    Column("end_ts", DateTime(timezone=False), nullable=True, default=null())
)

guilds_table = sa.Table(
    "guilds",
    metadata,
    Column("id", BigInteger, primary_key=True, nullable=False),
    Column("max_level", Integer, nullable=False, default=3),
    Column("weeks", Integer, nullable=False, default=0),
    Column("max_reroll", Integer, nullable=False, default=1),
    Column("reset_day", Integer, nullable=True),
    Column("reset_hour", Integer, nullable=True),
    Column("last_reset", DateTime(timezone=False), nullable=False, default=datetime.utcnow())
)

characters_table = sa.Table(
    "characters",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("name", String, nullable=False),
    Column("species", Integer, nullable=False),  # ref: > c_character_race.id
    Column("credits", Integer, nullable=False, default=0),
    Column("cc", Integer, nullable=False, default=0),
    Column("div_cc", Integer, nullable=False, default=0),
    Column("level", Integer, nullable=False, default=1),
    Column("token", Integer, nullable=False, default=0),
    Column("player_id", BigInteger, nullable=False),
    Column("guild_id", BigInteger, nullable=False),  # ref: > guilds.id
    Column("reroll", BOOLEAN, nullable=True),
    Column("active", BOOLEAN, nullable=False, default=True)
)

character_class_table = sa.Table(
    "character_class",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("character_id", Integer, nullable=False),  # ref: > characters.id
    Column("primary_class", Integer, nullable=False),  # ref: > c_character_class.id
    Column("archetype", Integer, nullable=True),  # ref: > c_character_subclass.id
    Column("active", BOOLEAN, nullable=False, default=True)
)

log_table = sa.Table(
    "log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("author", BigInteger, nullable=False),
    Column("cc", Integer, nullable=True),
    Column("credits", Integer, nullable=True),
    Column("token", Integer, nullable=True),
    Column("created_ts", DateTime(timezone=False), nullable=False, default=datetime.utcnow),
    Column("character_id", Integer, nullable=False),  # ref: > characters.id
    Column("activity", Integer, nullable=False),  # ref: > c_activity.id
    Column("notes", String, nullable=True),
    Column("adventure_id", Integer, nullable=True),  # ref: > adventures.id
    Column("invalid", BOOLEAN, nullable=False, default=False)
)

adventures_table = sa.Table(
    "adventures",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("guild_id", BigInteger, nullable=False),
    Column("name", String, nullable=False),
    Column("role_id", BigInteger, nullable=False),
    Column("dms", sa.ARRAY(BigInteger), nullable=False),  # ref: <> characters.player_id
    Column("category_channel_id", BigInteger, nullable=False),
    Column("cc", Integer, nullable=False, default=0),
    Column("created_ts", DateTime(timezone=False), nullable=False, default=datetime.utcnow),
    Column("end_ts", DateTime(timezone=False), nullable=True),
)

character_starship_table = sa.Table(
    "character_starship",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("character_id", BigInteger, nullable=False),
    Column("name", String, nullable=False),
    Column("transponder", String, nullable=True),
    Column("starship", Integer, nullable=False),
    Column("tier", Integer, nullable=True),
    Column("active", BOOLEAN, nullable=False, default=True)
)