import logging
import traceback

import discord
from discord.ext import commands
import discord.ext.commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ERROR_CHANNEL
from Resolute.helpers.adventures import get_player_adventures
from Resolute.helpers.appliations import upsert_application
from Resolute.helpers.arenas import get_player_arenas
from Resolute.helpers.general_helpers import process_message
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.players import get_player
from Resolute.models.embeds.events import MemberLeaveEmbed
from Resolute.models.objects.players import upsert_player_query
import discord.ext

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))

class Events(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Events\' loaded')

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        guild = self.bot.get_guild(payload.guild_id)
        # Reference Table Cleanup
        await upsert_application(self.bot.db, payload.user.id)

        # Cleanup Arena Board
        def predicate(message):
            return message.author == payload.user
        
        if arena_board := discord.utils.get(guild.channels, name="arena-board"):
            try:
                await arena_board.purge(check=predicate)
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    pass
                else:
                    log.error(error)
                    
        if exit_channel := discord.utils.get(guild.channels, name="exit"):
            player = await get_player(self.bot, payload.user.id, payload.guild_id)
            player.member = payload.user
            adventures = await get_player_adventures(self.bot, player)
            arenas = await get_player_arenas(self.bot, player)

            try:
                await exit_channel.send(embed=MemberLeaveEmbed(player, adventures, arenas))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                            f"{guild.name} [ {guild.id} ] for {payload.user.display_name} [ {payload.user.id} ]")
        
            

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = await get_guild(self.bot, member.guild.id)

        if (entrance_channel := discord.utils.get(member.guild.channels, name="entrance")) and g.greeting != None and g.greeting != "":
            message = process_message(g.greeting, member.guild, member)
            await entrance_channel.send(message)

    @commands.Cog.listener()
    async def on_command(self, ctx: discord.ApplicationContext):
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
            await player.update_command_count(self.bot, str(ctx.command))

    
    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        try:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])
            if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
                player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
                await player.update_command_count(self.bot, str(ctx.command))

            log.info(f"cmd: chan {ctx.channel} [{ctx.channel.id}], serv: {ctx.guild.name} [{ctx.guild.id}], "
                     f"auth: {ctx.user} [{ctx.user.id}]: {ctx.command} {params}")
        except AttributeError:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])
            if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
                player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
                await player.update_command_count(self.bot, str(ctx.command))

            log.info(f"Command in DM with {ctx.user} [{ctx.user.id}]: {ctx.command} {params}")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error):
        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, discord.errors.CheckFailure):
            return await ctx.respond(f'You do not have required permissions for `{ctx.command}`', ephemeral=True)
    
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])

            out_str = f"Error in command: cmd: chan {ctx.channel} [{ctx.channel.id}], {f'serv: {ctx.guild} [{ctx.guild.id}]' if ctx.guild else ''} auth: {ctx.user} [{ctx.user.id}]: {ctx.command} {params}\n```"\
                      f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"\
                      f"```"
            
            # At this time...I don't want DM Errors...cause those are going to happen a lot for now. 
            if ERROR_CHANNEL and ctx.guild:
                try:
                    await ctx.bot.get_channel(int(ERROR_CHANNEL)).send(out_str)
                except:
                    log.error(out_str)
            else:
                log.error(out_str)

        try:
            if hasattr(ctx, "bot") and not hasattr(ctx.bot, "db"):
                return await ctx.respond(f"Try again in a few seconds. I'm not fully awake yet.", ephemeral=True)
            
            if not ctx.guild:
                return await ctx.respond(f"This command isn't supported in direct messages.", ephemeral=True)    

            return await ctx.respond(f'Something went wrong. Let us know if it keeps up!', ephemeral=True)
        except:
            log.warning('Unable to respond')

    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: discord.ApplicationContext, error):
        if hasattr(ctx.command, 'on_error') or isinstance(error, discord.ext.commands.CommandNotFound):
            return

        if isinstance(error, discord.errors.CheckFailure):
            return await ctx.message.respond(f'You do not have required permissions for `{ctx.command}`', ephemeral=True)
    
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            out_str = f"Error in command: cmd: chan {ctx.channel} [{ctx.channel.id}], {f'serv: {ctx.guild} [{ctx.guild.id}]' if ctx.guild else ''} auth: {ctx.author} [{ctx.author.id}]: {ctx.command}\n```"\
                      f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"\
                      f"```"
            
            # At this time...I don't want DM Errors...cause those are going to happen a lot for now. 
            if ERROR_CHANNEL and ctx.guild:
                try:
                    await ctx.bot.get_channel(int(ERROR_CHANNEL)).send(out_str)
                except:
                    log.error(out_str)
            else:
                log.error(out_str)

        try:
            if hasattr(ctx, "bot") and not hasattr(ctx.bot, "db"):
                return await ctx.message.respond(f"Try again in a few seconds. I'm not fully awake yet.", ephemeral=True)
            
            if not ctx.guild:
                return await ctx.message.respond(f"This command isn't supported in direct messages.", ephemeral=True)    

            return await ctx.message.respond(f'Something went wrong. Let us know if it keeps up!', ephemeral=True)
        except:
            log.warning('Unable to respond')