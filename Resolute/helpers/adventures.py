import discord
from discord import Member, Role

from Resolute.bot import G0T0Bot
from Resolute.helpers.characters import get_character
from Resolute.models.objects.adventures import (
    Adventure, AdventureSchema, get_adventure_by_category_channel_query,
    get_adventure_by_role_query, get_adventures_by_dm_query,
    get_character_adventures_query, upsert_adventure_query)
from Resolute.models.objects.players import Player
from Resolute.models.objects.ref_objects import (NPCSchema,
                                                 get_adventure_npcs_query)


async def get_player_adventures(bot: G0T0Bot, player: Player) -> list[Adventure]:   
    adventures = []
    rows = []

    async with bot.db.acquire() as conn:
        dm_adventures = await conn.execute(get_adventures_by_dm_query(player.id))
        rows = await dm_adventures.fetchall()

    for character in player.characters:
        async with bot.db.acquire() as conn:
            player_adventures = await conn.execute(get_character_adventures_query(character.id))
            rows.extend(await player_adventures.fetchall())

    adventures.extend([AdventureSchema(bot.compendium).load(row) for row in rows])
    
    return adventures

async def upsert_adventure(bot: G0T0Bot, adventure: Adventure) -> None:
    async with bot.db.acquire() as conn:
        await conn.execute(upsert_adventure_query(adventure))

async def update_dm(member: Member, category_premissions: dict, role: Role, adventure_name: str,
                    remove: bool = False) -> dict:
    if remove:
        if role in member.roles:
            await member.remove_roles(role, reason=f"Removed from adventure {adventure_name}")
        del category_premissions[member]
    else:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Creating/Modifying adventure {adventure_name}")
        category_premissions[member] = discord.PermissionOverwrite(manage_messages=True)
    
    return category_premissions

async def get_adventure_from_role(bot: G0T0Bot, role_id: int) -> Adventure:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_adventure_by_role_query(role_id))
        row = await results.first()

    if row is None:
        return None
    
    adventure = AdventureSchema(bot.compendium).load(row)

    await get_adventure_characters(bot, adventure)
    await get_adventure_npcs(bot, adventure)

    return adventure

async def get_adventure_from_category(bot: G0T0Bot, category_channel_id: int) -> Adventure:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_adventure_by_category_channel_query(category_channel_id))
        row = await results.first()

    if row is None:
        return None

    adventure = AdventureSchema(bot.compendium).load(row)

    await get_adventure_characters(bot, adventure)
    await get_adventure_npcs(bot, adventure)

    return adventure


async def get_adventure_characters(bot: G0T0Bot, adventure) -> None:
    if adventure.characters:
        for char_id in adventure.characters:
            character = await get_character(bot, char_id)
            if character:
                adventure.player_characters.append(character)

    
async def get_adventure_npcs(bot: G0T0Bot, adventure: Adventure) -> None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_adventure_npcs_query(adventure.id))
        rows = await results.fetchall()

    adventure.npcs = [NPCSchema().load(row) for row in rows]
