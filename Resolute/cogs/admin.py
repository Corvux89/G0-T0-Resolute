import asyncio
from contextlib import redirect_stdout
import datetime
import io
import logging
import os
import textwrap
import traceback

import discord
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import ADMIN_GUILDS
from Resolute.helpers import is_admin, is_owner
from Resolute.models.objects.dashboards import RefDashboard
from Resolute.models.objects.financial import Financial
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.store import Store
from Resolute.models.views.admin import AdminMenuUI
from Resolute.models.views.automation_request import AutomationRequestView

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Admin(bot))


class Admin(commands.Cog):
    """
    A Cog that handles administrative commands and tasks for the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        admin_commands (discord.SlashCommandGroup): A group of slash commands for administrative purposes.
    Methods:
        __init__(bot):
            Initializes the Admin cog with the given bot instance.
        on_db_connected():
            Listener for the database connection event. Starts the reload_category_task and check_financials tasks if they are not already running.
        on_refresh_guild_cache(guild: PlayerGuild):
            Listener for the refresh guild cache event. Fetches and updates the guild cache.
        automation_request(ctx: discord.ApplicationContext):
            Slash command for logging an automation request. Sends a modal interaction to gather information about the request.
        admin_admin(ctx: discord.ApplicationContext):
            Slash command for handling the main administration command. Creates and sends an AdminMenuUI instance to the context, then deletes the context message.
        reload_cog(ctx: discord.ApplicationContext, cog: discord.Option):
            Slash command for reloading a specific cog, refreshing DB information, or reloading all cogs and DB information.
        _reload_DB(ctx):
            Private method for reloading the database information.
        reload_category_task():
            Task that reloads the compendium categories every 30 minutes.
        check_financials():
            Task that checks and updates financial data every 24 hours.
    """

    bot: G0T0Bot
    admin_commands = discord.SlashCommandGroup(
        "admin", "Bot administrative commands", guild_ids=ADMIN_GUILDS
    )

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Admin' loaded")

    @commands.Cog.listener()
    async def on_db_connected(self):
        if not self.reload_category_task.is_running():
            asyncio.ensure_future(self.reload_category_task.start())

        if not self.check_financials.is_running():
            asyncio.ensure_future(self.check_financials.start())

    @commands.Cog.listener()
    async def on_refresh_guild_cache(self, guild: PlayerGuild):
        guild = await guild.fetch()
        self.bot.player_guilds[str(guild.id)] = guild

    @commands.slash_command(
        name="automation_request", description="Log an automation request"
    )
    async def automation_request(self, ctx: G0T0Context):
        """
        Used by players to submit an automation request

        Args:
            ctx (discord.ApplicationContext): Represents a Discord application command interaction context.

        Returns:
            Interaction: Modal interaction to gather information about the request
        """
        modal = AutomationRequestView(ctx.player.guild)
        await ctx.send_modal(modal)

    @admin_commands.command(name="admin", description="Main administration command")
    @commands.check(is_admin)
    async def admin_admin(self, ctx: discord.ApplicationContext):
        """
        Handles the admin command for the admin cog.
        This command creates a new instance of AdminMenuUI, sends it to the context,
        and then deletes the context message.
        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
        """
        ui = AdminMenuUI.new(ctx.author, self.bot)
        await ui.send_to(ctx)
        await ctx.delete()

    @admin_commands.command(
        name="reload",
        description="Reloads either a specific cog, refresh DB information, or reload everything",
    )
    @commands.check(is_owner)
    async def reload_cog(
        self,
        ctx: G0T0Context,
        cog: discord.Option(
            discord.SlashCommandOptionType(3),
            description="Cog name, ALL, or DB",
            required=True,
        ),
    ):
        """
        Used to reload a cog, refresh DB information, or reload all cogs and DB information

        :param ctx: Context
        :param cog: cog to reload, SHEET to reload sheets, ALL to reload all
        """

        if str(cog).upper() == "ALL":
            for file_name in os.listdir("./Resolute/cogs"):
                if file_name.endswith(".py"):
                    ext = file_name.replace(".py", "")
                    self.bot.unload_extension(f"Resolute.cogs.{ext}")
                    self.bot.load_extension(f"Resolute.cogs.{ext}")
            await ctx.respond("All cogs reloaded")
        elif str(cog).upper() in ["DB", "COMPENDIUM"]:
            await self._reload_DB(ctx)
            await ctx.respond(f"Done")
        else:
            try:
                self.bot.unload_extension(f"Resolute.cogs.{cog}")
            except discord.ExtensionNotLoaded:
                return await ctx.respond(f"Cog was already unloaded", ephemeral=True)
            except discord.ExtensionNotFound:
                return await ctx.respond(
                    f"No cog found by the name: {cog}", ephemeral=True
                )
            except:
                return await ctx.respond(f"Something went wrong", ephemeral=True)

            self.bot.load_extension(f"Resolute.cogs.{cog}")
            await ctx.respond(f"Cog {cog} reloaded")

    @commands.group(hidden=True, invoke_without_command=True)
    @commands.check(is_owner)
    async def admin(self, ctx: discord.ApplicationContext):
        await ctx.send("Send a subcommand")

    @admin.command(hidden=True, name="eval")
    @commands.check(is_owner)
    async def admin_eval(self, ctx: discord.ApplicationContext, *, body: str):
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
        }

        def _cleanup_code(content):
            """Automatically removes code blocks from the code."""
            # remove ```py\n```
            if content.startswith("```") and content.endswith("```"):
                return "\n".join(content.split("\n")[1:-1])

            # remove `foo`
            return content.strip("` \n")

        env.update(globals())
        body = _cleanup_code(body)
        stdout = io.StringIO()

        to_compile = "async def func():\n{}".format(textwrap.indent(body, "  "))

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send("```py\n{}: {}\n```".format(e.__class__.__name__, e))

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send("```py\n{}{}\n```".format(value, traceback.format_exc()))
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send("```py\n{}\n```".format(value))
            else:
                await ctx.send("```py\n{}{}\n```".format(value, ret))

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

    @tasks.loop(hours=24)
    async def check_financials(self):
        fin = await Financial.get_financial_data(self.bot)
        current_time = datetime.datetime.now(datetime.timezone.utc)

        if fin.last_reset is None or fin.last_reset.month != current_time.month:
            begin_month = current_time.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            store_items = await Store.get_items(self.bot)

            fin.last_reset = current_time
            goal = fin.monthly_goal

            goal -= fin.adjusted_total

            if goal > 0:
                fin.reserve = max(fin.reserve - goal, 0)
            fin.monthly_total = 0
            fin.month_count += 1

            for entitlement in await self.bot.entitlements(
                exclude_ended=True, limit=None, after=begin_month
            ).flatten():
                entitlement: discord.Entitlement

                if entitlement.type in [
                    discord.EntitlementType.application_subscription,
                    discord.EntitlementType.premium_subscription,
                ]:
                    if store := next(
                        (s for s in store_items if s.sku == entitlement.sku_id), None
                    ):
                        fin.monthly_total += store.user_cost

                        if fin.adjusted_total > fin.monthly_goal:
                            fin.reserve += max(
                                0,
                                min(
                                    store.user_cost,
                                    fin.adjusted_total - fin.monthly_goal,
                                ),
                            )

            await fin.update()
            await RefDashboard.update_financial_dashboards(self.bot)
            log.info("Finanical month reset")
