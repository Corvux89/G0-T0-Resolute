import calendar
from datetime import datetime, timezone
from io import BytesIO

import discord
import requests
from PIL import Image, ImageDraw, ImageFilter
from texttable import Texttable

from Resolute.bot import G0T0Bot
from Resolute.models.categories.categories import DashboardType
from Resolute.models.embeds.dashboards import RPDashboardEmbed
from Resolute.models.objects.dashboards import (
    DashboardViews,
    RefDashboard,
    RPDashboardCategory,
)
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.financial import Financial


async def get_last_message_in_channel(channel: discord.TextChannel) -> discord.Message:
    """
    Retrieve the last message in a given text channel.
    This function attempts to get the last message in the specified channel.
    It first checks if the channel's `last_message` attribute is set. If not,
    it tries to fetch the last message from the channel's history. If that
    also fails, it attempts to fetch the message using the channel's
    `last_message_id`. If all attempts fail, it returns None.
    Args:
        channel (TextChannel): The text channel from which to retrieve the last message.
    Returns:
        Message: The last message in the channel, or None if it cannot be retrieved.
    """
    if not (last_message := channel.last_message):
        try:
            last_message = next((msg for msg in channel.history(limit=1)), None)
        except:
            try:
                last_message = await channel.fetch_message(channel.last_message_id)
            except:
                return None

    return last_message


async def get_financial_dashboards(bot: G0T0Bot) -> list[RefDashboard]:
    """
    Retrieve financial dashboards from the database.
    This function fetches all dashboards of type "FINANCIAL" from the database
    and returns them as a list of RefDashboard objects.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection and compendium.
    Returns:
        list[RefDashboard]: A list of financial dashboards.
    """
    dashboards = []

    d_type = bot.compendium.get_object(DashboardType, "FINANCIAL")

    query = RefDashboard.ref_dashboard_table.select().where(
        RefDashboard.ref_dashboard_table.c.dashboard_type == d_type.id
    )

    rows = await bot.query(query, QueryResultType.multiple)

    dashboards = [RefDashboard.RefDashboardSchema(bot).load(row) for row in rows]

    # async with bot.db.acquire() as conn:
    #     async for row in conn.execute(get_dashboard_by_type(d_type.id)):
    #         dashboard: RefDashboard = RefDashboardSchema(bot).load(row)
    #         dashboards.append(dashboard)

    return dashboards


async def get_class_census_data(bot: G0T0Bot) -> []:
    """
    Fetches class census data from the database.
    Args:
        bot (G0T0Bot): An instance of the G0T0Bot which contains the database connection.
    Returns:
        list: A list of lists where each inner list contains the class name and its corresponding count.
    """
    census = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(DashboardViews.class_census_table.select()):
            result = dict(row)
            census.append([result["Class"], result["#"]])

    return census


async def get_level_distribution_data(bot: G0T0Bot) -> []:
    """
    Fetches level distribution data from the database.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection.
    Returns:
        list: A list of lists where each sublist contains the level and its corresponding count.
    """
    data = []
    async with bot.db.acquire() as conn:
        async for row in conn.execute(DashboardViews.level_distribution_table.select()):
            result = dict(row)
            data.append([result["level"], result["#"]])
    return data


async def update_financial_dashboards(bot: G0T0Bot) -> None:
    """
    Asynchronously updates financial dashboards.
    This function retrieves a list of financial dashboards and updates each one using the provided bot instance.
    Args:
        bot (G0T0Bot): An instance of the G0T0Bot used to interact with the dashboards.
    Returns:
        None
    """
    dashboards = await get_financial_dashboards(bot)

    for d in dashboards:
        await update_dashboard(bot, d)


async def update_dashboard(bot: G0T0Bot, dashboard: RefDashboard) -> None:
    """
    Asynchronously updates the specified dashboard based on its type.
    Parameters:
        bot (G0T0Bot): The bot instance.
        dashboard (RefDashboard): The dashboard to update.
    Returns:
        None
    The function handles different types of dashboards:
        - "RP": Updates the role-playing dashboard by categorizing channels based on their last message.
        - "CCENSUS": Updates the class census dashboard with the latest class distribution data.
        - "LDIST": Updates the level distribution dashboard with the latest level distribution data.
        - "FINANCIAL": Updates the financial dashboard with the latest financial progress and generates a progress bar image.
    The function also handles the deletion of the dashboard if the original message is not pinned or does not exist.
    """
    original_message = await dashboard.get_pinned_post()

    if isinstance(original_message, bool):
        return

    if not original_message or not original_message.pinned:
        return await dashboard.delete()

    guild = await bot.get_player_guild(original_message.guild.id)

    if dashboard.dashboard_type.value.upper() == "RP":
        channels = dashboard.channels_to_search()
        category = bot.get_channel(dashboard.category_channel_id)

        archivist_field = RPDashboardCategory(
            title="Archivist", name="<:pencil:989284061786808380> -- Awaiting Archivist"
        )
        available_field = RPDashboardCategory(
            title="Available",
            name="<:white_check_mark:983576747381518396> -- Available",
        )
        unavailable_field = RPDashboardCategory(
            title="Unvailable", name="<:x:983576786447245312> -- Unavailable"
        )

        all_fields = [archivist_field, available_field, unavailable_field]

        for c in channels:
            if last_message := await get_last_message_in_channel(c):
                if last_message.content in ["```\n​\n```", "```\n \n```"]:
                    available_field.channels.append(c)
                elif (
                    guild.staff_role
                    and guild.staff_role.mention in last_message.content
                ):
                    archivist_field.channels.append(c)
                else:
                    unavailable_field.channels.append(c)
            else:
                available_field.channels.append(c)

        all_fields = [f for f in all_fields if f.channels or f.title != "Archivist"]
        return await original_message.edit(
            content="", embed=RPDashboardEmbed(all_fields, category.name)
        )

    elif dashboard.dashboard_type.value.upper() == "CCENSUS":
        data = await get_class_census_data(bot)

        class_table = Texttable()
        class_table.set_cols_align(["l", "r"])
        class_table.set_cols_valign(["m", "m"])
        class_table.set_cols_width([15, 5])
        class_table.header(["Class", "#"])
        class_table.add_rows(data, header=False)

        footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

        return await original_message.edit(
            content=f"```\n{class_table.draw()}```{footer}", embed=None
        )

    elif dashboard.dashboard_type.value.upper() == "LDIST":
        data = await get_level_distribution_data(bot)

        dist_table = Texttable()
        dist_table.set_cols_align(["l", "r"])
        dist_table.set_cols_valign(["m", "m"])
        dist_table.set_cols_width([10, 5])
        dist_table.header(["Level", "#"])
        dist_table.add_rows(data, header=False)

        footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

        return await original_message.edit(
            content=f"```\n{dist_table.draw()}```{footer}", embed=None
        )

    elif dashboard.dashboard_type.value.upper() == "FINANCIAL":
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
