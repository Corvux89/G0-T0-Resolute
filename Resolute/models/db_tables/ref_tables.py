import sqlalchemy as sa
from sqlalchemy import Column, Integer, BigInteger, Numeric, String, BOOLEAN
from Resolute.models.db_tables.base import metadata

ref_category_dashboard_table = sa.Table(
    "ref_category_dashboard",
    metadata,
    Column("dashboard_post_id", BigInteger, primary_key=True, nullable=False),
    Column("category_channel_id", BigInteger, nullable=True),
    Column("dashboard_post_channel_id", BigInteger, nullable=False),
    Column("excluded_channel_ids", sa.ARRAY(BigInteger), nullable=True, default=[]),
    Column("dashboard_type", Integer, nullable=False)  # ref: > c_dashboard_type.id
)

ref_weekly_stipend_table = sa.Table(
    "ref_weekly_stipend",
    metadata,
    Column("role_id", BigInteger, primary_key=True, nullable=False),
    Column("guild_id", BigInteger, nullable=False),  # ref: > guilds.id
    Column("amount", Integer, nullable=False),
    Column("reason", String, nullable=True),
    Column("leadership", BOOLEAN, nullable=False, default=False)
)

ref_gb_staging_table = sa.Table(
    "ref_gb_staging",
    metadata,
    Column("guild_id", BigInteger, primary_key=True, nullable=False),  # ref: > guilds.id
    Column("name", String, nullable=False),
    Column("base_cc", Integer, nullable=False),
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[]),
)

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
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[])
)