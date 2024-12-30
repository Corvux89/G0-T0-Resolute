import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.players import get_player
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player


def is_player_say_message(player: Player, message: discord.Message) -> bool:
        if char_name := get_char_name_from_message(message):
            for char in player.characters:
                if char.name.lower() == char_name.lower():
                    return True
        return False

async def get_player_from_say_message(bot: G0T0Bot, message: discord.Message) -> Player:
         if (player_name := get_player_name_from_message(message)) and (char_name := get_char_name_from_message(message)) and (member := discord.utils.get(message.guild.members, display_name=player_name)):
              player = await get_player(bot, member.id, member.guild.id)
              return player
              

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

def get_player_name_from_message(message: discord.Message) -> str:
        try:
            player_name = message.author.name.split(' // ')[1]
        except:
            return None
        
        return player_name