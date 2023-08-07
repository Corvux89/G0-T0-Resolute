import aiopg.sa
import discord
from discord import ApplicationContext, TextChannel, Role
from discord.ext.commands import Bot

from Resolute.compendium import Compendium
from Resolute.models.db_objects import RefCategoryDashboard, RefWeeklyStipend, GlobalPlayer, GlobalEvent
from Resolute.models.schemas import RefCategoryDashboardSchema, RefWeeklyStipendSchema, GlobalPlayerSchema, \
    GlobalEventSchema
from Resolute.queries import get_dashboard_by_category_channel, get_weekly_stipend_query, get_all_global_players, \
    get_active_global, get_global_player, delete_global_event, delete_global_players


async def get_dashboard_from_category_channel_id(ctx: ApplicationContext, category_channel_id: int) -> RefCategoryDashboard | None:

    if category_channel_id is None:
        return None

    async with ctx.bot.db.acquire() as conn:
        results = await conn.execute(get_dashboard_by_category_channel(category_channel_id))
        row = await results.first()

    if row is None:
        return None
    else:
        dashboard: RefCategoryDashboard = RefCategoryDashboardSchema().load(row)
        return dashboard


async def get_last_message(channel: TextChannel) -> discord.Message | None:
    last_message = channel.last_message

    if last_message is None:
        try:
            hx = [msg async  for msg in channel.history(limit=1)]
        except discord.errors.HTTPException as e:
            pass

        if len(hx) > 0:
            last_message = hx[0]
    if last_message is None:
        try:
            lm_id = channel.last_message_id
            last_message = await channel.fetch_message(lm_id) if lm_id is not None else None
        except discord.errors.HTTPException as e:
            print(f"Skipping channel {channel.name}: [ {e} ]")
            return None
    return last_message


async def get_weekly_stipend(db: aiopg.sa.Engine, role: Role) -> RefWeeklyStipend | None:
    async with db.acquire() as conn:
        results = await conn.execute(get_weekly_stipend_query(role.id))
        row = await results.first()

    if row is None:
        return None
    else:
        stipend: RefWeeklyStipend = RefWeeklyStipendSchema().load(row)
        return stipend

async def get_all_players(bot: Bot, guild_id: int) -> dict:
    players = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_all_global_players(guild_id)):
            if row is not None:
                player: GlobalPlayer = GlobalPlayerSchema(bot.compendium).load(row)
                players.append(player)

    return players

async def get_player(bot: Bot, gulid_id: int, player_id: int) -> GlobalPlayer | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_global_player(gulid_id, player_id))
        row = await results.first()

    if row is None:
        return None

    player: GlobalPlayer = GlobalPlayerSchema(bot.compendium).load(row)

    return player

async def get_global(bot: Bot, guild_id: int) -> GlobalEvent | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_active_global(guild_id))
        row = await results.first()

    if row is None:
        return None
    else:
        glob: GlobalEvent = GlobalEventSchema(bot.compendium).load(row)
        return glob

async def close_global(db: aiopg.sa.Engine, guild_id: int):
    async with db.acquire() as conn:
        await conn.execute(delete_global_event(guild_id))
        await conn.execute(delete_global_players(guild_id))

