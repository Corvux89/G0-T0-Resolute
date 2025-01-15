import logging

import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.guilds import get_guild
from Resolute.models.categories.categories import ArenaType
from Resolute.models.embeds.arenas import ArenaStatusEmbed
from Resolute.models.objects.arenas import (Arena, ArenaSchema,
                                            get_arena_by_channel_query,
                                            get_arena_by_host_query,
                                            get_character_arena_query)
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def get_arena(bot: G0T0Bot, channel_id: int) -> Arena:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_arena_by_channel_query(channel_id))
        row = await results.first()

    if row is None:
        return None
    
    arena: Arena = await ArenaSchema(bot).load(row)

    return arena

async def add_player_to_arena(bot: G0T0Bot, interaction: discord.Interaction, player: Player, character: PlayerCharacter, arena: Arena) -> None:
    if character.id in arena.characters:
        raise G0T0Error("Character already in the arena")
    elif not await can_join_arena(bot, player, arena.type, character):
        raise G0T0Error(f"Character is already in an {arena.type.value.lower()} arena")    
    if player.id in {c.player_id for c in arena.player_characters}:
        remove_char = next((c for c in arena.player_characters if c.player_id == player.id), None)
        arena.player_characters.remove(remove_char)
        arena.characters.remove(remove_char.id)

    await player.remove_arena_board_post(bot, interaction)
    # await remove_arena_board_post(interaction, bot, player)
    await interaction.response.send_message(f"{interaction.guild.get_member(player.id).mention} has joined the arena with {character.name}!")

    arena.characters.append(character.id)
    arena.player_characters.append(character)
    arena.update_tier(bot)
    
    await arena.upsert(bot)
    await ArenaStatusEmbed(interaction, arena).update()


async def get_player_arenas(bot: G0T0Bot, player: Player) -> list[Arena]:
    arenas = []
    rows =[]

    async with bot.db.acquire() as conn:
        host_arenas = await conn.execute(get_arena_by_host_query(player.id))
        rows = await host_arenas.fetchall()

    for character in player.characters:
        async with bot.db.acquire() as conn:
            player_arenas = await conn.execute(get_character_arena_query(character.id))
            rows.extend(await player_arenas.fetchall())

    arenas.extend(ArenaSchema(bot).load(row) for row in rows)
    
    return arenas


async def can_join_arena(bot: G0T0Bot, player: Player, arena_type: ArenaType = None, character: PlayerCharacter = None) -> bool:
    player_arenas = await get_player_arenas(bot, player)
    participating_arenas = [a for a in player_arenas if any([c.id in a.characters for c in player.characters])]
    guild = await get_guild(bot, player.guild_id)

    if len(participating_arenas) >= 2:
        return False
    elif arena_type and arena_type.value == "NARRATIVE" and guild.member_role and guild.member_role not in player.member.roles:
        return False

    if arena_type:
        filtered_arenas = [a for a in participating_arenas if a.type.id == arena_type.id]
    else:
        filtered_arenas = []
    
    if character and (arena := next((a for a in filtered_arenas if character.id in a.characters), None)):
        return False

    return True


    
