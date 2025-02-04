import logging

from discord import Interaction

from Resolute.models.categories.categories import ArenaType
from Resolute.models.embeds.arenas import ArenaStatusEmbed
from Resolute.models.objects.arenas import Arena
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def add_player_to_arena(interaction: Interaction, player: Player, character: PlayerCharacter, arena: Arena) -> None:
    """
    Asynchronously adds a player and their character to an arena.
    This function performs several checks to ensure the character can join the arena:
    1. Checks if the character is already in the arena.
    2. Verifies if the player can join the arena based on the arena type and character.
    3. Removes any existing character of the player from the arena before adding the new one.
    After passing the checks, the function:
    1. Removes the player's arena board post.
    2. Sends a message to the interaction response indicating the player has joined the arena.
    3. Adds the character to the arena's character list.
    4. Updates the arena's tier.
    5. Upserts the arena state.
    6. Updates the arena status embed.
    Args:
        interaction (Interaction): The interaction object representing the context of the command.
        player (Player): The player object representing the player joining the arena.
        character (PlayerCharacter): The character object representing the player's character.
        arena (Arena): The arena object representing the arena to join.
    Raises:
        G0T0Error: If the character is already in the arena or if the character cannot join the arena.
    """

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
    """
    Check if a player can join an arena.
    Args:
        player (Player): The player attempting to join the arena.
        arena_type (ArenaType, optional): The type of arena the player wants to join. Defaults to None.
        character (PlayerCharacter, optional): The character the player wants to use in the arena. Defaults to None.
    Returns:
        bool: True if the player can join the arena, False otherwise.
    Conditions:
        - A player cannot participate in more than two arenas simultaneously.
        - If the arena type is "NARRATIVE" and the player does not have the required guild member role, they cannot join.
        - A player cannot join an arena with the same character if the character is already participating in another arena of the same type.
    """

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


    
