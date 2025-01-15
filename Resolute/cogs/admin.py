import asyncio
import datetime
import logging
from os import listdir

from discord import (ApplicationContext, ExtensionNotFound, ExtensionNotLoaded, Option, SlashCommandGroup, Embed)
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.constants import ADMIN_GUILDS
from Resolute.helpers.dashboards import update_financial_dashboards
from Resolute.helpers.financial import get_financial_data, update_financial_data
from Resolute.helpers.general_helpers import is_admin, is_owner
from Resolute.helpers.store import get_store_items
from Resolute.models.objects.guilds import PlayerGuild
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
        if not self.reload_category_task.is_running():
            asyncio.ensure_future(self.reload_category_task.start())

        if not self.check_financials.is_running():
            asyncio.ensure_future(self.check_financials.start())

    @commands.Cog.listener()
    async def on_refresh_guild_cache(self, guild: PlayerGuild):
        guild = await guild.fetch()
        self.bot.player_guilds[str(guild.id)] = guild

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
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)
        modal = AutomationRequestView(player.guild)
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

    @commands.command(name="dev")
    async def dev(self, ctx: ApplicationContext):
        now = datetime.datetime.now(datetime.timezone.utc)
        entitlements = await self.bot.fetch_entitlements()
        store_items = await get_store_items(self.bot)    
        # entitlements = [e for e in entitlements if e.starts_at.year == now.year and e.starts_at.month == now.month]

        embed = Embed(title="Supporters")

        users = {}

        for e in entitlements:
            if store := next((s for s in store_items if s.sku == e.sku_id), None):
                if e.user_id not in users:
                    users[e.user_id] = {e.sku_id: 1}
                else:
                    if e.sku_id not in users[e.user_id]:
                        users[e.user_id][e.sku_id] = 1
                    else:
                        users[e.user_id][e.sku_id] += 1

        
        for user_id in users:
            user = ctx.guild.get_member(user_id)
            user_str = ""
            total = 0

            for sku, count in users[user_id].items():
                if store := next((s for s in store_items if s.sku == sku), None):
                    cost = store.user_cost * count
                    total += cost
                    user_str += f"{sku} x {count} @ ${store.user_cost:.2f} = ${cost:.2f}\n"

            user_str += f"\n**Total**: ${total:.2f}"


            embed.add_field(name=f"{user.display_name if user else 'Not Found'}",
                            value=user_str,
                            inline=False)
            
        return await ctx.send(embed=embed)


        

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
        fin = await get_financial_data(self.bot)
        current_time = datetime.datetime.now(datetime.timezone.utc)

        if fin.last_reset is None or fin.last_reset.month != current_time.month:
            fin.last_reset = current_time
            goal = fin.monthly_goal

            goal -= fin.adjusted_total

            if goal > 0:
                fin.reserve = max(fin.reserve - goal, 0)
            fin.monthly_total = 0
            fin.month_count += 1
            await update_financial_data(self.bot, fin)
            await update_financial_dashboards(self.bot)
            log.info("Finanical month reset")

