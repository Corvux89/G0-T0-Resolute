import discord

from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player


def is_player_say_message(player: Player, message: discord.Message) -> bool:
        if char_name := get_char_name_from_message(message):
            for char in player.characters:
                if char.name.lower() == char_name.lower():
                    return True
        return False    

def is_guild_npc_message(guild: PlayerGuild, message: discord.Message) -> bool:
     return bool(next((npc for npc in guild.npcs if npc.name.lower() == message.author.name.lower()), None))

def is_adventure_npc_message(adventure: Adventure, message: discord.Message) -> bool:
     return bool(next((npc for npc in adventure.npcs if npc.name.lower() == message.author.name.lower()), None))

def get_char_name_from_message(message: discord.Message) -> str:
        try:
            char_name = message.author.name.split(' // ')[0].split('] ', 1)[1].strip()
        except:
            return None
        
        return char_name