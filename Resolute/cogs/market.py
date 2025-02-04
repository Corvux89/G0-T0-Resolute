import logging

from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.views.market import MarketPromptUI, TransactionPromptUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
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
    market_commands = SlashCommandGroup("market", "Market commands")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Market\' loaded')

    @market_commands.command(
        name="request",
        description="Setup a market request"
    )
    async def market_request(self, ctx: ApplicationContext):
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
        await ctx.defer()
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)

        if not player.characters:
            raise CharacterNotFound()

        if len(player.characters) == 1:
            ui = TransactionPromptUI.new(self.bot, ctx.author, player)
        else:
            ui = MarketPromptUI.new(self.bot, ctx.author, player)

        await ui.send_to(ctx)
        await ctx.delete()      