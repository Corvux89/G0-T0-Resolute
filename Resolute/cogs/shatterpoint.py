import logging

from discord.commands import SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.helpers import is_admin
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.views.shatterpoint import ShatterpointSettingsUI

log = logging.getLogger(__name__)


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
    shatterpoint_commands = SlashCommandGroup(
        "shatterpoint",
        "Commands related to Shatterpoint event management.",
        guild_only=True,
    )
    check: bool = True

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        log.info(f"Cog 'ShatterPoints' loaded")

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        """
        Event handler that is called when the database connection is established.
        This method acquires a connection from the bot's database pool and executes
        a query to reset the busy flag.
        Returns:
            None
        """
        if self.check:
            self.check = False
            busy_shatterpoints = await self.bot.get_busy_shatterpoints()

            for shatterpoint in busy_shatterpoints:
                if shatterpoint.busy_member:
                    await shatterpoint.busy_member.send(
                        embed=ErrorEmbed(
                            f"**{shatterpoint.name}**: Issue scraping the channel. Bot went down or shard reset during process. Please check your settings to ensure no data was written, and re-scrape."
                        )
                    )
                    shatterpoint.busy_member = None
                    await shatterpoint.upsert()

    @shatterpoint_commands.command(name="manage", description="Manage a shatterpoint")
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
