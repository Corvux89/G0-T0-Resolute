from __future__ import annotations
import calendar
import datetime
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests
from PIL import Image, ImageDraw, ImageFilter
from texttable import Texttable
from io import BytesIO

import aiopg.sa
import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import ARRAY, insert

from Resolute.constants import CHANNEL_BREAK, ZWSP3
from Resolute.models import metadata
from Resolute.models.categories.categories import DashboardType
from Resolute.models.objects import RelatedList
from Resolute.helpers import get_last_message_in_channel
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.financial import Financial

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
        self.hide_if_empty: bool = kwargs.get("hide", False)

    def channel_output(self) -> str:
        if self.channels:
            sorted_channels = [
                c for c in sorted(filter(None, self.channels), key=lambda c: c.position)
            ]

            return "\n".join([f"{c.mention}" for c in sorted_channels])

        return ZWSP3

    def setup_channels(self, bot: G0T0Bot, embed: discord.Embed) -> None:

        def strip_field(str) -> int:
            if str.replace(" ", "") == ZWSP3.replace(" ", "") or str == "":
                return
            return int(str.replace("\u200b", "").replace("<#", "").replace(">", ""))

        if self.hide_if_empty:
            channels = [x.value if self.title in x.name else "" for x in embed.fields][
                0
            ].split("\n")
        else:
            channels = [x.value for x in embed.fields if self.title in x.name][0].split(
                "\n"
            )

        self.channels = [bot.get_channel(strip_field(x)) for x in channels if x != ""]


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

    async def refresh(self, bot: G0T0Bot, message: discord.Message = None) -> None:
        original_message = await self.get_pinned_post()

        if isinstance(original_message, bool):
            return

        if not original_message or not original_message.pinned:
            return await self.delete()

        guild = await bot.get_player_guild(original_message.guild.id)

        if self.dashboard_type.value.upper() == "RP":
            staff_name = guild.staff_role.name if guild.staff_role else "Archivist"
            staff_field = RPDashboardCategory(
                title=f"{staff_name}",
                name=f"<:pencil:989284061786808380> -- Awaiting {staff_name}",
                hide=True,
            )
            available_field = RPDashboardCategory(
                title="Available",
                name="<:white_check_mark:983576747381518396> -- Available",
            )
            unavailable_field = RPDashboardCategory(
                title="Unavailable", name="<:x:983576786447245312> -- Unavailable"
            )

            all_fields = [staff_field, available_field, unavailable_field]
            update = False

            if message:
                embed = original_message.embeds[0]

                staff_field.setup_channels(bot, embed)
                available_field.setup_channels(bot, embed)
                unavailable_field.setup_channels(bot, embed)

                node = ""

                for field in all_fields:
                    if message.channel in field.channels:
                        node = field.title
                        field.channels.remove(message.channel)

                if not message.content or message.content in [
                    CHANNEL_BREAK,
                    CHANNEL_BREAK.replace(" ", ""),
                ]:
                    available_field.channels.append(message.channel)
                    update = True if available_field.title != node else False
                elif guild.staff_role and guild.staff_role.mention in message.content:
                    staff_field.channels.append(message.channel)
                    update = True if staff_field.title != node else False
                else:
                    unavailable_field.channels.append(message.channel)
                    update = True if unavailable_field.title != node else False

            else:
                update = True
                for channel in self.channels_to_search():
                    if last_message := await get_last_message_in_channel(channel):
                        if last_message.content in [
                            CHANNEL_BREAK,
                            CHANNEL_BREAK.replace(" ", ""),
                        ]:
                            available_field.channels.append(channel)
                        elif (
                            guild.staff_role
                            and guild.staff_role.mention in last_message.content
                        ):
                            staff_field.channels.append(channel)
                        else:
                            unavailable_field.channels.append(channel)

            all_fields = [
                f for f in all_fields if len(f.channels) > 0 or f.hide_if_empty == False
            ]

            if update:
                embed = discord.Embed(
                    color=discord.Color.dark_gray(),
                    title=f"Channel Statuses - {self.category_channel.name}",
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text="Last Updated")

                for field in all_fields:
                    embed.add_field(
                        name=field.name, value=field.channel_output(), inline=False
                    )

                return await original_message.edit(content="", embed=embed)

        elif self.dashboard_type.value.upper() == "CCENSUS":
            census = []
            result = await bot.query(
                DashboardViews.class_census_table.select(), QueryResultType.multiple
            )

            for row in result:
                census.append([row["Class"], row["#"]])

            class_table = Texttable()
            class_table.set_cols_align(["l", "r"])
            class_table.set_cols_valign(["m", "m"])
            class_table.set_cols_width([15, 5])
            class_table.header(["Class", "#"])
            class_table.add_rows(census, header=False)

            footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

            return await original_message.edit(
                content=f"```\n{class_table.draw()}```{footer}", embed=None
            )

        elif self.dashboard_type.value.upper() == "LDIST":
            dist = []

            result = await bot.query(
                DashboardViews.level_distribution_table.select(),
                QueryResultType.multiple,
            )

            for row in result:
                dist.append([row["level"], row["#"]])

            dist_table = Texttable()
            dist_table.set_cols_align(["l", "r"])
            dist_table.set_cols_valign(["m", "m"])
            dist_table.set_cols_width([10, 5])
            dist_table.header(["Level", "#"])
            dist_table.add_rows(dist, header=False)

            footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

            return await original_message.edit(
                content=f"```\n{dist_table.draw()}```{footer}", embed=None
            )

        elif self.dashboard_type.value.upper() == "FINANCIAL":
            fin: Financial = await bot.get_financial_data()
            res = requests.get(
                "https://res.cloudinary.com/jerrick/image/upload/d_642250b563292b35f27461a7.png,f_jpg,fl_progressive,q_auto,w_1024/y3mdgvccfyvmemabidd0.jpg"
            )
            if res.status_code != 200:
                raise Exception("Failed to download image")

            background = Image.open(BytesIO(res.content)).convert("RGBA")
            background = background.resize((800, 400))

            background = Image.open(BytesIO(res.content)).convert("RGBA")
            background = background.resize((800, 400))

            # Progress bar properties
            bar_width = 700
            bar_height = 50
            bar_x = 50
            bar_y = 300
            corner_radius = 20
            shadow_offset = 10

            # Calculate progress
            progress = min(
                fin.adjusted_total / fin.monthly_goal, 1
            )  # Cap progress at 100% for the main bar

            shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)

            shadow_color = (0, 0, 0, 100)

            shadow_rect = [
                bar_x + shadow_offset,
                bar_y + shadow_offset,
                bar_x + bar_width + shadow_offset,
                bar_y + bar_height + shadow_offset,
            ]
            shadow_draw.rounded_rectangle(
                shadow_rect, fill=shadow_color, radius=corner_radius
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))

            background = Image.alpha_composite(background, shadow)

            draw = ImageDraw.Draw(background)

            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                fill="gray",
                outline="white",
                width=2,
                radius=corner_radius,
            )

            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + int(bar_width * progress), bar_y + bar_height],
                fill="green",
                radius=corner_radius,
            )

            image_buffer = BytesIO()
            background.save(image_buffer, format="PNG")
            image_buffer.seek(0)

            embed = discord.Embed(
                title="G0-T0 Financial Progress",
                description=f"Current Monthly Progress: ${fin.adjusted_total:.2f}\n"
                f"Monthly Goal: ${fin.monthly_goal:.2f}\n"
                f"Reserve: ${fin.reserve:.2f}",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="Stretch Goals",
                value="If we end up with enough reserve funds, we will look at making a website to house our content rulings / updates and work on better integrations with the bot.",
            )

            embed.set_image(url="attachment://progress.png")
            embed.set_footer(text="Last Updated")

            file = discord.File(image_buffer, filename="progress.png")
            original_message.attachments.clear()
            return await original_message.edit(file=file, embed=embed, content="")


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
