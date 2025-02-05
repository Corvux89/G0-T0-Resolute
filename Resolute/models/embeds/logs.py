from datetime import datetime, timezone
from discord import Embed, Color

from Resolute.constants import THUMBNAIL
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player


class LogEmbed(Embed):
    def __init__(self, log_entry: DBLog, show_values: bool = False):
        super().__init__(title=f"{log_entry.activity.value} Logged - {log_entry.character.name if log_entry.character else log_entry.player.member.display_name}",
                         color=Color.random(),
                         timestamp=log_entry.created_ts.replace(tzinfo=None))
        
        self.set_thumbnail(url=log_entry.player.member.display_avatar.url if log_entry.player.member else THUMBNAIL)
        self.set_footer(text=f"Logged by {log_entry.author.member.name} - ID: {log_entry.id}",
                        icon_url=log_entry.author.member.display_avatar.url)
        self.description = f"**Player**: {log_entry.player.member.mention if log_entry.player.member else 'Player not found'}\n"

        self.description += f"**Character**: {log_entry.character.name}\n" if log_entry.character else ''

        self.description += f"**Faction**: {log_entry.faction.value}\n" if log_entry.faction else ''

        if show_values:
            if log_entry.cc:
                self.description += f"**Chain Codes**: {log_entry.cc:,}\n"
            if log_entry.credits:
                self.description += f"**Credits**: {log_entry.credits:,}\n"
            if log_entry.renown:
                self.description += f"**Renown**: {log_entry.renown}"
        
        if log_entry.notes:
            self.description += f"**Notes**: {log_entry.notes}\n"


class LogStatsEmbed(Embed):
    def __init__(self, player: Player, player_stats: {}, first: bool = True):
        super().__init__(title=f"Log statistics for {player.member.name}",
                         color=Color.random(),
                         timestamp=datetime.now(timezone.utc))
        
        self.set_thumbnail(url=player.member.display_avatar.url)

        if first:
            self.description = f"**Charcters (active / total)**: {len([x for x in player.characters if x.active == True])} / {len(player.characters)}\n"\
                            f"**Total Logs**: {player_stats['#']:,}\n"\
                            f"**Total CC Earned**: {player_stats['debt']:,}\n"\
                            f"**Total CC Spent**: {player_stats['credit']:,}\n"\
                            f"**Character Starting CC**: {player_stats['starting']:,}\n"\
                            f"**Total Lifetime CC**: {player_stats['starting'] + player_stats['debt'] + player_stats['credit']:,}"
            
            self.add_field(
                name="Activity Breakdown",
                value="\n".join([f"{a.replace('Activity ', '')}: {v}" for a, v in player_stats.items() if "Activity" in a])
            )

class LogHxEmbed(Embed):
    def __init__(self, player: Player, logs: list[DBLog] = []):
        super().__init__(title=f"Log history - {player.member.name}",
                         color=Color.random())
        
        self.set_thumbnail(url=player.member.display_avatar.url)

        if not logs:
            self.description = f"No logs for this player"

        for log in logs:
            value = f"**Author**: {log.author.member.mention if log.author.member else '`Not found`'}\n"\
                    f"**Character**: {log.character.name if log.character else 'None'}{' (*inactive*)' if log.character and not log.character.active else ''}\n"\
                    f"**Activity:** {log.activity.value}\n"\
                    f"**Chain Codes**: {log.cc:,}\n"\
                    f"**Credits**: {log.credits:,}\n"
            
            if log.faction:
                value += (f"**Renown**: {log.renown}\n"
                          f"**Faction**: {log.faction.value}\n")
                
            value += (f"**Invalidated?**: {log.invalid}\n"\
                      f"{f'**Notes**: {log.notes}' if log.notes else ''}")
            
            self.add_field(name=f"Log # {log.id} - <t:{log.epoch_time}>", value=value, inline=False)