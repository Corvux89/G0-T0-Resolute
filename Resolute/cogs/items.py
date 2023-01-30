from discord import SlashCommandGroup, ApplicationContext, Option
from discord.ext import commands

from ProphetBot.bot import BpBot
from ProphetBot.helpers import item_autocomplete
from ProphetBot.models.embeds import BlacksmithItemEmbed, MagicItemEmbed, ConsumableItemEmbed, ScrollItemEmbed, \
    ErrorEmbed


def setup(bot: commands.Bot):
    bot.add_cog(Items(bot))


class Items(commands.Cog):
    bot: BpBot
    item_commands = SlashCommandGroup("item", "Item commands")

    # noinspection PyTypeHints
    def __init__(self, bot):
        self.bot = bot
        print(f'Cog \'Items\' loaded')

    @item_commands.command(
        name="lookup",
        description="Look up item information"
    )
    async def item_lookup(self, ctx: ApplicationContext,
                          item: Option(str, description="Item to lookup",
                                       autocomplete=item_autocomplete,
                                       required=True)):
        """
        Looks up item information

        :param ctx: Context
        :param item: Item to lookup
        """

        if item_record := ctx.bot.compendium.get_object("blacksmith", item):
            embed = BlacksmithItemEmbed(item_record)
        elif item_record := ctx.bot.compendium.get_object("wondrous", item):
            embed = MagicItemEmbed(item_record)
        elif item_record := ctx.bot.compendium.get_object("consumable", item):
            embed = ConsumableItemEmbed(item_record)
        elif item_record := ctx.bot.compendium.get_object("scroll", item):
            embed = ScrollItemEmbed(item_record)
        else:
            return await ctx.respond(embed=ErrorEmbed(description=f"Item not found"))

        await ctx.respond(embed=embed)
