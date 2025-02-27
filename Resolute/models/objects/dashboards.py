from __future__ import annotations
from typing import TYPE_CHECKING

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY, insert

from Resolute.constants import ZWSP3
from Resolute.models import metadata
from Resolute.models.categories.categories import DashboardType
from Resolute.models.objects import RelatedList

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class RPDashboardCategory(object):
    """
    A class to represent a dashboard category in the RP system.
    Attributes
    ----------
    title : str
        The title of the dashboard category.
    name : str
        The name of the dashboard category.
    channels : list[TextChannel]
        A list of TextChannel objects associated with the dashboard category.
    Methods
    -------
    channel_output():
        Returns a string of mentions for the sorted channels in the category.
    """

    def __init__(self, **kwargs):
        self.title = kwargs.get("title")
        self.name = kwargs.get("name")
        self.channels: list[discord.TextChannel] = kwargs.get("channels", [])

    def channel_output(self) -> str:
        if self.channels:
            sorted_channels = [
                c for c in sorted(filter(None, self.channels), key=lambda c: c.position)
            ]

            return "\n".join([f"{c.mention}" for c in sorted_channels])

        return ZWSP3


class RefDashboard(object):
    """
    A class to represent a reference dashboard.
    Attributes:
    -----------
    _db : aiopg.sa.Engine
        The database engine.
    category_channel_id : int
        The ID of the category channel.
    channel_id : int
        The ID of the channel.
    post_id : int
        The ID of the post.
    excluded_channel_ids : list[int]
        A list of IDs of channels to be excluded.
    dashboard_type : DashboardType
        The type of the dashboard.
    channel : TextChannel
        The text channel associated with the dashboard.
    category_channel : CategoryChannel
        The category channel associated with the dashboard.
    Methods:
    --------
    channels_to_search() -> list[TextChannel]:
        Returns a list of text channels to search, excluding the ones in excluded_channel_ids.
    get_pinned_post() -> Message:
        Asynchronously fetches the pinned post message from the channel.
    upsert():
        Asynchronously inserts or updates the dashboard in the database.
    delete():
        Asynchronously deletes the dashboard from the database.
    """

    ref_dashboard_table = sa.Table(
        "ref_dashboards",
        metadata,
        sa.Column("post_id", sa.BigInteger, primary_key=True, nullable=False),
        sa.Column("category_channel_id", sa.BigInteger, nullable=True),
        sa.Column("channel_id", sa.BigInteger, nullable=False),
        sa.Column(
            "excluded_channel_ids", ARRAY(sa.BigInteger), nullable=True, default=[]
        ),
        sa.Column(
            "dashboard_type", sa.Integer, nullable=False
        ),  # ref: > c_dashboard_type.id
    )

    class RefDashboardSchema(Schema):
        bot: G0T0Bot = None
        category_channel_id = fields.Integer(required=False, allow_none=True)
        channel_id = fields.Integer(required=True)
        post_id = fields.Integer(required=True)
        excluded_channel_ids = fields.List(fields.Integer)
        dashboard_type = fields.Method(None, "get_dashboard_type")

        def __init__(self, bot: G0T0Bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        def make_dashboard(self, data, **kwargs) -> "RefDashboard":
            dashboard = RefDashboard(self.bot.db, **data)
            self.get_channels(dashboard)
            return dashboard

        def get_dashboard_type(self, value) -> DashboardType:
            return self.bot.compendium.get_object(DashboardType, value)

        def get_channels(self, dashboard: "RefDashboard"):
            dashboard.channel = self.bot.get_channel(dashboard.channel_id)
            dashboard.excluded_channels = RelatedList(
                dashboard,
                dashboard.update_channels,
                [self.bot.get_channel(c) for c in dashboard.excluded_channel_ids],
            )
            dashboard.category_channel = self.bot.get_channel(
                dashboard.category_channel_id
            )

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db

        self.category_channel_id = kwargs.get("category_channel_id")
        self.channel_id = kwargs.get("channel_id")
        self.post_id = kwargs.get("post_id")
        self.excluded_channel_ids: list[int] = kwargs.get("excluded_channel_ids", [])
        self.dashboard_type: DashboardType = kwargs.get("dashboard_type")
        self.channel: discord.TextChannel = kwargs.get("channel")
        self.category_channel: discord.CategoryChannel = kwargs.get("category_channel")

        self.excluded_channels: RelatedList[discord.TextChannel] = RelatedList(
            self, self.update_channels, kwargs.get("excluded_channels", [])
        )

    def update_channels(self):
        self.excluded_channel_ids = [c.id for c in self.excluded_channels]

    def channels_to_search(self) -> list[discord.TextChannel]:
        if self.category_channel:
            return list(
                filter(
                    lambda c: c.id not in self.excluded_channel_ids,
                    self.category_channel.text_channels,
                )
            )

        return []

    async def get_pinned_post(self) -> discord.Message:
        if self.channel:
            try:
                msg = await self.channel.fetch_message(self.post_id)
            except discord.HTTPException:
                return True
            except:
                return None

            return msg
        return None

    async def upsert(self) -> None:
        update_dict = {
            "category_channel_id": (
                self.category_channel.id
                if hasattr(self, "category_channel") and self.category_channel
                else self.category_channel_id
            ),
            "channel_id": (
                self.channel.id
                if hasattr(self, "channel") and self.channel
                else self.channel_id
            ),
            "post_id": self.post_id,
            "excluded_channel_ids": (
                [c.id for c in self.excluded_channels]
                if hasattr(self, "excluded_channels") and self.excluded_channels
                else self.excluded_channel_ids
            ),
            "dashboard_type": self.dashboard_type.id,
        }

        insert_dict = {**update_dict}

        query = insert(RefDashboard.ref_dashboard_table).values(**insert_dict)

        query = query.on_conflict_do_update(
            index_elements=["post_id"], set_=update_dict
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def delete(self) -> None:
        query = RefDashboard.ref_dashboard_table.delete().where(
            RefDashboard.ref_dashboard_table.c.post_id == self.post_id
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)


# PGSQL Views
class DashboardViews(object):
    class_census_table = sa.Table(
        "Class Census",
        metadata,
        sa.Column("Class", sa.String, nullable=False),
        sa.Column("#", sa.Integer, nullable=False),
    )

    level_distribution_table = sa.Table(
        "Level Distribution",
        metadata,
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("#", sa.Integer, nullable=False, default=0),
    )
