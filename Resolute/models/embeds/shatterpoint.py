from discord import Embed, Color

from Resolute.bot import G0T0Bot
from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.models.objects.shatterpoint import Shatterpoint

class ShatterpointEmbed(Embed):
    def __init__(self, bot: G0T0Bot, shatterpoint: Shatterpoint, player_list: bool = False):
        super().__init__(title=f"Summary for shatterpoint: {shatterpoint.name}",
                         color=Color.random())
        self.set_thumbnail(url=THUMBNAIL)
        
        guild = bot.get_guild(shatterpoint.guild_id)
        scraped_channels = [bot.get_channel(c).mention for c in shatterpoint.channels] if shatterpoint.channels else ["None"]
        active_players = [p for p in shatterpoint.players if p.active]
        override_players = [p for p in shatterpoint.players if not p.update]

        self.description = f"**Base Chain Codes**: {shatterpoint.base_cc}\n"\
                           f"**Total Participants**: {len(active_players)}"
        

        self.add_field(name="Scraped Channels",
                       value="\n".join([f"{ZWSP3}{c}" for c in scraped_channels]),
                       inline=False)
        
        if override_players:
            self.add_field(name="Manual Overrides",
                           value="\n".join([f"{ZWSP3}{guild.get_member(p.player_id).mention} ({p.cc})" for p in override_players]),
                           inline=False)
            
        if player_list:
            chunk_size = 20

            chunked_players = [active_players[i: i + chunk_size] for i in range(0, len(active_players), chunk_size)]

            for players in chunked_players:
                self.add_field(name="All active players (CC, # posts)",
                               value="\n".join([f"{ZWSP3}{member.mention if member else f'Unknown Member {p.player_id}'} ({p.cc:,}, {p.num_messages})" for p in players if (member := guild.get_member(p.player_id)) is not None]),
                               inline=False)
                
class ShatterpointLogEmbed(Embed):
    def __init__(self, shatterpoint: Shatterpoint):
        super().__init__(title=f"Shatterpoint: {shatterpoint.name} - has been logged")

        self.add_field(name="# of Entries",
                       value=f"{len(shatterpoint.players)}",
                       inline=False)
        
