from datetime import datetime, timezone
from discord import Embed, Member, Color
from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.helpers.characters import get_character
from Resolute.models.categories.categories import Activity
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player
from Resolute.models.objects.characters import PlayerCharacter


class LogEmbed(Embed):
    def __init__(self, log_entry: DBLog, author: Member, member: Member, character: PlayerCharacter = None, show_values: bool = False):
        super().__init__(title=f"{log_entry.activity.value} Logged - {character.name if character else member.display_name}",
                         color=Color.random(),
                         timestamp=log_entry.created_ts)
        
        self.set_thumbnail(url=member.display_avatar.url)
        self.set_footer(text=f"Logged by {author.name} - ID: {log_entry.id}",
                        icon_url=author.display_avatar.url)
        self.description = f"**Player**: {member.mention}\n"

        self.description += f"**Character**: {character.name}\n" if character else ''

        if show_values:
            if log_entry.cc:
                self.description += f"**Chain Codes**: {log_entry.cc:,}\n"
            if log_entry.credits:
                self.description += f"**Credits**: {log_entry.credits:,}\n"
        
        if log_entry.notes:
            self.description += f"**Notes**: {log_entry.notes}\n"


class LogStatsEmbed(Embed):
    def __init__(self, bot: G0T0Bot, player: Player, player_stats: {}, first: bool = True):
        guild = bot.get_guild(player.guild_id)
        member = guild.get_member(player.id)

        super().__init__(title=f"Log statistics for {member.name}",
                         color=Color.random(),
                         timestamp=datetime.now(timezone.utc))
        
        self.set_thumbnail(url=member.display_avatar.url)

        if first:
            self.description = f"**Charcters (active / total)**: {len([x for x in player.characters if x.active == True])} / {len(player.characters)}\n"\
                            f"**Total Logs**: {player_stats['#']:,}\n"\
                            f"**Total CC Earned**: {player_stats['debt']:,}\n"\
                            f"**Total CC Spent**: {player_stats['credit']:,}\n"\
                            f"**Character Starting CC**: {player_stats['starting']:,}\n"\
                            f"**Total Lifetime CC**: {player_stats['starting'] + player_stats['debt'] + player_stats['credit']:,}"
            
            self.add_field(
                name="Activity Breakdown",
                value="\n".join([f"{bot.compendium.get_object(Activity, int(a.replace('Activity ', ''))).value}: {v}" for a, v in player_stats.items() if "Activity" in a])
            )

class LogHxEmbed(Embed):
    def __init__(self, bot: G0T0Bot, player: Player, logs: list[DBLog] = []):
        guild = bot.get_guild(player.guild_id)
        member = guild.get_member(player.id)
        super().__init__(title=f"Log history - {member.name}",
                         color=Color.random())
        
        self.set_thumbnail(url=member.display_avatar.url)

        if not logs:
            self.description = f"No logs for this player"

        for log in logs:
            author = guild.get_member(log.author).mention if guild.get_member(log.author) else "`Not found`"
            character = next((c for c in player.characters if c.id == log.character_id), None)

            value = f"**Author**: {author}\n"\
                    f"**Character**: {character.name if character else 'None'}{' (*inactive*)' if character and not character.active else ''}\n"\
                    f"**Activity:** {log.activity.value}\n"\
                    f"**Chain Codes**: {log.cc:,}\n"\
                    f"**Credits**: {log.credits:,}\n"\
                    f"**Invalidated?**: {log.invalid}\n"\
                    f"{f'**Notes**: {log.notes}' if log.notes else ''}"
            
            self.add_field(name=f"Log # {log.id} - <t:{log.epoch_time}>", value=value, inline=False)