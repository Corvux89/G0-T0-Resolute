import discord

from discord import Color, Embed
from Resolute.constants import THUMBNAIL
from Resolute.helpers.general_helpers import process_message
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.ref_objects import RefWeeklyStipend



class GuildEmbed(Embed):
    def __init__(self, g: PlayerGuild, stipends: list[RefWeeklyStipend] = None):
        super().__init__(title=f'Server Settings for {g.guild.name}',
                         colour=Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.add_field(name="**Settings**",
                       value=f"**Max Level**: {g.max_level}\n"
                             f"**Max Characters**: {g.max_characters}\n"
                             f"**Handicap CC Amount**: {g.handicap_cc}\n"
                             f"**Diversion Limit**: {g.div_limit}\n"
                             f"**Log Reward Point Threshold**: {g.reward_threshold or ''}\n",
                       inline=False)

        reset_str = f"**Approx Next Run**: <t:{g.get_next_reset}>\n" if g.get_next_reset else ""
        reset_str += f"**Last Reset: ** <t:{g.get_last_reset}>"

        self.add_field(name="**Reset Schedule**",   
                        value=reset_str,
                        inline=False)
            
        if len(stipends) > 0:
            self.add_field(name="Stipends (* = Leadership Role and only applies highest amount)",
                        value="\n".join([f"{discord.utils.get(g.guild.roles, id=s.role_id).mention} ({s.amount} CC's){'*' if s.leadership else ''}{f' - {s.reason}' if s.reason else ''}" for s in stipends]),
                           inline=False)
            
class ResetEmbed(Embed):
    def __init__(self, g: PlayerGuild, completeTime: float):
        super().__init__(title=f"Weekly Reset",
                         color=Color.random())
        
        self.set_thumbnail(url=THUMBNAIL)

        if g.reset_message:
            self.description = f"{process_message(g.reset_message, g)}"

        if g.calendar and g.server_date:
            self.add_field(name="Galactic Date",
                           value=f"{g.formatted_server_date}",
                           inline=False)

        if g.weekly_announcement:
            for announcement in g.weekly_announcement:
                parts = announcement.split("|")
                title = parts[0] if len(parts) > 1 else "Announcement"
                body = parts[1] if len(parts) > 1 else parts[0]
                self.add_field(name=title,
                               value=process_message(body, g),
                               inline=False)

        self.set_footer(text=f"Weekly reset complete in {completeTime:.2f} seconds")
        