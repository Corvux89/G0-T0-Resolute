import logging

from discord import SlashCommandGroup, ApplicationContext
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.models.views.channel_admin import ChannelAdminUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(ChannelAdmin(bot))


class ChannelAdmin(commands.Cog):
    bot: G0T0Bot

    channel_commands = SlashCommandGroup("channel", "Channel commands", guild_only=True)
    
    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Channel Admin\' loaded')

    @channel_commands.command(
        name="manage",
        description="Room settings",
    )
    async def channel_settings(self, ctx: ApplicationContext):
        ui = ChannelAdminUI.new(self.bot, ctx.author)
        await ui.send_to(ctx)
        await ctx.delete()