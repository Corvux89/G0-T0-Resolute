

from Resolute.bot import G0T0Bot
from Resolute.models.objects.shatterpoint import Shatterpoint, ShatterpointPlayer, ShatterPointPlayerSchema, ShatterPointSchema, delete_shatterpoint_players, delete_shatterpoint_query, get_all_shatterpoint_players_query, get_shatterpoint_query, upsert_shatterpoint_player_query, upsert_shatterpoint_query


async def upsert_shatterpoint(bot: G0T0Bot, shatterpoint: Shatterpoint) -> Shatterpoint:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_shatterpoint_query(shatterpoint))
        row = await results.first()

    shatterpoint = ShatterPointSchema().load(row)

    shatterpoint.players = await get_shatterpoint_players(bot, shatterpoint.guild_id)

    return shatterpoint

async def delete_players(bot: G0T0Bot, guild_id: int) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(delete_shatterpoint_players(guild_id))

async def delete_shatterpoint(bot: G0T0Bot, guild_id: int) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(delete_shatterpoint_query(guild_id))

async def get_shatterpoint(bot: G0T0Bot, guild_id: int) -> Shatterpoint:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_shatterpoint_query(guild_id))
        row = await results.first()

    if row is None:
        return None
    
    shatterpoint = ShatterPointSchema().load(row)
    
    shatterpoint.players = await get_shatterpoint_players(bot, guild_id)

    return shatterpoint


async def get_shatterpoint_players(bot: G0T0Bot, guild_id: int) -> list[ShatterpointPlayer]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_all_shatterpoint_players_query(guild_id))
        rows = await results.fetchall()

    player_list = [ShatterPointPlayerSchema().load(row) for row in rows]

    return player_list

async def upsert_shatterpoint_player(bot: G0T0Bot, spplayer: ShatterpointPlayer) -> ShatterpointPlayer:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_shatterpoint_player_query(spplayer))
        row = await results.first()

    if row is None:
        return None
    
    player = ShatterPointPlayerSchema().load(row)

    return player