import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.dashboards import update_financial_dashboards
from Resolute.helpers.general_helpers import process_message
from Resolute.models.embeds.events import MemberLeaveEmbed
from Resolute.models.objects.applications import PlayerApplication
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
        on_entitlement_create(entitlement: Entitlement):
            Handles the event when an entitlement is created.
        on_entitlement_update(entitlement: Entitlement):
            Handles the event when an entitlement is updated.
    """

    bot: G0T0Bot

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        log.info(f"Cog 'Events' loaded")

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

        if player := await self.bot.get_player(
            int(payload.user.id), payload.guild_id, lookup_only=True
        ):
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
            player: Player = Player(
                self.bot,
                payload.user.id,
                payload.guild_id,
                member=payload.user,
                guild=g,
            )

        try:
            await player.guild.exit_channel.send(embed=MemberLeaveEmbed(player))
        except Exception as error:
            if isinstance(error, discord.HTTPException):
                log.error(
                    f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                    f"{player.guild.guild.name} [ {player.guild.id} ] for {payload.user.display_name} [ {payload.user.id} ]"
                )

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
                fin.reserve += max(
                    0, min(store.user_cost, fin.adjusted_total - fin.monthly_goal)
                )

        await fin.update()
        await update_financial_dashboards(self.bot)
