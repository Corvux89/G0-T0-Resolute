import calendar
import discord

from datetime import datetime, timezone
from Resolute.bot import G0T0Bot
from Resolute.models.embeds.dashboards import RPDashboardEmbed
from Resolute.models.objects.dashboards import RPDashboardCategory, RefDashboard, RefDashboardSchema, delete_dashboard_query, get_class_census, get_dashboard_by_category_channel_query, get_dashboard_by_post_id, get_dashboards, get_level_distribution, upsert_dashboard_query
from texttable import Texttable


async def get_pinned_post(bot: G0T0Bot, dashboard: RefDashboard) -> discord.Message:
    if channel := bot.get_channel(dashboard.channel_id):
        try:
            msg = await channel.fetch_message(dashboard.post_id)
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
    last_message = channel.last_message

    if last_message is None:
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
            if bot.get_channel(dashboard.category_channel_id).guild.id == guild_id:
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

async def update_dashboard(bot: G0T0Bot, dashboard: RefDashboard):
    original_message = await get_pinned_post(bot, dashboard)

    if not original_message or not original_message.pinned:
        return await delete_dashboard(bot, dashboard)
    
    if dashboard.dashboard_type.value.upper() == "RP":
        channels = get_dashboard_channels(bot, dashboard)
        category = bot.get_channel(dashboard.category_channel_id)
        archivist_role = discord.utils.get(category.guild.roles, name="Archivist")

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
                elif archivist_role and archivist_role.mention in last_message.content:
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


