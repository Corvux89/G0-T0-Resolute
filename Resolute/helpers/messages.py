import discord
from Resolute.models.objects.players import Player


def is_player_say_message(player: Player, message: discord.Message) -> bool:
        try:
            char_name = message.author.name.split(' // ')[0].split('] ', 1)[1].strip()
        except:
            return False

        for char in player.characters:
            if char.name.lower() == char_name.lower():
                return True
        return False