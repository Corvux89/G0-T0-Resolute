from discord import TextChannel
import sqlalchemy as sa
from sqlalchemy import Column, Integer, BigInteger, String
from Resolute.compendium import Compendium
from Resolute.models import metadata
from marshmallow import Schema, fields, post_load
from sqlalchemy import null, and_, or_
from sqlalchemy.sql.selectable import FromClause, TableClause
from sqlalchemy.dialects.postgresql import insert

from Resolute.models.categories.categories import DashboardType

class RPDashboardCategory(object):
    def __init__(self, **kwargs):
        self.title = kwargs.get('title')
        self.name = kwargs.get('name')
        self.channels: list[TextChannel] = kwargs.get('channels', [])

    def channel_output(self):
        if self.channels:
            sorted_channels = [c for c in sorted(filter(None, self.channels), key=lambda c: c.position)]

            return "\n".join([f"{c.mention}" for c in sorted_channels])
        
        return "\u200b"

class RefDashboard(object):
    def __init__(self, **kwargs):
        self.category_channel_id = kwargs.get('category_channel_id')
        self.channel_id = kwargs.get('channel_id')
        self.post_id = kwargs.get('post_id')
        self.excluded_channel_ids: list[int] = kwargs.get('excluded_channel_ids', [])
        self.dashboard_type: DashboardType = kwargs.get('dashboard_type')

ref_dashboard_table = sa.Table(
    "ref_dashboards",
    metadata,
    Column("post_id", BigInteger, primary_key=True, nullable=False),
    Column("category_channel_id", BigInteger, nullable=True),
    Column("channel_id", BigInteger, nullable=False),
    Column("excluded_channel_ids", sa.ARRAY(BigInteger), nullable=True, default=[]),
    Column("dashboard_type", Integer, nullable=False)  # ref: > c_dashboard_type.id
)

class RefDashboardSchema(Schema):
    compendium: Compendium
    category_channel_id = fields.Integer(required=True)
    channel_id = fields.Integer(required=True)
    post_id = fields.Integer(required=True)
    excluded_channel_ids = fields.List(fields.Integer)
    dashboard_type = fields.Method(None, "get_dashboard_type")

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_dashboard(self, data, **kwargs):
        return RefDashboard(**data)
    
    def get_dashboard_type(self, value):
        return self.compendium.get_object(DashboardType, value)
    
def get_dashboard_by_category_channel_query(category_channel_id: int) -> FromClause:
    return ref_dashboard_table.select().where(
        ref_dashboard_table.c.category_channel_id == category_channel_id
    )

def get_dashboard_by_post_id(post_id: int) -> FromClause:
    return ref_dashboard_table.select().where(
        ref_dashboard_table.c.post_id == post_id
    )

def upsert_dashboard_query(dashboard: RefDashboard):
    insert_statment = insert(ref_dashboard_table).values(
        category_channel_id=dashboard.category_channel_id,
        channel_id=dashboard.channel_id,
        post_id=dashboard.post_id,
        excluded_channel_ids=dashboard.excluded_channel_ids,
        dashboard_type=dashboard.dashboard_type.id
    ).returning(ref_dashboard_table)

    update_dict = {
        'category_channel_id': dashboard.category_channel_id,
        'channel_id': dashboard.channel_id,
        'post_id': dashboard.post_id,
        'excluded_channel_ids': dashboard.excluded_channel_ids,
        'dashboard_type': dashboard.dashboard_type.id
    }

    upsert_statement = insert_statment.on_conflict_do_update(
        index_elements=['post_id'],
        set_=update_dict
    )

    return upsert_statement

def get_dashboards() -> FromClause:
    return ref_dashboard_table.select()

def delete_dashboard_query(dashboard: RefDashboard) -> TableClause:
    return ref_dashboard_table.delete().where(
        ref_dashboard_table.c.post_id == dashboard.post_id
    )


# PGSQL Views
class_census_table = sa.Table(
    "Class Census",
    metadata,
    Column("Class", String, nullable=False),
    Column("#", Integer, nullable=False)
)

def get_class_census() -> FromClause:
    return class_census_table.select()


level_distribution_table = sa.Table(
    "Level Distribution",
    metadata,
    Column("level", Integer, nullable=False),
    Column("#", Integer, nullable=False, default=0)
)

def get_level_distribution() -> FromClause:
    return level_distribution_table.select()