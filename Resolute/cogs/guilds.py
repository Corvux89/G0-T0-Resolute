import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from timeit import default_timer as timer

import discord
import discord.ext
import discord.ext.tasks
from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers.characters import handle_character_mention
from Resolute.helpers.general_helpers import confirm, get_webhook, is_admin, split_content
from Resolute.helpers.guilds import get_guilds_with_reset
from Resolute.helpers.logs import create_log, update_activity_points
from Resolute.models.embeds.guilds import ResetEmbed
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import reset_div_cc
from Resolute.models.views.guild_settings import GuildSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))


class Guilds(commands.Cog):
    bot: G0T0Bot
    guilds_commands = SlashCommandGroup("guild", "Commands related to guild specific settings", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Guilds\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        if not self.schedule_weekly_reset.is_running():
            asyncio.ensure_future(self.schedule_weekly_reset.start())

        if not self.cleanup_rp_posts.is_running():
            asyncio.ensure_future(self.cleanup_rp_posts.start())

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
                        if isinstance(ctx.channel, discord.Thread):
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
        Manually trigger the weekly reset for a server.

        :param ctx: Context
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
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"WEEKLY RESET: Error sending message to announcements channel in "
                              f"{guild.guild.name} [ {guild.id} ]")
                else:
                    log.error(error)

        return guild

    async def perform_weekly_reset(self, g: PlayerGuild):
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

                player_list = await asyncio.gather(*(self.bot.get_player(m.id, g.id) for m in members))
                
                for player in player_list:
                    stipend_task.append(create_log(self.bot, self.bot.user, "STIPEND", player,
                                                    notes=stipend.reason or "Weekly Stipend",
                                                    cc=stipend.amount))
                
            else:
                await stipend.delete()

        await asyncio.gather(*stipend_task)                 

        end = timer()

        # Announce we're all done!
        g = await self.push_announcements(g, end-start)
        await g.upsert()
        self.bot.dispatch("refresh_guild_cache", g)
        

    # --------------------------- #
    # Task Helpers
    # --------------------------- #
    @tasks.loop(minutes=5)
    async def schedule_weekly_reset(self):
        hour = datetime.now(timezone.utc).hour
        day = datetime.now(timezone.utc).weekday()
        guild_list = await get_guilds_with_reset(self.bot, day, hour)
        for guild in guild_list:
            await self.perform_weekly_reset(guild)

    @tasks.loop(minutes=60)
    async def cleanup_rp_posts(self):
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=72)

        for guild in self.bot.guilds:
            g: PlayerGuild = await self.bot.get_player_guild(guild.id)

            def predicate(message: discord.Message):
                return message.author.bot and message.webhook_id is not None

            if g.rp_post_channel:
                try:
                    deleted_messages = await g.rp_post_channel.purge(limit=None, before=cutoff_time, check=predicate)
                    if len(deleted_messages) > 0:
                        log.info(f"RP BOARD: {len(deleted_messages)} message{'s' if len(deleted_messages) > 1 else ''} deleted from {g.rp_post_channel.name} for {g.guild.name} [{g.guild.id}]")
                except Exception as error:
                    if isinstance(error, discord.errors.HTTPException):
                        log.error(f"RP BOARD: Error purging messages in {g.rp_post_channel.name}")
                    else:
                        log.error(error)



