from discord import Embed, Member, Color
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player
from Resolute.models.objects.characters import PlayerCharacter


class LogEmbed(Embed):
    def __init__(self, log_entry: DBLog, author: Member, member: Member, player: Player, character: PlayerCharacter = None, show_values: bool = False):
        super().__init__(title=f"{log_entry.activity.value} Logged - {character.name if character else member.display_name}",
                         color=Color.random())
        
        self.set_thumbnail(url=member.display_avatar.url)
        self.set_footer(text=f"Logged by {author.name} - ID: {log_entry.id}",
                        icon_url=author.display_avatar.url)
        self.description = f"**Player**: {member.mention}\n"

        self.description += f"**Character**: {character.name}\n" if character else ''

        if show_values:
            if log_entry.cc:
                self.description += f"**Chain Codes**: {log_entry.cc:,}\n"
            if log_entry.credits:
                self.description == f"**Credits**: {log_entry.credits:,}\n"
        
        if log_entry.notes:
            self.description += f"**Notes**: {log_entry.notes}\n"

