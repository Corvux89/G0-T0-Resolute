from asyncio import ensure_future, gather
import logging
import random
from datetime import datetime, timedelta, timezone
from timeit import default_timer as timer

from discord import ApplicationContext, HTTPException, Message, SlashCommandGroup, Thread
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers.characters import handle_character_mention
from Resolute.helpers.general_helpers import confirm, get_webhook, is_admin, split_content
from Resolute.helpers.logs import update_activity_points
from Resolute.models.embeds.guilds import ResetEmbed
from Resolute.models.objects.guilds import GuildSchema, PlayerGuild, get_guilds_with_reset_query
from Resolute.models.objects.players import reset_div_cc
from Resolute.models.views.guild_settings import GuildSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))


class Guilds(commands.Cog):
    """
    A Discord Cog that handles guild-specific commands and events for the G0T0Bot.
    Attributes:
        bot (G0T0Bot): The instance of the bot.
        guilds_commands (SlashCommandGroup): A group of slash commands related to guild settings.
    Methods:
        __init__(bot):
            Initializes the Guilds cog with the given bot instance.
        on_compendium_loaded():
            Event listener that starts scheduled tasks when the compendium is loaded.
        on_command_error(ctx, error):
            Event listener that handles command errors, particularly for NPC commands.
        guild_settings(ctx):
            Command to modify the current guild/server settings.
        guild_weekly_reset(ctx):
            Command to manually trigger the weekly reset for a server.
        guild_announcements(ctx):
            Command to manually push announcements to the guild's announcement channel.
        push_announcements(guild, complete_time=None, **kwargs):
            Sends announcements to the guild's announcement channel.
        perform_weekly_reset(g):
            Performs the weekly reset for the given guild, including updating guild data and sending announcements.
        schedule_weekly_reset():
            Scheduled task that performs weekly resets for guilds at specific times.
        cleanup_rp_posts():
            Scheduled task that cleans up roleplay posts older than 72 hours in the guild's RP post channel.
    """
    bot: G0T0Bot
    guilds_commands = SlashCommandGroup("guild", "Commands related to guild specific settings", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Guilds\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        """
        Event handler that is called when the compendium is loaded.
        This method ensures that the weekly reset and RP post cleanup tasks are started
        if they are not already running.
        Tasks:
            - schedule_weekly_reset: A task that handles weekly resets.
            - cleanup_rp_posts: A task that cleans up role-playing posts.
        Note:
            This method uses asyncio to ensure that the tasks are started asynchronously.
        """

        if not self.schedule_weekly_reset.is_running():
            ensure_future(self.schedule_weekly_reset.start())

        if not self.cleanup_rp_posts.is_running():
            ensure_future(self.cleanup_rp_posts.start())

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db") and ctx.guild:
            guild = await self.bot.get_player_guild(ctx.guild.id)
            if npc := next((npc for npc in guild.npcs if npc.key == ctx.invoked_with), None):
                user_roles = [role.id for role in ctx.author.roles]
                if bool(set(user_roles) & set(npc.roles)) or await is_admin(ctx):
                    player = await self.bot.get_player(ctx.author.id, ctx.guild.id)
                    content = ctx.message.content.replace(f'>{npc.key}', '')
                    content = await handle_character_mention(ctx, content)

                    await player.update_command_count("npc")
                    webhook = await get_webhook(ctx.channel)
                    chunks = split_content(content)
                    
                    for chunk in chunks:
                        if isinstance(ctx.channel, Thread):
                            await webhook.send(username=npc.name,
                                                avatar_url=npc.avatar_url if npc.avatar_url else None,
                                                content=chunk,
                                                thread=ctx.channel)
                        else:
                            await webhook.send(username=npc.name,
                                            avatar_url=npc.avatar_url if npc.avatar_url else None,
                                            content=chunk)
                        
                        if not guild.is_dev_channel(ctx.channel):
                            await player.update_post_stats(npc, ctx.message, content=chunk)
                            if len(chunk) > ACTIVITY_POINT_MINIMUM:
                                await update_activity_points(self.bot, player)
                    await ctx.message.delete()
    
    @guilds_commands.command(
            name="settings",
            description="Modify the current guild/server settings"
    )
    @commands.check(is_admin)
    async def guild_settings(self, ctx: ApplicationContext):
        """
        Handles the guild settings command.
        This method retrieves the guild settings for the guild associated with the given context,
        creates a new GuildSettingsUI instance, and sends it to the context. Finally, it deletes
        the context message.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
        Returns:
            Coroutine: A coroutine that deletes the context message.
        """
        g = await self.bot.get_player_guild(ctx.guild.id)

        ui = GuildSettingsUI.new(self.bot, ctx.author, g)

        await ui.send_to(ctx)
        return await ctx.delete()


    @guilds_commands.command(
        name="weekly_reset",
        description="Performs a weekly reset for the server"
    )
    @commands.check(is_admin)
    async def guild_weekly_reset(self, ctx: ApplicationContext):
        """
        Manually performs a weekly reset for the guild.
        This method defers the context, retrieves the player's guild, and asks for confirmation
        from the user before performing the weekly reset. If the user confirms, the weekly reset
        is performed; otherwise, the operation is cancelled.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
        Returns:
            None
        """
        await ctx.defer()

        g: PlayerGuild = await self.bot.get_player_guild(ctx.guild.id)

        conf = await confirm(ctx, f"Are you sure you want to manually do a weekly reset? (Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f"Times oud waiting for a response or invalid response.", delete_after=10)
        elif not conf:
            return await ctx.respond(f"Ok, cancelling.", delete_after=10)

        await self.perform_weekly_reset(g)
        return await ctx.respond("Weekly reset manually completed")
    
    @guilds_commands.command(
        name="send_announcements",
        description="Send announcements only"
    )
    @commands.check(is_admin)
    async def guild_announcements(self, ctx: ApplicationContext):
        """
        Manually push guild announcements.
        This method allows a user to manually trigger the pushing of announcements for a guild.
        It first defers the response, then retrieves the player's guild information.
        The user is prompted to confirm the action. If the user confirms, the announcements are pushed,
        the guild information is updated, and the guild cache is refreshed.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
        Returns:
            None
        """
        await ctx.defer()

        g: PlayerGuild = await self.bot.get_player_guild(ctx.guild.id)

        conf = await confirm(ctx, f"Are you sure you want to manually push announcements? (Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f"Times oud waiting for a response or invalid response.", delete_after=10)
        elif not conf:
            return await ctx.respond(f"Ok, cancelling.", delete_after=10)
        
        g = await self.push_announcements(g, None, title="Announcements")
        await g.upsert()
        self.bot.dispatch("refresh_guild_cache", g)
        return await ctx.respond("Announcements manually completed")
        
    async def push_announcements(self, guild: PlayerGuild, complete_time: float = None, **kwargs) -> PlayerGuild:
        """
        Sends announcement messages to the guild's announcement channel.
        This function sends announcement messages to the specified guild's announcement channel.
        It creates embeds for the announcements and sends them to the channel. If the guild has
        specified roles for entry and member, it mentions those roles in the announcement.
        Args:
            guild (PlayerGuild): The guild object containing information about the guild.
            complete_time (float, optional): The time when the announcements are complete. Defaults to None.
            **kwargs: Additional keyword arguments for creating the announcement embeds.
        Returns:
            PlayerGuild: The updated guild object with cleared weekly announcements and reset ping_announcement flag.
        Raises:
            HTTPException: If there is an error sending the message to the announcement channel.
            Exception: For any other exceptions that occur during the process.
        """
        if guild.announcement_channel:
            try:
                embeds = ResetEmbed.chunk_announcements(guild, complete_time, **kwargs)
                if guild.ping_announcement == True and guild.entry_role and guild.member_role:
                    await guild.announcement_channel.send(embeds=embeds, content=f"{guild.entry_role.mention}{guild.member_role.mention}")
                else:
                    await guild.announcement_channel.send(embeds=embeds)
                
                guild.weekly_announcement = []
                guild.ping_announcement = False
            except Exception as error:
                if isinstance(error, HTTPException):
                    log.error(f"WEEKLY RESET: Error sending message to announcements channel in "
                              f"{guild.guild.name} [ {guild.id} ]")
                else:
                    log.error(error)

        return guild

    async def perform_weekly_reset(self, g: PlayerGuild):
        """
        Perform the weekly reset for a given player guild.
        This method updates the guild's week count, resets player currency and activity points,
        and processes stipends for guild members.
        Args:
            g (PlayerGuild): The player guild to perform the weekly reset on.
        Returns:
            None
        """
        # Setup
        start = timer()
        stipend_task = []

        # Guild updates
        g.weeks += 1
        g._last_reset = datetime.now(timezone.utc)
        if g.server_date and g.server_date is not None:
            g.server_date += random.randint(13, 16)
        

        # Reset Player CC's and Activity Points
        async with self.bot.db.acquire() as conn:
            await conn.execute(reset_div_cc(g.id))
        
        # Stipends
        leadership_stipend_players = set()

        for stipend in g.stipends:
            if stipend_role := self.bot.get_guild(g.id).get_role(stipend.role_id):
                members = stipend_role.members
                if stipend.leadership:
                    members = list(filter(lambda m: m.id not in leadership_stipend_players, members))
                    leadership_stipend_players.update(m.id for m in stipend_role.members)

                player_list = await gather(*(self.bot.get_player(m.id, g.id) for m in members))
                
                for player in player_list:
                    stipend_task.append(self.bot.log(None, player, self.bot.user, "STIPEND",
                                                     notes=stipend.reason or "Weekly Stipend",
                                                     cc=stipend.amount,
                                                     silent=True))                
            else:
                await stipend.delete()

        await gather(*stipend_task)                 

        end = timer()

        # Announce we're all done!
        g = await self.push_announcements(g, end-start)
        await g.upsert()
        self.bot.dispatch("refresh_guild_cache", g)

    # --------------------------- #
    # Private Methods
    # --------------------------- #
    async def _get_guilds_with_reset(self, day: int, hour: int) -> list[PlayerGuild]:
        """
        Retrieve a list of guilds that have a reset scheduled at the specified day and hour.
        Args:
            day (int): The day of the week (0-6) when the reset is scheduled.
            hour (int): The hour of the day (0-23) when the reset is scheduled.
        Returns:
            list[PlayerGuild]: A list of PlayerGuild objects that have a reset scheduled at the specified day and hour.
        """
        async with self.bot.db.acquire() as conn:
            results = await conn.execute(get_guilds_with_reset_query(day, hour))
            rows = await results.fetchall()

        guild_list = [await GuildSchema(self.bot.db, self.bot.get_guild(row["id"])).load(row) for row in rows]

        return guild_list

    # --------------------------- #
    # Task Helpers
    # --------------------------- #
    @tasks.loop(minutes=5)
    async def schedule_weekly_reset(self):
        """
        Schedules and performs a weekly reset for guilds.
        This method checks the current UTC time and day of the week, retrieves a list of guilds
        that are scheduled for a reset at that time, and performs the reset for each guild in the list.
        Returns:
            None
        """
        hour = datetime.now(timezone.utc).hour
        day = datetime.now(timezone.utc).weekday()
        guild_list = await self._get_guilds_with_reset(day, hour)
        for guild in guild_list:
            await self.perform_weekly_reset(guild)

    @tasks.loop(minutes=60)
    async def cleanup_rp_posts(self):
        """
        Asynchronously cleans up role-playing (RP) posts in the designated RP post channels of all guilds.
        This method deletes messages that are older than 72 hours and were sent by bots using webhooks.
        Steps:
        1. Calculate the cutoff time as the current time minus 72 hours.
        2. Iterate through all guilds the bot is a member of.
        3. For each guild, retrieve the PlayerGuild object.
        4. Define a predicate function to identify messages sent by bots using webhooks.
        5. If the guild has an RP post channel, attempt to purge messages that match the predicate and are older than the cutoff time.
        6. Log the number of deleted messages if any were deleted.
        7. Handle and log any exceptions that occur during the purge process.
        Raises:
            HTTPException: If there is an error purging messages in the RP post channel.
            Exception: For any other exceptions that occur during the purge process.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=72)

        for guild in self.bot.guilds:
            g: PlayerGuild = await self.bot.get_player_guild(guild.id)

            def predicate(message: Message):
                return message.author.bot and message.webhook_id is not None

            if g.rp_post_channel:
                try:
                    deleted_messages = await g.rp_post_channel.purge(limit=None, before=cutoff_time, check=predicate)
                    if len(deleted_messages) > 0:
                        log.info(f"RP BOARD: {len(deleted_messages)} message{'s' if len(deleted_messages) > 1 else ''} deleted from {g.rp_post_channel.name} for {g.guild.name} [{g.guild.id}]")
                except Exception as error:
                    if isinstance(error, HTTPException):
                        log.error(f"RP BOARD: Error purging messages in {g.rp_post_channel.name}")
                    else:
                        log.error(error)



