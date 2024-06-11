import discord

from discord import Embed, Color

from Resolute.bot import G0T0Bot
from Resolute.models.objects.dashboards import RPDashboardCategory, RefDashboard

class DashboardEditEmbed(Embed):
    def __init__(self, bot: G0T0Bot, dashboard: RefDashboard):
        super().__init__(color=Color.random(),
                         title=f"Edit Dashboard")
        channel = bot.get_channel(dashboard.channel_id)

        self.description=f"**Type**: {dashboard.dashboard_type.value}\n"\
                         f"**In Channel**: {channel.mention}\n"\
                         f"**Post Link**: https://discord.com/channels/{channel.guild.id}/{channel.id}/{dashboard.post_id} \n"

        if dashboard.excluded_channel_ids:
            self.add_field(name="Excluded Channels",
                           value="\n".join([bot.get_channel(c).mention for c in dashboard.excluded_channel_ids]))

class RPDashboardEmbed(Embed):
    def __init__(self, channel_statuses: list[RPDashboardCategory], category_name: str):
        super().__init__(color=Color.dark_grey(),
                         title=f"Channel Statuses - {category_name}",
                         timestamp=discord.utils.utcnow())
        
        for status in channel_statuses:
            self.add_field(name=status.name,
                           value=status.channel_output(),
                           inline=False)
            
        self.set_footer(text="Last Updated")
