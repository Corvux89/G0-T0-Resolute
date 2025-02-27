import logging
from timeit import default_timer as timer

import discord
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import DASHBOARD_REFRESH_INTERVAL, ZWSP3
from Resolute.helpers.dashboards import update_dashboard
from Resolute.models.embeds.dashboards import RPDashboardEmbed
from Resolute.models.objects.dashboards import (
    RefDashboard,
    RPDashboardCategory,
)
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.views.dashboards import DashboardSettingsUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Dashboards(bot))


class Dashboards(commands.Cog):
    """
    Cog for managing dashboards in the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        dashboard_commands (SlashCommandGroup): Group of slash commands for dashboard management.
    Methods:
        __init__(bot):
            Initializes the Dashboards cog.
        on_compendium_loaded():
            Listener for the 'compendium_loaded' event. Starts the dashboard update loop if not already running.
        on_message(message: Message):
            Listener for the 'message' event. Updates the dashboard based on the message content and channel.
        dashboard_manage(ctx: ApplicationContext):
            Command to manage dashboards. Sends the dashboard settings UI to the user.
        strip_field(str) -> int:
            Strips unnecessary characters from a string and converts it to an integer.
        update_dashboards():
            Task that periodically updates the dashboards.
    """

    bot: G0T0Bot
    dashboard_commands = discord.SlashCommandGroup(
        "dashboard", "Dashboard commands", guild_only=True
    )

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        log.info(f"Cog 'Dashboards' loaded")

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        """
        Asynchronous method that is called when the compendium is loaded.
        This method checks if the `update_dashboards` task is running. If it is not running,
        it logs a message indicating that dashboards will be reloaded at a specified interval
        and starts the `update_dashboards` task.
        Returns:
            None
        """
        if not self.update_dashboards.is_running():
            log.info(
                f"Reloading dashboards every {DASHBOARD_REFRESH_INTERVAL} minutes."
            )
            await self.update_dashboards.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handles incoming messages and updates the dashboard accordingly.
        This method is triggered whenever a message is sent in a channel. It checks if the message is in a text channel
        that belongs to a category associated with a dashboard. If so, it updates the dashboard based on the content of the message.
        Args:
            message (Message): The message object representing the incoming message.
        Returns:
            None
        """
        if (
            hasattr(self.bot, "db")
            and hasattr(message.channel, "category_id")
            and (category_channel_id := message.channel.category_id)
            and message.channel.type == discord.ChannelType.text
        ):
            dashboard = await self.bot.get_dashboard_from_category(category_channel_id)

            if not dashboard or message.channel.id in dashboard.excluded_channel_ids:
                return

            post_message = await dashboard.get_pinned_post()

            if isinstance(post_message, bool):
                return

            if not post_message or not post_message.pinned:
                return await dashboard.delete()

            guild = await self.bot.get_player_guild(message.guild.id)

            if dashboard.dashboard_type.value.upper() == "RP":
                embed = post_message.embeds[0]

                staff_field = RPDashboardCategory(
                    title="Archivist",
                    name="<:pencil:989284061786808380> -- Awaiting Archivist",
                    channels=[
                        self.bot.get_channel(self.strip_field(x))
                        for x in [
                            x.value if "Archivist" in x.name else ""
                            for x in embed.fields
                        ][0].split("\n")
                        if x != ""
                    ],
                )
                available_field = RPDashboardCategory(
                    title="Available",
                    name="<:white_check_mark:983576747381518396> -- Available",
                    channels=[
                        self.bot.get_channel(self.strip_field(x))
                        for x in [
                            x.value for x in embed.fields if "Available" in x.name
                        ][0].split("\n")
                        if x != ""
                    ],
                )

                unavailable_field = RPDashboardCategory(
                    title="Unavailable",
                    name="<:x:983576786447245312> -- Unavailable",
                    channels=[
                        self.bot.get_channel(self.strip_field(x))
                        for x in [
                            x.value for x in embed.fields if "Unavailable" in x.name
                        ][0].split("\n")
                        if x != ""
                    ],
                )

                all_fields = [staff_field, available_field, unavailable_field]
                node = ""
                update = False

                for field in all_fields:
                    if message.channel in field.channels:
                        node = field.title
                        field.channels.remove(message.channel)

                if not message.content or message.content in [
                    "```\n​\n```",
                    "```\n \n```",
                ]:
                    available_field.channels.append(message.channel)
                    update = True if available_field.title != node else False
                elif guild.staff_role and guild.staff_role.mention in message.content:
                    staff_field.channels.append(message.channel)
                    update = True if staff_field.title != node else False
                else:
                    unavailable_field.channels.append(message.channel)
                    update = True if unavailable_field.title != node else False

                all_fields = [
                    f
                    for f in all_fields
                    if len(f.channels) > 0 or f.title != "Archivist"
                ]

                if update:
                    return await post_message.edit(
                        content="",
                        embed=RPDashboardEmbed(
                            all_fields, message.channel.category.name
                        ),
                    )

    @dashboard_commands.command(
        name="manage",
        description="Manage dashboards",
    )
    async def dashboard_manage(self, ctx: G0T0Context):
        """
        Manages the dashboard settings for the user.
        This asynchronous method creates a new instance of `DashboardSettingsUI`
        with the bot and the author from the context, sends the UI to the context,
        and then deletes the context message.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
        """
        ui = DashboardSettingsUI.new(self.bot, ctx.author)
        await ui.send_to(ctx)
        await ctx.delete()

    def strip_field(self, str) -> int:
        if str.replace(" ", "") == ZWSP3.replace(" ", "") or str == "":
            return
        return int(str.replace("\u200b", "").replace("<#", "").replace(">", ""))

    # --------------------------- #
    # Tasks
    # --------------------------- #
    @tasks.loop(minutes=DASHBOARD_REFRESH_INTERVAL)
    async def update_dashboards(self):
        """
        Asynchronously updates the channel status dashboards.
        This method acquires a database connection, retrieves dashboard data,
        updates each dashboard, and logs the time taken for the update process.
        Steps:
        1. Start a timer to measure the update duration.
        2. Acquire a database connection from the bot's connection pool.
        3. Execute the `get_dashboards` query to retrieve dashboard data.
        4. For each row in the query result:
            a. Load the row data into a `RefDashboard` object using `RefDashboardSchema`.
            b. Update the dashboard using the `update_dashboard` function.
        5. Stop the timer and log the duration of the update process.
        Returns:
            None
        """
        start = timer()

        rows = await self.bot.query(
            RefDashboard.ref_dashboard_table.select(), QueryResultType.multiple
        )

        for row in rows:
            dashboard: RefDashboard = RefDashboard.RefDashboardSchema(self.bot).load(
                row
            )
            await update_dashboard(self.bot, dashboard)

        # async with self.bot.db.acquire() as conn:
        #     async for row in conn.execute(get_dashboards()):
        #         dashboard: RefDashboard = RefDashboardSchema(self.bot).load(row)
        #         await update_dashboard(self.bot, dashboard)
        end = timer()
        log.info(
            f"DASHBOARD: Channel status dashboards updated in [ {end - start:.2f} ]s"
        )
