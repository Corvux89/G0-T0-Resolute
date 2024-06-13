import asyncio
import logging

from discord import SlashCommandGroup, Option, ExtensionAlreadyLoaded, ExtensionNotFound, ExtensionNotLoaded, \
    ApplicationContext
from discord.ext import commands, tasks
from os import listdir

from Resolute.constants import ADMIN_GUILDS
from Resolute.helpers import is_owner
from Resolute.bot import G0T0Bot
from Resolute.helpers import *
from Resolute.models.views.admin import AdminMenuUI
from Resolute.models.views.automation_request import AutomationRequestView

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Admin(bot))


class Admin(commands.Cog):
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    admin_commands = SlashCommandGroup("admin", "Bot administrative commands", guild_ids=ADMIN_GUILDS)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Admin\' loaded')

    @commands.Cog.listener()
    async def on_db_connected(self):
        asyncio.ensure_future(self.reload_category_task.start())

    @commands.slash_command(
        name="automation_request",
        description="Log an automation request"
    )
    async def automation_request(self, ctx: ApplicationContext):
        """
        Used by players to submit an automation request

        Args:
            ctx (ApplicationContext): Represents a Discord application command interaction context.

        Returns:
            Interaction: Modal interaction to gather information about the request
        """
        modal = AutomationRequestView()
        await ctx.send_modal(modal)

    @admin_commands.command(
        name="admin",
        description="Main administration command"
    )
    @commands.check(is_admin)
    async def admin_admin(self, ctx: ApplicationContext):
        ui = AdminMenuUI.new(ctx.author, self.bot)
        await ui.send_to(ctx)
        await ctx.delete()

    @admin_commands.command(
        name="reload",
        description="Reloads either a specific cog, refresh DB information, or reload everything"
    )
    @commands.check(is_owner)
    async def reload_cog(self, ctx: ApplicationContext,
                         cog: Option(str, description="Cog name, ALL, or SHEET", required=True)):
        """
        Used to reload a cog, refresh DB information, or reload all cogs and DB information

        :param ctx: Context
        :param cog: cog to reload, SHEET to reload sheets, ALL to reload all
        """
        await ctx.defer()

        if str(cog).upper() == 'ALL':
            for file_name in listdir('./Resolute/cogs'):
                if file_name.endswith('.py'):
                    ext = file_name.replace('.py', '')
                    self.bot.unload_extension(f'Resolute.cogs.{ext}')
                    self.bot.load_extension(f'Resolute.cogs.{ext}')
            await ctx.respond("All cogs reloaded")
            await self._reload_sheets(ctx)
        elif str(cog).upper() in ['DB', 'COMPENDIUM']:
            await self._reload_DB(ctx)
            await ctx.respond(f'Done')
        else:
            try:
                self.bot.unload_extension(f'Resolute.cogs.{cog}')
            except ExtensionNotLoaded:
                return await ctx.respond(f'Cog was already unloaded', ephemeral=True)
            except ExtensionNotFound:
                return await ctx.respond(f'No cog found by the name: {cog}', ephemeral=True)
            except:
                return await ctx.respond(f'Something went wrong', ephemeral=True)

            self.bot.load_extension(f'Resolute.cogs.{cog}')
            await ctx.respond(f'Cog {cog} reloaded')

    # --------------------------- #
    # Private Methods
    # --------------------------- #

    async def _reload_DB(self, ctx):
        await self.bot.compendium.reload_categories(self.bot)
        await ctx.send("Compendium reloaded")

    # --------------------------- #
    # Tasks
    # --------------------------- #
    @tasks.loop(minutes=30)
    async def reload_category_task(self):
        await self.bot.compendium.reload_categories(self.bot)
