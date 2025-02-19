import discord

from Resolute.constants import THUMBNAIL
from Resolute.helpers.general_helpers import process_message
from Resolute.models.objects.guilds import PlayerGuild


class GuildEmbed(discord.Embed):
    def __init__(self, g: PlayerGuild):
        super().__init__(title=f'Server Settings for {g.guild.name}',
                         colour=discord.Color.random())
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
            
        if len(g.stipends) > 0:
            self.add_field(name="Stipends (* = Leadership Role and only applies highest amount)",
                        value="\n".join([f"{discord.utils.get(g.guild.roles, id=s.role_id).mention} ({s.amount} CC's){'*' if s.leadership else ''}{f' - {s.reason}' if s.reason else ''}" for s in g.stipends]),
                           inline=False)
            
class ResetEmbed(discord.Embed):
    def __init__(self, g: PlayerGuild, is_primary: bool = False, **kwargs):
        super().__init__(color=discord.Color.random())
        if is_primary:
            title = kwargs.get('title', 'Weekly Reset')

            self.set_thumbnail(url=THUMBNAIL)

            if 'reset' in title.lower() and g.reset_message:
                self.description = f"{process_message(g.reset_message, g)}"

            if g.calendar and g.server_date:
                self.add_field(name="Galactic Date",
                            value=f"{g.formatted_server_date}",
                            inline=False)
                
                if (birthdays := kwargs.get('birthdays', [])) and len(birthdays) > 0:
                    birthday_str = []

                    for character in birthdays:
                        if member := g.guild.get_member(character.player_id):
                            birthday_str.append(f"{character.name} ({member.mention})\n - {character.dob_month(g).display_name}:{character.dob_day(g):02}, {character.age(g)} years")

                    self.add_field(name="Happy Birthday!",
                                   value="\n".join(birthday_str))
                    
            if time := kwargs.get('complete_time', 0):
                self.set_footer(text=f"Weekly reset complete in {time:.2f} seconds")
        else:
            title = kwargs.get('title', 'Announcements')
        
        self.title = title

    @staticmethod
    def chunk_announcements(g: PlayerGuild, complete_time: float = 0, **kwargs):
        embeds = []
        current_embed = None
        total_chars = 0

        if len(g.weekly_announcement) == 0:
            return [ResetEmbed(g, True, complete_time=complete_time, **kwargs)]

        for announcement in g.weekly_announcement:
            parts = announcement.split("|")
            title = parts[0] if len(parts) > 1 else "Announcement"
            body = parts[1] if len(parts) > 1 else parts[0]
            processed_announcement = process_message(body, g)

            field_char_count = len(title) + len(processed_announcement)

            if (not current_embed or
                total_chars + field_char_count > 5500 or
                len(current_embed.fields) >= 25):
                
                if current_embed:
                    embeds.append(current_embed)

                current_embed = ResetEmbed(g, len(embeds)==0, complete_time=complete_time, **kwargs)
                total_chars = len(current_embed.title or "") + len(current_embed.description or "") + len(current_embed.footer.text if current_embed.footer else "" or "")
            
            current_embed.add_field(name=title, value=processed_announcement, inline=False)
            total_chars += field_char_count

        if current_embed:
            embeds.append(current_embed)
        
        return embeds
