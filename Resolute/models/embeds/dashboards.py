import discord

from Resolute.models.objects.dashboards import RefDashboard, RPDashboardCategory


class DashboardEditEmbed(discord.Embed):
    def __init__(self, dashboard: RefDashboard):
        super().__init__(color=discord.Color.random(), title=f"Edit Dashboard")

        self.description = (
            f"**Type**: {dashboard.dashboard_type.value}\n"
            f"**In Channel**: {dashboard.channel.mention}\n"
            f"**Post Link**: https://discord.com/channels/{dashboard.channel.guild.id}/{dashboard.channel.id}/{dashboard.post_id} \n"
        )

        if dashboard.excluded_channels:
            self.add_field(
                name="Excluded Channels",
                value="\n".join(c.mention for c in dashboard.excluded_channels if c),
            )


class RPDashboardEmbed(discord.Embed):
    def __init__(self, channel_statuses: list[RPDashboardCategory], category_name: str):
        super().__init__(
            color=discord.Color.dark_grey(),
            title=f"Channel Statuses - {category_name}",
            timestamp=discord.utils.utcnow(),
        )

        for status in channel_statuses:
            self.add_field(
                name=status.name, value=status.channel_output(), inline=False
            )

        self.set_footer(text="Last Updated")
