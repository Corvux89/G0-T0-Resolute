import logging

from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.models.views.channel_admin import ChannelAdminUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(ChannelAdmin(bot))


class ChannelAdmin(commands.Cog):
    '''
    A cog for managing channel-related commands in a Discord bot.
    Attributes:
        bot (G0T0Bot): The instance of the bot that this cog is attached to.
        channel_commands (SlashCommandGroup): A group of slash commands related to channel management.
    Methods:
        __init__(bot):
            Initializes the ChannelAdmin cog with the given bot instance.
        channel_settings(ctx: ApplicationContext):
            Handles the channel settings command. This method creates a new instance of the ChannelAdminUI class,
            sends it to the user, and then deletes the original context message.
    '''
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
        """
        Handles the channel settings command.
        This method creates a new instance of the ChannelAdminUI class, sends it to the user,
        and then deletes the original context message.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
        """

        ui = ChannelAdminUI.new(self.bot, ctx.author)
        await ui.send_to(ctx)
        await ctx.delete()