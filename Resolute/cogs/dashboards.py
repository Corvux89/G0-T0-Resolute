import logging
from timeit import default_timer as timer

import discord
import discord.utils
from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.constants import DASHBOARD_REFRESH_INTERVAL, ZWSP3
from Resolute.helpers import (delete_dashboard, get_dashboard_from_category,
                              get_guild, get_pinned_post, update_dashboard)
from Resolute.models.embeds.dashboards import RPDashboardEmbed
from Resolute.models.objects.dashboards import (RefDashboard,
                                                RefDashboardSchema,
                                                RPDashboardCategory,
                                                get_dashboards)
from Resolute.models.views.dashboards import DashboardSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Dashboards(bot))


class Dashboards(commands.Cog):
    bot: G0T0Bot
    dashboard_commands = SlashCommandGroup("dashboard", "Dashboard commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Dashboards\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        log.info(f"Reloading dashboards every {DASHBOARD_REFRESH_INTERVAL} minutes.")
        if not self.update_dashboards.is_running():
            await self.update_dashboards.start()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if hasattr(self.bot, "db") and hasattr(message.channel, "category_id") and (category_channel_id := message.channel.category_id):
            dashboard = await get_dashboard_from_category(self.bot, category_channel_id)

            if not dashboard or message.channel.id in dashboard.excluded_channel_ids:
                return
            
            post_message = await get_pinned_post(self.bot, dashboard)

            if not post_message or not post_message.pinned and post_message is not True:
                return await delete_dashboard(self.bot, dashboard)
            
            guild = await get_guild(self.bot, message.guild.id)
            
            if dashboard.dashboard_type.value.upper() == "RP":
                embed = post_message.embeds[0]

                archivist_field = RPDashboardCategory(title="Archivist",
                                                      name="<:pencil:989284061786808380> -- Awaiting Archivist",
                                                      channels=[self.bot.get_channel(self.strip_field(x))  for x in [x.value if "Archivist" in x.name else "" for x in embed.fields][0].split('\n')])
                available_field = RPDashboardCategory(title="Available",
                                                     name="<:white_check_mark:983576747381518396> -- Available",
                                                     channels=[self.bot.get_channel(self.strip_field(x)) for x in [x.value for x in embed.fields if "Available" in x.name][0].split('\n')])
                
                unavailable_field = RPDashboardCategory(title="Unavailable",
                                                       name="<:x:983576786447245312> -- Unavailable",
                                                       channels=[self.bot.get_channel(self.strip_field(x)) for x in [x.value for x in embed.fields if "Unavailable" in x.name][0].split('\n')])
                
                all_fields = [archivist_field, available_field, unavailable_field]
                node = ""
                update = False

                for field in all_fields:
                    if message.channel in field.channels:
                        node = field.title
                        field.channels.remove(message.channel)

                if not message.content or message.content in ["```\n​\n```", "```\n \n```"]:
                    available_field.channels.append(message.channel)                     
                    update = True if available_field.title != node else False
                elif guild.archivist_role and guild.archivist_role.mention in message.content:
                    archivist_field.channels.append(message.channel)
                    update = True if archivist_field.title != node else False
                else:
                    unavailable_field.channels.append(message.channel)
                    update = True if unavailable_field.title != node else False

                all_fields = [f for f in all_fields if len(f.channels)>0 or f.title != "Archivist"]

                if update:
                    return await post_message.edit(content="", embed=RPDashboardEmbed(all_fields, message.channel.category.name))

    @dashboard_commands.command(
        name="manage",
        description="Manage dashboards",
    )
    async def dashboard_manage(self, ctx: ApplicationContext):
        ui = DashboardSettingsUI.new(self.bot, ctx.author)
        await ui.send_to(ctx)
        await ctx.delete()


    def strip_field(self, str) -> int:
        if str.replace(' ','') == ZWSP3.replace(' ', '') or str == '':
            return
        return int(str.replace('\u200b', '').replace('<#','').replace('>',''))

    # --------------------------- #
    # Tasks
    # --------------------------- #
    @tasks.loop(minutes=DASHBOARD_REFRESH_INTERVAL)
    async def update_dashboards(self):
        start = timer()
        async with self.bot.db.acquire() as conn:
            async for row in conn.execute(get_dashboards()):
                dashboard: RefDashboard = RefDashboardSchema(self.bot.compendium).load(row)
                await update_dashboard(self.bot, dashboard)
        end = timer()
        log.info(f"DASHBOARD: Channel status dashboards updated in [ {end - start:.2f} ]s")