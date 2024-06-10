import logging
import discord

from discord import SlashCommandGroup, ApplicationContext, Option
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.adventures import get_adventure_from_category
from Resolute.helpers.general_helpers import is_admin
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.views.channel_admin import ChannelAdminUI
from Resolute.models.views.rooms import RoomSettingsUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(ChannelAdmin(bot))


class ChannelAdmin(commands.Cog):
    bot: G0T0Bot

    channel_commands = SlashCommandGroup("channel", "Channel commands")
    
    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Channel Admin\' loaded')

    @channel_commands.command(
        name="manage",
        description="Room settings"
    )
    async def channel_settings(self, ctx: ApplicationContext):
        ui = ChannelAdminUI.new(self.bot, ctx.author)
        await ui.send_to(ctx)
        await ctx.delete()