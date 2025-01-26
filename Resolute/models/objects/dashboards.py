import sqlalchemy as sa
import aiopg.sa
from discord import CategoryChannel, HTTPException, TextChannel, Message
from marshmallow import Schema, fields, post_load
from sqlalchemy import BigInteger, Column, Integer, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.selectable import FromClause, TableClause
from Resolute.constants import ZWSP3
from Resolute.models import metadata
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
        
        return ZWSP3

class RefDashboard(object):
    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db

        self.category_channel_id = kwargs.get('category_channel_id')
        self.channel_id = kwargs.get('channel_id')
        self.post_id = kwargs.get('post_id')
        self.excluded_channel_ids: list[int] = kwargs.get('excluded_channel_ids', [])
        self.dashboard_type: DashboardType = kwargs.get('dashboard_type')
        self.channel: TextChannel = kwargs.get('channel')
        self.category_channel: CategoryChannel = kwargs.get('category_channel')
        
    def channels_to_search(self) -> list[TextChannel]:
        if self.category_channel:
            return list(filter(lambda c: c.id not in self.excluded_channel_ids, self.category_channel.text_channels))
        
        return []
    
    async def get_pinned_post(self) -> Message:
        if self.channel:
            try:
                msg = await self.channel.fetch_message(self.post_id)
            except HTTPException:
                return True
            except:
                return None
            
            return msg
        return None

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
    bot = None
    category_channel_id = fields.Integer(required=False, allow_none=True)
    channel_id = fields.Integer(required=True)
    post_id = fields.Integer(required=True)
    excluded_channel_ids = fields.List(fields.Integer)
    dashboard_type = fields.Method(None, "get_dashboard_type")

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    def make_dashboard(self, data, **kwargs):
        dashboard = RefDashboard(self.bot.db, **data)
        self.get_channels(dashboard)
        return dashboard
    
    def get_dashboard_type(self, value):
        return self.bot.compendium.get_object(DashboardType, value)
    
    def get_channels(self, dashboard: RefDashboard):
        dashboard.channel = self.bot.get_channel(dashboard.channel_id)
        dashboard.category_channel = self.bot.get_channel(dashboard.category_channel_id)

    
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

def get_dashboard_by_type(type: int) -> FromClause:
    return ref_dashboard_table.select().where(ref_dashboard_table.c.dashboard_type == type)

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