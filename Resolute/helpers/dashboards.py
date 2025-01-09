import calendar
from datetime import datetime, timezone
from io import BytesIO

import discord
import requests
from texttable import Texttable

from Resolute.bot import G0T0Bot
from Resolute.helpers import get_guild
from Resolute.helpers.financial import get_financial_data
from Resolute.models.categories.categories import DashboardType
from Resolute.models.embeds.dashboards import RPDashboardEmbed
from Resolute.models.objects.dashboards import (
    RefDashboard, RefDashboardSchema, RPDashboardCategory,
    delete_dashboard_query, get_class_census,
    get_dashboard_by_category_channel_query, get_dashboard_by_post_id, get_dashboard_by_type,
    get_dashboards, get_level_distribution, upsert_dashboard_query)
from Resolute.models.objects.financial import Financial
from PIL import Image, ImageDraw, ImageFilter


async def get_pinned_post(bot: G0T0Bot, dashboard: RefDashboard) -> discord.Message:
    if channel := bot.get_channel(dashboard.channel_id):
        try:
            msg = await channel.fetch_message(dashboard.post_id)
        except discord.HTTPException:
            return True
        except:
            return None
        
        return msg
    return None

def get_dashboard_channels(bot: G0T0Bot, dashboard: RefDashboard) -> list[discord.TextChannel]:
    if category := bot.get_channel(dashboard.category_channel_id):
        return list(filter(lambda c: c.id not in dashboard.excluded_channel_ids, category.text_channels))
    return []

async def get_dashboard_from_category(bot: G0T0Bot, category_id: int) -> RefDashboard:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_dashboard_by_category_channel_query(category_id))
        row = await results.first()

    if row is None:
        return None
    
    d = RefDashboardSchema(bot.compendium).load(row)

    return d

async def get_dashboard_from_post(bot: G0T0Bot, post_id: int) -> RefDashboard:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_dashboard_by_post_id(post_id))
        row = await results.first()

    if row is None:
        return None
    
    d = RefDashboardSchema(bot.compendium).load(row)

    return d

async def upsert_dashboard(bot: G0T0Bot, dashboard: RefDashboard) -> RefDashboard:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_dashboard_query(dashboard))
        row = await results.first()

    if row is None:
        return None

    d = RefDashboardSchema(bot.compendium).load(row)

    return d

async def delete_dashboard(bot: G0T0Bot, dashboard: RefDashboard) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(delete_dashboard_query(dashboard))


async def get_last_message(channel: discord.TextChannel) -> discord.Message:
    if not (last_message := channel.last_message):
        try:
            last_message = next((msg for msg in channel.history(limit=1)), None)
        except:
            try:
                last_message = await channel.fetch_message(channel.last_message_id)
            except:
                return None
            
    return last_message

async def get_guild_dashboards(bot: G0T0Bot, guild_id: int) -> list[RefDashboard]:
    dashboards = []
    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_dashboards()):
            dashboard: RefDashboard = RefDashboardSchema(bot.compendium).load(row)
            if bot.get_channel(dashboard.channel_id).guild.id == guild_id:
                dashboards.append(dashboard)

    return dashboards

async def get_financial_dashboards(bot: G0T0Bot) -> list[RefDashboard]:
    dashboards = []

    d_type = bot.compendium.get_object(DashboardType, "FINANCIAL")

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_dashboard_by_type(d_type.id)):
            dashboard: RefDashboard = RefDashboardSchema(bot.compendium).load(row)
            dashboards.append(dashboard)

    return dashboards

async def get_class_census_data(bot: G0T0Bot) -> []:
    census = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_class_census()):
            result = dict(row)
            census.append([result['Class'], result['#']])
    
    return census

async def get_level_distribution_data(bot: G0T0Bot) -> []:
    data = []
    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_level_distribution()):
            result = dict(row)
            data.append([result['level'], result['#']])
    return data

async def update_financial_dashboards(bot: G0T0Bot):
    dashboards = await get_financial_dashboards(bot)

    for d in dashboards:
        await update_dashboard(bot, d)

