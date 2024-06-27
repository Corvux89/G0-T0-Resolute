import random
import discord
import logging
import asyncio

from datetime import datetime, timezone
from discord.ext import commands, tasks
from discord import SlashCommandGroup, ApplicationContext
from timeit import default_timer as timer

import discord.ext.tasks

from Resolute.bot import G0T0Bot
from Resolute.models.categories import Activity
from Resolute.helpers.guilds import get_guilds_with_reset, get_guild, update_guild
from Resolute.helpers.guilds import delete_weekly_stipend, get_guild_stipends
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player
from Resolute.models.embeds.guilds import ResetEmbed
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import reset_div_cc
from Resolute.models.views.guild_settings import GuildSettingsUI
import discord.ext

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))


class Guilds(commands.Cog):
    bot: G0T0Bot
    guilds_commands = SlashCommandGroup("guild", "Commands related to guild specific settings")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Guilds\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        if not self.schedule_weekly_reset.is_running():
            asyncio.ensure_future(self.schedule_weekly_reset.start())
    
    @guilds_commands.command(
            name="settings",
            description="Modify the current guild/server settings"
    )
    async def guild_settings(self, ctx: ApplicationContext):
        g = await get_guild(self.bot, ctx.guild.id)

        ui = GuildSettingsUI.new(self.bot, ctx.author, g)

        await ui.send_to(ctx)
        return await ctx.delete()


    @guilds_commands.command(
        name="weekly_reset",
        description="Performs a weekly reset for the server"
    )
    async def guild_weekly_reset(self, ctx: ApplicationContext):
        """
        Manually trigger the weekly reset for a server.

        :param ctx: Context
        """
        await ctx.defer()

        g: PlayerGuild = await get_guild(self.bot, ctx.guild.id)

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

        # Reset weekly stats
        await update_guild(self.bot.db, g)

        # Reset Player CC's     
        async with self.bot.db.acquire() as conn:
            await conn.execute(reset_div_cc(g.id))
        
        # Stipends
        if activity := self.bot.compendium.get_object(Activity, "STIPEND"):
            leadership_stipend_players = set()

            for stipend in stipends:
                if stipend_role := self.bot.get_guild(g.id).get_role(stipend.role_id):
                    members = stipend_role.members
                    if stipend.leadership:
                        members = list(filter(lambda m: m.id not in leadership_stipend_players, members))
                        leadership_stipend_players.update(m.id for m in stipend_role.members)

                    player_list = await asyncio.gather(*(get_player(self.bot, m.id, g.id) for m in members))
                    
                    for player in player_list:
                        stipend_task.append(create_log(self.bot, self.bot.user, g, activity, player,
                                                       notes=stipend.reason or "Weekly Stipend",
                                                       cc=stipend.amount))
                    
                else:
                    await delete_weekly_stipend(self.bot.db, stipend)

        await asyncio.gather(*stipend_task)                 

        end = timer()

        # Announce we're all done!
        if announcement_channel := discord.utils.get(guild.channels, name="announcements"):
            try:
                if g.ping_announcement == True and (citizen_role := discord.utils.get(guild.roles, name="Citizen")) and (acolyte_role := discord.utils.get(guild.roles, name="Acolyte")):
                    await announcement_channel.send(embed=ResetEmbed(g, end-start), content=f"{citizen_role.mention}{acolyte_role.mention}")
                else:
                    await announcement_channel.send(embed=ResetEmbed(g, end-start))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"WEEKLY RESET: Error sending message to announcements channel in "
                              f"{self.bot.get_guild(g.id).name} [ {g.id} ]")
                else:
                    log.error(error)

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
