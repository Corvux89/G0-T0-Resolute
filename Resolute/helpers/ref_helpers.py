import aiopg.sa
import discord
from discord import ApplicationContext, TextChannel, Role
from discord.ext.commands import Bot

from ProphetBot.compendium import Compendium
from ProphetBot.models.db_objects import RefCategoryDashboard, RefWeeklyStipend, GlobalPlayer, GlobalEvent, \
    GlobalModifier, HostStatus
from ProphetBot.models.schemas import RefCategoryDashboardSchema, RefWeeklyStipendSchema, GlobalPlayerSchema, \
    GlobalEventSchema
from ProphetBot.queries import get_dashboard_by_category_channel, get_weekly_stipend_query, get_all_global_players, \
    get_active_global, get_global_player, delete_global_event, delete_global_players


async def get_dashboard_from_category_channel_id(ctx: ApplicationContext) -> RefCategoryDashboard | None:
    category_channel_id = ctx.channel.category_id

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


def calc_amt(compendium: Compendium, base: int, pmod: GlobalModifier = None, hostmod: HostStatus = None) -> int:
    if pmod is None or (hostmod is not None and hostmod.value.upper() == "HOSTING ONLY"):
        pmod = compendium.get_object("c_global_modifier", "Low")

    ratio_adj = 1
    if hostmod is None:
        host_addition = 0
    elif hostmod.value.upper() == "PARTICIPATING":
        host_addition = 100
    elif hostmod.value.upper() == "HOSTING ONLY":
        host_addition = (base * .75) + 100
        ratio_adj = 0
    else:
        host_addition = 0

    amt = round(base * (pmod.adjustment * ratio_adj))

    if amt > pmod.max:
        amt = pmod.max
    amt += host_addition
    return amt


async def get_all_players(bot: Bot, guild_id: int) -> dict:
    players = dict()

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_all_global_players(guild_id)):
            if row is not None:
                player: GlobalPlayer = GlobalPlayerSchema(bot.compendium).load(row)
                players[player.player_id] = player

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

