import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.views.channel_admin import ChannelAdminUI

log = logging.getLogger(__name__)

def setup(bot: G0T0Bot):
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

    channel_commands = discord.SlashCommandGroup("channel", "Channel commands", guild_only=True)
    
    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Channel Admin\' loaded')

    @commands.Cog.listener()
    async def on_db_connected(self):
        busy_guilds = await self.bot.get_busy_guilds()

        for guild in busy_guilds:
            await guild.archive_user.send(embed=ErrorEmbed(f"**Channel Archive**: Issue archiving the channel. Bot went down or shard reset during process."))
            guild.archive_user = None
            await guild.upsert()
            self.bot.dispatch("refresh_guild_cache", guild)

    @channel_commands.command(
        name="manage",
        description="Room settings",
    )
    async def channel_settings(self, ctx: G0T0Context):
        """
        Handles the channel settings command.
        This method creates a new instance of the ChannelAdminUI class, sends it to the user,
        and then deletes the original context message.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
        """

        ui = ChannelAdminUI.new(self.bot, ctx.player)
        await ui.send_to(ctx)
        await ctx.delete()