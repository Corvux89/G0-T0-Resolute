import sqlalchemy as sa
from sqlalchemy import Column, Integer, String
from Resolute.models.db_tables.base import metadata

class_census_table = sa.Table(
    "Class Census",
    metadata,
    Column("Class", String, nullable=False),
    Column("#", Integer, nullable=False, default=0)
)

level_distribution_table = sa.Table(
    "Level Distribution",
    metadata,
    Column("level", Integer, nullable=False),
    Column("#", Integer, nullable=False, default=0)
)