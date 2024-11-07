import logging

from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers import get_player
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.views.market import MarketPromptUI, TransactionPromptUI


log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Market(bot))
    pass

class Market(commands.Cog):
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
        await ctx.defer()
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)

        if not player.characters:
            raise CharacterNotFound()

        if len(player.characters) == 1:
            ui = TransactionPromptUI.new(self.bot, ctx.author, player)
        else:
            ui = MarketPromptUI.new(self.bot, ctx.author, player)

        await ui.send_to(ctx)
        await ctx.delete()      

