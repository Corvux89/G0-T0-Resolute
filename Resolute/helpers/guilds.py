
import aiopg

from Resolute.bot import G0T0Bot
from Resolute.models.objects.guilds import *
from Resolute.models.objects.ref_objects import (
    RefWeeklyStipend,
    RefWeeklyStipendSchema, delete_weekly_stipend_query, get_guild_weekly_stipends_query, get_weekly_stipend_query, upsert_weekly_stipend)


async def get_guild(bot: G0T0Bot, guild_id: int) -> PlayerGuild:
    if len(bot.player_guilds) > 0 and (guild:= bot.player_guilds.get(str(guild_id))):
        return guild

    async with bot.db.acquire() as conn:
        async with conn.begin():
            results = await conn.execute(get_guild_from_id(guild_id))
            guild_row = await results.first()

            if guild_row is None:
                guild = PlayerGuild(id=guild_id)
                guild: PlayerGuild = await guild.upsert(bot)
            else:
                guild = await GuildSchema(bot, guild_id).load(guild_row)

    bot.player_guilds[str(guild_id)] = guild
    return guild

# TODO: Make this a bot function looking at local cache rather than query
async def get_guilds_with_reset(bot: G0T0Bot, day: int, hour: int) -> list[PlayerGuild]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_guilds_with_reset_query(day, hour))
        rows = await results.fetchall()

    guild_list = [await GuildSchema(bot, row["id"]).load(row) for row in rows]

    return guild_list

# TODO: Make this a property of the guild
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