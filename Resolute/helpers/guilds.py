

from Resolute.bot import G0T0Bot
from Resolute.models.objects.guilds import *


async def get_guilds_with_reset(bot: G0T0Bot, day: int, hour: int) -> list[PlayerGuild]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_guilds_with_reset_query(day, hour))
        rows = await results.fetchall()

    guild_list = [await GuildSchema(bot.db, bot.get_guild(row["id"])).load(row) for row in rows]

    return guild_list
