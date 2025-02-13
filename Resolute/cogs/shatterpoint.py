import logging

import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.helpers.general_helpers import is_admin
from Resolute.models.objects.shatterpoint import reset_busy_flag_query
from Resolute.models.views.shatterpoint import ShatterpointSettingsUI

log = logging.getLogger(__name__)

# TODO: on_db_connected notify if shatterpoint is busy and is reset


def setup(bot: G0T0Bot):
    bot.add_cog(Shatterpoints(bot))

class Shatterpoints(commands.Cog):
    """
    Cog for managing Shatterpoint events.
    Attributes:
        bot (G0T0Bot): The bot instance.
        shatterpoint_commands (SlashCommandGroup): Group of slash commands related to Shatterpoint event management.
    Methods:
        __init__(bot):
            Initializes the Shatterpoints cog.
        on_db_connected():
            Event listener that resets the busy flag in the database when the bot connects to the database.
        shatterpoint_manage(ctx: ApplicationContext):
            Command to manage a shatterpoint. Only accessible to admins.
    """
    bot: G0T0Bot 
    shatterpoint_commands = SlashCommandGroup("shatterpoint", "Commands related to Shatterpoint event management.", guild_only=True)

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        log.info(f'Cog \'ShatterPoints\' loaded')

    @commands.Cog.listener()
    async def on_db_connected(self):
        """
        Event handler that is called when the database connection is established.
        This method acquires a connection from the bot's database pool and executes
        a query to reset the busy flag.
        Returns:
            None
        """
        async with self.bot.db.acquire() as conn:
            await conn.execute(reset_busy_flag_query())


    @shatterpoint_commands.command(
        name="manage",
        description="Manage a shatterpoint"
    )
    @commands.check(is_admin)
    async def shatterpoint_manage(self, ctx: G0T0Context):
        """
        Manages the shatterpoint settings for the guild.
        This method retrieves the shatterpoint settings for the guild and 
        initializes the ShatterpointSettingsUI with the retrieved settings. 
        It then sends the UI to the user and deletes the original context message.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
        """
        shatterpoint = await self.bot.get_shatterpoint(ctx.guild.id)

        ui = ShatterpointSettingsUI.new(self.bot, ctx.author, shatterpoint)
        await ui.send_to(ctx)
        await ctx.delete()