async def update_dashboard(bot: G0T0Bot, dashboard: RefDashboard):
    original_message = await get_pinned_post(bot, dashboard)

    if isinstance(original_message, bool):
        return

    if not original_message or not original_message.pinned:
        return await delete_dashboard(bot, dashboard)
    
    guild = await get_guild(bot, original_message.guild.id)
    
    if dashboard.dashboard_type.value.upper() == "RP":
        channels = get_dashboard_channels(bot, dashboard)
        category = bot.get_channel(dashboard.category_channel_id)

        archivist_field = RPDashboardCategory(title="Archivist",
                                                name="<:pencil:989284061786808380> -- Awaiting Archivist")
        available_field = RPDashboardCategory(title="Available",
                                                name="<:white_check_mark:983576747381518396> -- Available")
        unavailable_field = RPDashboardCategory(title="Unvailable",
                                                name="<:x:983576786447245312> -- Unavailable")
        
        all_fields = [archivist_field, available_field, unavailable_field]
        
        for c in channels:
            if last_message := await get_last_message(c):
                if last_message.content in ["```\n​\n```", "```\n \n```"]:
                    available_field.channels.append(c)
                elif guild.staff_role and guild.staff_role.mention in last_message.content:
                    archivist_field.channels.append(c)
                else:
                    unavailable_field.channels.append(c)
            else:
                available_field.channels.append(c)


        all_fields = [f for f in all_fields if f.channels or f.title != "Archivist"]
        return await original_message.edit(content="", embed=RPDashboardEmbed(all_fields, category.name))

    
    elif dashboard.dashboard_type.value.upper() == "CCENSUS":
        data = await get_class_census_data(bot)

        class_table = Texttable()
        class_table.set_cols_align(['l', 'r'])
        class_table.set_cols_valign(['m', 'm'])
        class_table.set_cols_width([15, 5])
        class_table.header(['Class', '#'])
        class_table.add_rows(data, header=False)

        footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

        return await original_message.edit(content=f"```\n{class_table.draw()}```{footer}", embed=None)
    
    elif dashboard.dashboard_type.value.upper() == "LDIST":
        data = await get_level_distribution_data(bot)

        dist_table = Texttable()
        dist_table.set_cols_align(['l', 'r'])
        dist_table.set_cols_valign(['m', 'm'])
        dist_table.set_cols_width([10, 5])
        dist_table.header(['Level', '#'])
        dist_table.add_rows(data, header=False)

        footer = f"Last Updated - <t:{calendar.timegm(datetime.now(timezone.utc).timetuple())}:F>"

        return await original_message.edit(content=f"```\n{dist_table.draw()}```{footer}", embed=None)
    
    elif dashboard.dashboard_type.value.upper() == "FINANCIAL":
        fin: Financial = await get_financial_data(bot)

        res = requests.get("https://res.cloudinary.com/jerrick/image/upload/d_642250b563292b35f27461a7.png,f_jpg,fl_progressive,q_auto,w_1024/y3mdgvccfyvmemabidd0.jpg")
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
        progress = min(fin.adjusted_total / fin.monthly_goal, 1)  # Cap progress at 100% for the main bar

        shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)

        shadow_color = (0, 0, 0, 100)  

        shadow_rect = [
            bar_x + shadow_offset,
            bar_y + shadow_offset,
            bar_x + bar_width + shadow_offset,
            bar_y + bar_height + shadow_offset,
        ]
        shadow_draw.rounded_rectangle(shadow_rect, fill=shadow_color, radius=corner_radius)
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

        background.save("progress.png")

        embed = discord.Embed(title="G0-T0 Financial Progress",
                              description=f"Current Monthly Progress: ${fin.adjusted_total:.2f}\n"
                                            f"Monthly Goal: ${fin.monthly_goal:.2f}\n"
                                            f"Reserve: ${fin.reserve:.2f}",
                              color=discord.Color.gold(),
                              timestamp=discord.utils.utcnow())
        
        embed.add_field(name="Stretch Goals",
                        value="If we end up with enough reserve funds, we will look at making a website to house our content rulings / updates and work on better integrations with the bot.")
        
        embed.set_image(url="attachment://progress.png")
        embed.set_footer(text="Last Updated")

        file = discord.File("progress.png", filename="progress.png")
        original_message.attachments.clear()
        return await original_message.edit(file=file, embed=embed, content="")

