import logging

import discord

from Resolute.models.categories.categories import ArenaType
from Resolute.models.embeds.arenas import ArenaStatusEmbed
from Resolute.models.objects.arenas import (Arena)
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def add_player_to_arena(interaction: discord.Interaction, player: Player, character: PlayerCharacter, arena: Arena) -> None:
    if character.id in arena.characters:
        raise G0T0Error("Character already in the arena")
    elif not await can_join_arena(player, arena.type, character):
        raise G0T0Error(f"Character is already in an {arena.type.value.lower()} arena")    
    if player.id in {c.player_id for c in arena.player_characters}:
        remove_char = next((c for c in arena.player_characters if c.player_id == player.id), None)
        arena.player_characters.remove(remove_char)
        arena.characters.remove(remove_char.id)

    await player.remove_arena_board_post(interaction)
    await interaction.response.send_message(f"{player.member.mention} has joined the arena with {character.name}!")

    arena.characters.append(character.id)
    arena.player_characters.append(character)
    arena.update_tier()
    
    await arena.upsert()
    await ArenaStatusEmbed(interaction, arena).update()


async def can_join_arena(player: Player, arena_type: ArenaType = None, character: PlayerCharacter = None) -> bool:
    participating_arenas = [a for a in player.arenas if any([c.id in a.characters for c in player.characters])]

    if len(participating_arenas) >= 2:
        return False
    elif arena_type and arena_type.value == "NARRATIVE" and player.guild.member_role and player.guild.member_role not in player.member.roles:
        return False

    if arena_type:
        filtered_arenas = [a for a in participating_arenas if a.type.id == arena_type.id]
    else:
        filtered_arenas = []
    
    if character and (arena := next((a for a in filtered_arenas if character.id in a.characters), None)):
        return False

    return True


    
