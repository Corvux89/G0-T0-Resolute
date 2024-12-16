import asyncio

import aiopg

from Resolute.bot import G0T0Bot
from Resolute.models.objects.guilds import *
from Resolute.models.objects.ref_objects import (
    NPCSchema, RefServerCalendarSchema, RefWeeklyStipend,
    RefWeeklyStipendSchema, delete_weekly_stipend_query, get_guild_npcs_query,
    get_guild_weekly_stipends_query, get_server_calendar,
    get_weekly_stipend_query, upsert_weekly_stipend)


async def get_guild(bot: G0T0Bot, guild_id: int) -> PlayerGuild:
    if len(bot.player_guilds) > 0 and (g:= bot.player_guilds.get(str(guild_id))):
        return g

    async with bot.db.acquire() as conn:
        async with conn.begin():
            results = await conn.execute(get_guild_from_id(guild_id))
            guild_row = await results.first()

            if guild_row is None:
                guild = PlayerGuild(id=guild_id)
                results = await conn.execute(upsert_guild(guild))
                guild_row = await results.first()

            g: PlayerGuild = GuildSchema(bot.get_guild(guild_id)).load(guild_row)

    await build_guild(bot, g)
    bot.player_guilds[str(guild_id)] = g
    return g

async def build_guild(bot: G0T0Bot, guild: PlayerGuild):
    await load_calendar(bot.db, guild)
    await load_npcs(bot, guild)
    guild.guild = bot.get_guild(guild.id)


async def load_calendar(db: aiopg.sa.Engine, guild: PlayerGuild):
    async with db.acquire() as conn:
            results = await conn.execute(get_server_calendar(guild.id))
            rows = await results.fetchall()
    guild.calendar = [RefServerCalendarSchema().load(row) for row in rows]

async def load_npcs(bot: G0T0Bot, guild: PlayerGuild):
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_guild_npcs_query(guild.id))
        rows = await results.fetchall()
    guild.npcs = [NPCSchema().load(row) for row in rows]


async def update_guild(bot: G0T0Bot, guild: PlayerGuild) -> PlayerGuild:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_guild(guild))
        row = await results.first()

    g = GuildSchema().load(row)

    await build_guild(bot, g)
    bot.player_guilds[str(guild.id)] = g
    return g

async def get_guilds_with_reset(bot: G0T0Bot, day: int, hour: int) -> list[PlayerGuild]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_guilds_with_reset_query(day, hour))
        rows = await results.fetchall()

    guild_list = [GuildSchema().load(row) for row in rows]

    await asyncio.gather(*(build_guild(bot, g) for g in guild_list))

    return guild_list

async def get_guild_stipends(db: aiopg.sa.Engine, guild_id: int) -> list[RefWeeklyStipend]:
    async with db.acquire() as conn:
        results = await conn.execute(get_guild_weekly_stipends_query(guild_id))
        rows = await results.fetchall()
    
    stipend_list = [RefWeeklyStipendSchema().load(row) for row in rows]

    return stipend_list

async def get_weekly_stipend(db: aiopg.sa.Engine, role_id: int) -> RefWeeklyStipend:
    async with db.acquire() as conn:
        results = await conn.execute(get_weekly_stipend_query(role_id))
        row = await results.first()

        if row is None:
            return None
        
        stipend: RefWeeklyStipend = RefWeeklyStipendSchema().load(row)

        return stipend
    
async def update_weekly_stipend(db: aiopg.sa.Engine, stipend: RefWeeklyStipend) -> None:
    async with db.acquire() as conn:
        await conn.execute(upsert_weekly_stipend(stipend))

async def delete_weekly_stipend(db: aiopg.sa.Engine, stipend: RefWeeklyStipend) -> None:
    async with db.acquire() as conn:
        await conn.execute(delete_weekly_stipend_query(stipend))

def get_guild_internal_date(guild: PlayerGuild, day: int, month: int, year: int) -> int:
    if not guild.calendar:
        return None
    
    epoch_time = (year * guild.days_in_server_year) + (guild.calendar[month-1].day_start+day-1)

    return epoch_time