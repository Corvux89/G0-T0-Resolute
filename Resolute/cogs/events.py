import logging
import traceback

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ERROR_CHANNEL
from Resolute.helpers.dashboards import update_financial_dashboards
from Resolute.helpers.general_helpers import process_message
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.events import MemberLeaveEmbed
from Resolute.models.objects.applications import PlayerApplication
from Resolute.models.objects.exceptions import G0T0CommandError, G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

def setup(bot: G0T0Bot):
    bot.add_cog(Events(bot))

class Events(commands.Cog):
    """
    Cog for handling various bot events.
    Attributes:
        bot (G0T0Bot): The bot instance.
    Methods:
        on_raw_member_remove(payload: RawMemberRemoveEvent):
            Handles the event when a member is removed from the guild.
        on_member_join(member: Member):
            Handles the event when a member joins the guild.
        on_command(ctx: discord.ApplicationContext):
            Handles the event when a command is invoked.
        on_application_command(ctx: discord.ApplicationContext):
            Handles the event when an application command is invoked.
        on_application_command_error(ctx: discord.ApplicationContext, error):
            Handles errors that occur during the execution of an application command.
        on_command_error(ctx: discord.ApplicationContext, error):
            Handles errors that occur during the execution of a command.
        on_entitlement_create(entitlement: Entitlement):
            Handles the event when an entitlement is created.
        on_entitlement_update(entitlement: Entitlement):
            Handles the event when an entitlement is updated.
    """
    bot: G0T0Bot

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        log.info(f'Cog \'Events\' loaded')

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        """
        Event handler for when a member is removed from a guild.
        This function performs the following actions:
        1. Cleans up the reference table by upserting the application data.
        2. Checks if the player exists in the bot's database.
        3. If the player exists:
            - Cleans up the arena board by purging messages from the removed member.
            - Sets the player's member attribute to the removed user if an exit channel is present.
        4. If the player does not exist:
            - Retrieves the player's guild information.
            - Creates a new player instance with the removed user's information.
        5. Attempts to send a leave embed message to the guild's exit channel.
        Args:
            payload (RawMemberRemoveEvent): The event payload containing information about the removed member.
        """
        # Reference Table Cleanup
        await PlayerApplication(self.bot, payload.user).delete()

        if player := await self.bot.get_player(int(payload.user.id), payload.guild_id, 
                                               lookup_only=True):
            # Cleanup Arena Board
            def predicate(message):
                return message.author == payload.user
            
            if player.guild.arena_board_channel:
                try:
                    await player.guild.arena_board_channel.purge(check=predicate)
                except Exception as error:
                    if isinstance(error, discord.HTTPException):
                        pass
                    else:
                        log.error(error)
                        
            if player.guild.exit_channel:
                player.member = payload.user
        else:
            g: PlayerGuild = await self.bot.get_player_guild(payload.guild_id)
            player: Player = Player(payload.user.id, payload.guild_id, member=payload.user, guild=g)

        
        try:
            await player.guild.exit_channel.send(embed=MemberLeaveEmbed(player))
        except Exception as error:
            if isinstance(error, discord.HTTPException):
                log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                        f"{player.guild.guild.name} [ {player.guild.id} ] for {payload.user.display_name} [ {payload.user.id} ]")     

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Event handler that is called when a new member joins the guild.
        This function sends a greeting message to the entrance channel if it is set up in the guild's settings.
        Args:
            member (Member): The member who joined the guild.
        Returns:
            None
        """
        g = await self.bot.get_player_guild(member.guild.id)

        if g.entrance_channel and g.greeting != None and g.greeting != "":
            message = process_message(g.greeting, member.guild, member)
            await g.entrance_channel.send(message)

    @commands.Cog.listener()
    async def on_command(self, ctx: discord.ApplicationContext):
        """
        Event handler for when a command is invoked.
        This method is triggered whenever a command is executed. It updates the command count
        for the player who invoked the command.
        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked. This includes
                                      information about the command, the user who invoked it, and
                                      the guild (if applicable).
        Returns:
            None
        """
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None)
            await player.update_command_count(str(ctx.command))

    
    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        """
        Event handler for when an application command is executed.
        This function logs the command execution details and updates the command count for the player
        if the bot has a database connection.
        Args:
            ctx (discord.ApplicationContext): The context of the application command, which includes information
                                      about the command, the user who executed it, and the channel/guild
                                      where it was executed.
        Raises:
            AttributeError: If there is an issue accessing attributes of the context or bot.
        Logs:
            Information about the command execution, including the channel, server, author, and command details.
        """
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
        """
        Handles errors that occur during the execution of application commands.
        Parameters:
        ctx (discord.ApplicationContext): The context in which the command was invoked.
        error (Exception): The error that was raised during command execution.
        Returns:
        None
        This function performs the following actions:
        - If the command has a custom error handler (`on_error`), it returns immediately.
        - If the error is a `CheckFailure`, it responds with a message indicating insufficient permissions.
        - If the error is a `G0T0Error`, it responds with an embedded error message.
        - Logs detailed error information to a specified error channel or to the log if the error channel is not available.
        - Responds with appropriate messages for specific conditions such as bot not being fully initialized or command not supported in direct messages.
        """
        if hasattr(ctx.command, 'on_error'):
            return                

        if isinstance(error, discord.CheckFailure):
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
        """
        Handles errors that occur during command invocation.
        Parameters:
        ctx (discord.ApplicationContext): The context in which the command was invoked.
        error (Exception): The exception that was raised during command invocation.
        Returns:
        None
        Behavior:
        - If the command has its own error handler or the error is a CommandNotFound, the function returns immediately.
        - If the error is a CheckFailure, sends a message indicating the user lacks permissions for the command.
        - If the error is a G0T0CommandError, sends an embedded error message.
        - Logs the error details to a specified error channel or logs it if the error channel is not available.
        - Sends a message indicating the bot is not fully awake if the bot's database is not available.
        - Sends a message indicating the command is not supported in direct messages if invoked in a DM.
        - Sends a generic error message if none of the above conditions are met.
        - Logs a warning if unable to respond to the user.
        """
        time = 5
        if hasattr(ctx.command, 'on_error') or isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, discord.CheckFailure):
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
        """
        Event handler for when an entitlement is created.
        This method is called automatically when an entitlement is created.
        It processes the entitlement using the handle_entitlements function.
        Args:
            entitlement (Entitlement): The entitlement object that was created.
        """       
        await self._handle_entitlements(entitlement)

    @commands.Cog.listener()
    async def on_entitlement_update(self, entitlement: discord.Entitlement):
        """
        Event handler for entitlement updates.
        This method is called whenever an entitlement is updated. It processes
        the updated entitlement by calling the handle_entitlements function.
        Args:
            entitlement (Entitlement): The updated entitlement object.
        """
        await self._handle_entitlements(entitlement)

    # --------------------------- #
    # Private Methods
    # --------------------------- #
    async def _handle_entitlements(self, entitlement: discord.Entitlement) -> None:
        """
        Handle the entitlements for a user.
        This function processes the entitlements by updating the financial data
        and dashboards based on the store items and their costs.
        Args:
            entitlement (Entitlement): The entitlement object containing SKU ID.
        Returns:
            None
        """
        store_items = await self.bot.get_store_items()

        fin = await self.bot.get_financial_data()

        if store := next((s for s in store_items if s.sku == entitlement.sku_id), None):
            fin.monthly_total += store.user_cost
            
            if fin.adjusted_total > fin.monthly_goal:
                fin.reserve += max(0, min(store.user_cost, fin.adjusted_total - fin.monthly_goal))

        await fin.update()
        await update_financial_dashboards(self.bot)
        

        