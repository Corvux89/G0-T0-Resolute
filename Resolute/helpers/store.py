from ast import Store

from Resolute.bot import G0T0Bot
from Resolute.models.objects.store import StoreSchema, get_store_items_query


async def get_store_items(bot: G0T0Bot) -> list[Store]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_store_items_query())
        rows = await results.fetchall()

    store_items = [StoreSchema().load(row) for row in rows]

    return store_items