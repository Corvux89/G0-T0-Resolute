from Resolute.bot import G0T0Bot
from Resolute.models.objects.ref_objects import (NPC, NPCSchema,
                                                 delete_npc_query,
                                                 get_npc_query,
                                                 upsert_npc_query)


async def get_npc(bot: G0T0Bot, guild_id: int, key: str) -> NPC:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_npc_query(guild_id, key))    
        row = await results.first()

    if row is None:
        return None
    
    npc: NPC = NPCSchema().load(row)

    return npc

async def upsert_npc(bot: G0T0Bot, npc: NPC) -> NPC:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_npc_query(npc))
        row = await results.first()

    if row is None:
        return None
    
    npc: NPC = NPCSchema().load(row)

    return npc

async def delete_npc(bot: G0T0Bot, npc: NPC) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(delete_npc_query(npc))
