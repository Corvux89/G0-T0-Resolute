import asyncio
import datetime
import io
import logging
import os
import re

import chat_exporter
import discord
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from texttable import Texttable

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import ADMIN_GUILDS
from Resolute.helpers.dashboards import update_financial_dashboards
from Resolute.helpers.general_helpers import is_admin, is_owner
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.views.admin import AdminMenuUI
from Resolute.models.views.automation_request import AutomationRequestView

log = logging.getLogger(__name__)

def setup(bot: G0T0Bot):
    bot.add_cog(Admin(bot))


class Admin(commands.Cog):
    '''
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
    '''
    bot: G0T0Bot  
    admin_commands = discord.SlashCommandGroup("admin", "Bot administrative commands", guild_ids=ADMIN_GUILDS)

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

    @admin_commands.command(
        name="admin",
        description="Main administration command"
    )
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
        description="Reloads either a specific cog, refresh DB information, or reload everything"
    )
    @commands.check(is_owner)
    async def reload_cog(self, ctx: G0T0Context,
                         cog: discord.Option(discord.SlashCommandOptionType(3), description="Cog name, ALL, or DB", required=True)):
        """
        Used to reload a cog, refresh DB information, or reload all cogs and DB information

        :param ctx: Context
        :param cog: cog to reload, SHEET to reload sheets, ALL to reload all
        """
        await ctx.defer()

        if str(cog).upper() == 'ALL':
            for file_name in os.listdir('./Resolute/cogs'):
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
            except discord.ExtensionNotLoaded:
                return await ctx.respond(f'Cog was already unloaded', ephemeral=True)
            except discord.ExtensionNotFound:
                return await ctx.respond(f'No cog found by the name: {cog}', ephemeral=True)
            except:
                return await ctx.respond(f'Something went wrong', ephemeral=True)

            self.bot.load_extension(f'Resolute.cogs.{cog}')
            await ctx.respond(f'Cog {cog} reloaded')

    @commands.command(name="stop")
    @commands.check(is_owner)
    async def stop(self, ctx: G0T0Context):
        exit()
    
    @commands.command(name="dev")
    @commands.check(is_admin)
    async def dev(self, ctx: G0T0Context):
        transcript = await chat_exporter.export(ctx.channel,
                                                guild=ctx.guild,
                                                bot=self.bot)
        
        if transcript is None:
            return
        transcript_file = discord.File(io.BytesIO(transcript.encode()),
                                       filename=f"transcript-{ctx.channel.name}.html")

        text = BeautifulSoup(transcript, "html.parser")

        ems = text.find_all("em")

        ems.extend(text.find_all(class_="chatlog__markdown-preserve"))

        stats = {}

        words = 0
        lines = 0
        characters = 0
        count = 0

        def name(s):
            match = re.search(r"\[\d+\]\s+([^/]+)", s)
            return match.group(1).strip() if match else s

        for tag in ems:
            words += len(tag.text.split())
            lines += max(tag.text.count("\n"), 1)
            characters += len(tag.text)
            message = tag.find_parent(class_="chatlog__message")
            header = tag.find_previous(class_="chatlog__header")
            group = tag.find_parent(class_="chatlog__message-group")
            if author:= message.find(class_="chatlog__author-name") or (group and (author := group.find(class_="chatlog__author-name"))) or (author := message.find_previous(class_="chatlog__author-name")) or (header and (author := header.find(class_="chatlog__author-name"))):
                author_name = name(author.text)
                if author_name not in stats: 
                    stats[author_name] = {
                        "names": [],
                        "count": 0,
                        "words": 0,
                        "lines": 0,
                        "characters": 0
                    }

                stats[author_name]["words"] += len(tag.text.split())
                stats[author_name]["lines"] += max(tag.text.count("\n"), 1)
                stats[author_name]["characters"] += len(tag.text)
                if author.text not in stats[author_name]["names"]:
                    stats[author_name]["names"].append(author.text)
            else:
                print("no author found?")


        # Prep Data
        for key, values in stats.items():
            for author_name in values['names']:
                author_tags = text.find_all(lambda t: t.has_attr('title') and author_name in t['title'])
                count += len(author_tags)
                values["count"] += len(author_tags)

            
        stat_list = [(key, f"{values['words']:,}", f"{values['lines']:,}", f"{values['characters']:,}", f"{values['count']:,}") for key, values in stats.items()]
        stat_list = sorted(stat_list, key=lambda x: x[0])

        stat_list.append(("Total", f"{words:,}", f"{lines:,}", f"{characters:,}", f"{count:,}"))


        # TextTable
        table = Texttable()
        table.set_cols_align(['l', 'r', 'r', 'r', 'r'])
        table.set_cols_valign(['m', 'm', 'm', 'm', 'm'])
        table.header(['Name', '# Words', '# Lines', '# Chars', '# Posts'])
        table.add_rows(stat_list, header=False)

        await ctx.send(file=transcript_file)
        await ctx.send(f"```{table.draw()}```")
       

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
        fin = await self.bot.get_financial_data()
        current_time = datetime.datetime.now(datetime.timezone.utc)

        if fin.last_reset is None or fin.last_reset.month != current_time.month:
            fin.last_reset = current_time
            goal = fin.monthly_goal

            goal -= fin.adjusted_total

            if goal > 0:
                fin.reserve = max(fin.reserve - goal, 0)
            fin.monthly_total = 0
            fin.month_count += 1
            await fin.update()
            await update_financial_dashboards(self.bot)
            log.info("Finanical month reset")

