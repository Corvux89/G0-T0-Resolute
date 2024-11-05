from Resolute.bot import G0T0Bot
from Resolute.models.objects.npc import NPC, get_npc_query, NPCSchema


async def get_npc(bot: G0T0Bot, guild_id: int, key: str) -> NPC:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_npc_query(guild_id, key))    
        row = await results.first()

    if row is None:
        return None
    
    npc: NPC = NPCSchema().load(row)

    return npc
