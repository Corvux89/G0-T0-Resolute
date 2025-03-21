import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.views.market import MarketPromptUI, TransactionPromptUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Market(bot))
    pass


class Market(commands.Cog):
    """
    A cog that handles market-related commands for the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        market_commands (SlashCommandGroup): A group of slash commands related to the market.
    Methods:
        __init__(bot):
            Initializes the Market cog with the given bot instance.
        market_request(ctx: ApplicationContext):
            Handles the market request command. Sets up a market request for the user.
    """

    bot: G0T0Bot
    market_commands = discord.SlashCommandGroup("market", "Market commands")

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Market' loaded")

    @market_commands.command(name="request", description="Setup a market request")
    async def market_request(self, ctx: G0T0Context):
        """
        Handles a market request from a user.
        This function defers the context, retrieves the player associated with the user,
        and checks if the player has any characters. Depending on the number of characters
        the player has, it initializes either a TransactionPromptUI or MarketPromptUI and
        sends it to the user.
        Args:
            ctx (ApplicationContext): The context of the application command.
        Raises:
            CharacterNotFound: If the player has no characters.
        """

        if not ctx.player.characters:
            raise CharacterNotFound()

        if len(ctx.player.characters) == 1:
            ui = TransactionPromptUI.new(self.bot, ctx.author, ctx.player)
        else:
            ui = MarketPromptUI.new(self.bot, ctx.author, ctx.player)

        await ui.send_to(ctx)
        await ctx.delete()
