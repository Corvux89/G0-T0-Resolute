
from discord import Message, utils

from Resolute.bot import G0T0Bot
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player


def is_player_say_message(player: Player, message: Message) -> bool:
        """
        Determines if a given message is a "say" message from one of the player's characters.
        Args:
            player (Player): The player object containing a list of characters.
            message (Message): The message object to be checked.
        Returns:
            bool: True if the message is a "say" message from one of the player's characters, False otherwise.
        """
        if char_name := get_char_name_from_message(message):
            for char in player.characters:
                if char.name.lower() == char_name.lower():
                    return True
        return False

async def get_player_from_say_message(bot: G0T0Bot, message: Message) -> Player:
        """
        Extracts player information from a message and retrieves the corresponding Player object.
        Args:
            bot (G0T0Bot): The bot instance used to interact with the game.
            message (Message): The message object containing the player's information.
        Returns:
            Player: The Player object corresponding to the extracted player information.
        Raises:
            ValueError: If the player name or character name cannot be extracted from the message.
        """
        if (player_name := get_player_name_from_message(message)) and (char_name := get_char_name_from_message(message)) and (member := utils.get(message.guild.members, display_name=player_name)):
            player = await bot.get_player(member.id, member.guild.id)
            return player
              

def is_guild_npc_message(guild: PlayerGuild, message: Message) -> bool:
    """
    Determines if the author of a given message is an NPC (Non-Player Character) in the specified guild.
    Args:
        guild (PlayerGuild): The guild containing NPCs to check against.
        message (Message): The message whose author is to be checked.
    Returns:
        bool: True if the message author is an NPC in the guild, False otherwise.
    """ 
    return bool(next((npc for npc in guild.npcs if npc.name.lower() == message.author.name.lower()), None))

def is_adventure_npc_message(adventure: Adventure, message: Message) -> bool:
    """
    Determines if the author of a given message is an NPC (Non-Player Character) in the specified adventure.
    Args:
        adventure (Adventure): The adventure instance containing NPCs.
        message (Message): The message instance to check the author of.
    Returns:
        bool: True if the message author is an NPC in the adventure, False otherwise.
    """
    return bool(next((npc for npc in adventure.npcs if npc.name.lower() == message.author.name.lower()), None))

def get_char_name_from_message(message: Message) -> str:
        """
        Extracts the character name from a given message.
        The function attempts to split the author's name in the message by ' // ' and then by '] ' 
        to extract the character name. If the extraction fails, it returns None.
        Args:
            message (Message): The message object containing the author's name.
        Returns:
            str: The extracted character name, or None if extraction fails.
        """
        try:
            char_name = message.author.name.split(' // ')[0].split('] ', 1)[1].strip()
        except:
            return None
        
        return char_name

def get_player_name_from_message(message: Message) -> str:
        """
        Extracts the player's name from a message object.
        The function assumes that the author's name in the message is formatted
        with a ' // ' delimiter, and it extracts the portion after the first delimiter.
        Args:
            message (Message): The message object containing the author's name.
        Returns:
            str: The extracted player's name. If the author's name does not contain
                 the expected delimiter, returns None.
        """
        try:
            player_name = message.author.name.split(' // ')[1:]
        except:
            return None
        
        return " // ".join(player_name)