import logging
import traceback

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ERROR_CHANNEL
from Resolute.helpers.adventures import get_player_adventures
from Resolute.helpers.appliations import upsert_application
from Resolute.helpers.arenas import get_player_arenas
from Resolute.helpers.general_helpers import process_message
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.players import get_player
from Resolute.models.embeds.events import MemberLeaveEmbed

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
        member = self.bot.get_guild(payload.guild_id).get_member(payload.user.id)
        # Reference Table Cleanup
        await upsert_application(self.bot.db, member.id)

        # Cleanup Arena Board
        def predicate(message):
            return message.author == member
        
        if arena_board := discord.utils.get(member.guild.channels, name="arena-board"):
            try:
                await arena_board.purge(check=predicate)
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    pass
                else:
                    log.error(error)
        
        if exit_channel := discord.utils.get(member.guild.channels, name="exit"):
            player = await get_player(self.bot, member.id, member.guild.id)
            adventures = await get_player_adventures(self.bot, player)
            arenas = await get_player_arenas(self.bot, player)

            try:
                await exit_channel.send(embed=MemberLeaveEmbed(player, adventures, arenas))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                            f"{member.guild.name} [ {member.guild.id} ] for {member.name} [ {member.id} ]")
        
            

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = await get_guild(self.bot, member.guild.id)

        if (entrance_channel := discord.utils.get(member.guild.channels, name="entrance")) and g.greeting != None and g.greeting != "":
            message = process_message(g.greeting, member.guild, member)
            await entrance_channel.send(message)

    
    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        try:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])

            log.info(f"cmd: chan {ctx.channel} [{ctx.channel.id}], serv: {ctx.guild.name} [{ctx.guild.id}], "
                     f"auth: {ctx.user} [{ctx.user.id}]: {ctx.command} {params}")
        except AttributeError:
            log.info(f"Command in PM with {ctx.message.author} [{ctx.message.author.id}]: {ctx.message.content}")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error):
        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, discord.errors.CheckFailure):
            return await ctx.respond(f'You do not have required permissions for `{ctx.command}`')
    
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])

            out_str = f"Error in command: cmd: chan {ctx.channel} [{ctx.channel.id}], serv: {ctx.guild} [{ctx.guild.id}] auth: {ctx.user} [{ctx.user.id}]: {ctx.command} {params}\n```"\
                      f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"\
                      f"```"
            
            if ERROR_CHANNEL:
                try:
                    await ctx.bot.get_channel(int(ERROR_CHANNEL)).send(out_str)
                except:
                    log.error(out_str)
            else:
                log.error(out_str)

        try:
            if hasattr(ctx, "bot") and not hasattr(ctx.bot, "db"):
                return await ctx.respond(f"Try again in a few seconds. I'm not fully awake yet.", ephemeral=True)
            return await ctx.respond(f'Something went wrong. Let us know if it keeps up!', ephemeral=True)
        except:
            log.warning('Unable to respond')