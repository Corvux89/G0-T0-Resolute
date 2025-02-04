import logging
import re
from timeit import default_timer as timer

from discord import ApplicationContext, Interaction

from Resolute.helpers.general_helpers import get_selection
from Resolute.models.objects.applications import ApplicationType
from Resolute.models.objects.characters import (PlayerCharacter,
                                                PlayerCharacterClass)
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def create_new_character(type: ApplicationType, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs) -> PlayerCharacter:
    """
    Asynchronously creates a new character for a player.
    Args:
        type (ApplicationType): The type of application (e.g., 'freeroll', 'death').
        player (Player): The player creating the new character.
        new_character (PlayerCharacter): The new character to be created.
        new_class (PlayerCharacterClass): The class of the new character.
        **kwargs: Additional keyword arguments, including:
            - old_character (PlayerCharacter): The player's old character, if applicable.
    Returns:
        PlayerCharacter: The newly created character.
    Raises:
        Exception: If there is an error during the character creation process.
    Notes:
        - If the type is 'freeroll' or 'death', the old character will be deactivated.
        - If the type is 'freeroll', the new character will reference the old character.
        - If the type is 'death', the player's handicap amount will be reset.
        - The function logs the time taken to create the character.
    """
    start = timer()

    old_character: PlayerCharacter = kwargs.get('old_character')

    new_character.player_id = player.id
    new_character.guild_id = player.guild_id        
    if type in [ApplicationType.freeroll, ApplicationType.death]:
        new_character.reroll = True
        old_character.active = False

        if type == ApplicationType.freeroll:
            new_character.freeroll_from = old_character.id
        else:
            player.handicap_amount = 0

        await old_character.upsert()

    new_character = await new_character.upsert()

    new_class.character_id = new_character.id
    new_class = await new_class.upsert()

    new_character.classes.append(new_class)

    end = timer()

    log.info(f"Time to create character {new_character.id}: [ {end-start:.2f} ]s")

    return new_character

def find_character_by_name(name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
    """
    Find characters by their name or nickname from a list of PlayerCharacter objects.
    This function searches for characters whose name or nickname matches the given name.
    The search is case-insensitive.
    Args:
        name (str): The name or nickname to search for.
        characters (list[PlayerCharacter]): A list of PlayerCharacter objects to search within.
    Returns:
        list[PlayerCharacter]: A list of PlayerCharacter objects that match the given name or nickname.
                               If no direct matches are found, it returns characters with partial matches.
    """
    direct_matches = [c for c in characters if c.name.lower() == name.lower()]

    # Prioritize main name first
    if not direct_matches:
        direct_matches = [c for c in characters if c.nickname and c.nickname.lower() == name.lower()]

    if not direct_matches:
        partial_matches = [c for c in characters if name.lower() in c.name.lower() or (c.nickname and name.lower() in c.nickname.lower())]
        return partial_matches
    
    return direct_matches  

async def handle_character_mention(ctx: ApplicationContext | Interaction, content: str, DM: bool = True) -> str:
    """
    Handles character mentions in a given content string.
    This function searches for character mentions in the format `{$character_name}` within the provided content string.
    It then attempts to match these mentions with characters from the guild's compendium and replaces the mentions with
    formatted links to the characters. Optionally, it can send a direct message to the mentioned characters' players.
    Args:
        ctx (ApplicationContext | Interaction): The context of the command or interaction.
        content (str): The content string containing potential character mentions.
        DM (bool, optional): Whether to send a direct message to the mentioned characters' players. Defaults to True.
    Returns:
        str: The content string with character mentions replaced by formatted links.
    """
    mentioned_characters = []

    if char_mentions := re.findall(r'{\$([^}]*)}', content):
        g = await ctx.bot.get_player_guild(ctx.guild.id)
        guild_characters = await g.get_all_characters(ctx.bot.compendium)
        for mention in char_mentions:
            matches = find_character_by_name(mention, guild_characters)
            mention_char = None

            if len(matches) == 1:
                mention_char = matches[0]
            elif len(matches) > 1:
                choices = [f"{c.name} [{ctx.guild.get_member(c.player_id).display_name}]" for c in matches]
                if choice := await get_selection(ctx, choices, True, True, f"Type your choice in {ctx.channel.jump_url}", True, f"Found multiple matches for `{mention}`"):
                    mention_char = matches[choices.index(choice)]

            if mention_char:
                if mention_char not in mentioned_characters:
                    mentioned_characters.append(mention_char)
                content = content.replace("{$" + mention + "}", f"[{mention_char.nickname if mention_char.nickname else mention_char.name}](<discord:///users/{mention_char.player_id}>)")
        if DM:
            for char in mentioned_characters:
                if member := ctx.guild.get_member(char.player_id):
                    try:
                        await member.send(f"{ctx.author.mention} directly mentioned `{char.name}` in:\n{ctx.channel.jump_url}")
                    except:
                        pass

    return content
