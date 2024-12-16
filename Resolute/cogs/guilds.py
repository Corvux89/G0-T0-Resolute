import asyncio
import logging
import random
from datetime import datetime, timezone
from timeit import default_timer as timer

import discord
import discord.ext
import discord.ext.tasks
from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.helpers import (confirm, create_log, delete_weekly_stipend,
                              get_guild, get_guild_stipends,
                              get_guilds_with_reset, get_player, get_webhook,
                              is_admin, update_activity_points, update_guild)
from Resolute.models.categories import Activity
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

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db") and ctx.guild:
            guild = await get_guild(self.bot, ctx.guild.id)
            if npc := next((npc for npc in guild.npcs if npc.key == ctx.invoked_with), None):
                user_roles = [role.id for role in ctx.author.roles]
                if bool(set(user_roles) & set(npc.roles)) or is_admin(ctx):
                    player = await get_player(self.bot, ctx.author.id, ctx.guild.id)
                    content = ctx.message.content.replace(f'>{npc.key}', '')
                    await player.update_post_stats(self.bot, npc, content)
                    await player.update_command_count(self.bot, "npc")
                    webhook = await get_webhook(ctx.channel)
                    await webhook.send(username=npc.name,
                                    avatar_url=npc.avatar_url if npc.avatar_url else None,
                                    content=content)
                    await update_activity_points(self.bot, player, guild)
                    await ctx.message.delete()
    
    @guilds_commands.command(
            name="settings",
            description="Modify the current guild/server settings"
    )
    @commands.check(is_admin)
    async def guild_settings(self, ctx: ApplicationContext):
        g = await get_guild(self.bot, ctx.guild.id)

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

        g: PlayerGuild = await get_guild(self.bot, ctx.guild.id)

        conf = await confirm(ctx, f"Are you sure you want to manually do a weekly reset? (Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f"Times oud waiting for a response or invalid response.", delete_after=10)
        elif not conf:
            return await ctx.respond(f"Ok, cancelling.", delete_after=10)

        await self.perform_weekly_reset(g)
        return await ctx.respond("Weekly reset manually completed")

    async def perform_weekly_reset(self, g: PlayerGuild):
        # Setup
        start = timer()
        player_cc = 0
        stipends = await get_guild_stipends(self.bot.db, g.id)
        guild = self.bot.get_guild(g.id)   
        stipend_task = []

        # Guild updates
        g.weeks += 1
        g._last_reset = datetime.now(timezone.utc)
        if g.server_date and g.server_date is not None:
            g.server_date += random.randint(13, 16)
        

        # Reset Player CC's and 
        async with self.bot.db.acquire() as conn:
            await conn.execute(reset_div_cc(g.id))
        
        # Stipends
        leadership_stipend_players = set()

        for stipend in stipends:
            if stipend_role := self.bot.get_guild(g.id).get_role(stipend.role_id):
                members = stipend_role.members
                if stipend.leadership:
                    members = list(filter(lambda m: m.id not in leadership_stipend_players, members))
                    leadership_stipend_players.update(m.id for m in stipend_role.members)

                player_list = await asyncio.gather(*(get_player(self.bot, m.id, g.id) for m in members))
                
                for player in player_list:
                    stipend_task.append(create_log(self.bot, self.bot.user, "STIPEND", player,
                                                    notes=stipend.reason or "Weekly Stipend",
                                                    cc=stipend.amount))
                
            else:
                await delete_weekly_stipend(self.bot.db, stipend)

        await asyncio.gather(*stipend_task)                 

        end = timer()

        # Announce we're all done!
        if g.announcement_channel:
            try:
                if g.ping_announcement == True and g.entry_role and g.member_role:
                    await g.announcement_channel.send(embed=ResetEmbed(g, end-start), content=f"{g.entry_role.mention}{g.member_role.mention}")
                else:
                    await g.announcement_channel.send(embed=ResetEmbed(g, end-start))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"WEEKLY RESET: Error sending message to announcements channel in "
                              f"{self.bot.get_guild(g.id).name} [ {g.id} ]")
                else:
                    log.error(error)
                    
        # Cleanup
        g.weekly_announcement = []
        g.ping_announcement = False

        await update_guild(self.bot, g)

        

    # --------------------------- #
    # Task Helpers
    # --------------------------- #
    @tasks.loop(minutes=5)
    async def schedule_weekly_reset(self):
        hour = datetime.now(timezone.utc).hour
        day = datetime.now(timezone.utc).weekday()
        # log.info(f"GUIlDS: Checking reset for day {day} and hour {hour}")
        guild_list = await get_guilds_with_reset(self.bot, day, hour)
        for guild in guild_list:
            await self.perform_weekly_reset(guild)
