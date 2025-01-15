import logging
import traceback

import discord
import discord.ext
import discord.ext.commands
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ERROR_CHANNEL
from Resolute.helpers.appliations import upsert_application
from Resolute.helpers.events import handle_entitlements
from Resolute.helpers.general_helpers import process_message
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.events import MemberLeaveEmbed
from Resolute.models.objects.exceptions import G0T0CommandError, G0T0Error
from Resolute.models.objects.players import Player

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
        # Reference Table Cleanup
        await upsert_application(self.bot.db, payload.user.id)

        if player := await self.bot.get_player(payload.user.id, payload.guild_id, 
                                               lookup_only=True):
            # Cleanup Arena Board
            def predicate(message):
                return message.author == payload.user
            
            if player.guild.arena_board_channel:
                try:
                    await player.guild.arena_board_channel.purge(check=predicate)
                except Exception as error:
                    if isinstance(error, discord.errors.HTTPException):
                        pass
                    else:
                        log.error(error)
                        
            if player.guild.exit_channel:
                player.member = payload.user
            else:
                player: Player = Player(payload.user.id, payload.guild_id, member=payload.user)

            
            try:
                await player.guild.exit_channel.send(embed=MemberLeaveEmbed(player))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                            f"{player.guild.guild.name} [ {player.guild.id} ] for {payload.user.display_name} [ {payload.user.id} ]")     

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = await self.bot.get_player_guild(member.guild.id)

        if g.entrance_channel and g.greeting != None and g.greeting != "":
            message = process_message(g.greeting, member.guild, member)
            await g.entrance_channel.send(message)

    @commands.Cog.listener()
    async def on_command(self, ctx: discord.ApplicationContext):
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None)
            await player.update_command_count(str(ctx.command))

    
    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        try:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])
            if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
                if player := await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                                       lookup_only=True):
                    
                    await player.update_command_count(str(ctx.command))

            log.info(f"cmd: chan {ctx.channel} [{ctx.channel.id}], serv: {f'{ctx.guild.name} [{ctx.guild.id}]' if ctx.guild_id else 'DC'}, "
                     f"auth: {ctx.user} [{ctx.user.id}]: {ctx.command}  {params}")
            
        except AttributeError:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in (ctx.selected_options or [])])
            if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
                player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None)
                await player.update_command_count(str(ctx.command))

            log.info(f"Command in DM with {ctx.user} [{ctx.user.id}]: {ctx.command} {params}")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error):
        if hasattr(ctx.command, 'on_error'):
            return                

        if isinstance(error, discord.errors.CheckFailure):
            return await ctx.respond(f'You do not have required permissions for `{ctx.command}`', ephemeral=True)
        elif isinstance(error, G0T0Error):
            return await ctx.respond(embed=ErrorEmbed(error), ephemeral=True)
    
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
        time = 5
        if hasattr(ctx.command, 'on_error') or isinstance(error, discord.ext.commands.CommandNotFound):
            return

        if isinstance(error, discord.errors.CheckFailure):
            return await ctx.send(f'You do not have required permissions for `{ctx.command}`', delete_after=time)
        elif isinstance(error, G0T0CommandError):
            return await ctx.send(embed=ErrorEmbed(error), delete_after=time)
    
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
                return await ctx.send(f"Try again in a few seconds. I'm not fully awake yet.", delete_after=time)
            
            if not ctx.guild:
                return await ctx.send(f"This command isn't supported in direct messages.", delete_after=time)    

            return await ctx.send(f'Something went wrong. Let us know if it keeps up!', delete_after=time)
        except:
            log.warning('Unable to respond')

    @commands.Cog.listener()
    async def on_entitlement_create(self, entitlement: discord.Entitlement):
       await handle_entitlements(self.bot, entitlement)

    @commands.Cog.listener()
    async def on_entitlement_update(self, entitlement: discord.Entitlement):
        await handle_entitlements(self.bot, entitlement)
        

        