
from Resolute.bot import G0T0Bot
from Resolute.models.objects.financial import Financial, FinancialSchema, get_financial_query, update_financial_query


async def get_financial_data(bot: G0T0Bot) -> Financial:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_financial_query())
        row = await results.first()

    
    fin = FinancialSchema().load(row)

    return fin

async def update_financial_data(bot: G0T0Bot, fin: Financial) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(update_financial_query(fin))