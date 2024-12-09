import discord
from Resolute.bot import G0T0Bot
from Resolute.helpers.dashboards import update_financial_dashboards
from Resolute.helpers.financial import get_financial_data, update_financial_data
from Resolute.helpers.store import get_store_items


async def handle_entitlements(bot: G0T0Bot, entitlement: discord.Entitlement):
    store_items = await get_store_items(bot)        
    fin = await get_financial_data(bot)

    if store := next((s for s in store_items if s.sku == entitlement.sku_id), None):
        fin.monthly_total += store.user_cost
        if fin.adjusted_total > fin.monthly_goal:
            fin.reserve += max(0, min(store.user_cost, fin.adjusted_total - fin.monthly_goal))

    await update_financial_data(bot, fin)
    await update_financial_dashboards(bot)