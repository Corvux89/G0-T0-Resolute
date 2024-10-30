from discord import *
from discord.ext import commands
from discord.commands import SlashCommandGroup

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import is_admin
from Resolute.helpers.shatterpoint import get_shatterpoint
from Resolute.models.views.shatterpoint import ShatterpointSettingsUI

log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Shatterpoints(bot))

class Shatterpoints(commands.Cog):
    # TODO: Scrape channel update to scrape character (based on say), then reward characers credits based on conversion as well, and apply renown
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    shatterpoint_commands = SlashCommandGroup("shatterpoint", "Commands related to Shatterpoint event management.", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

        log.info(f'Cog \'ShatterPoints\' loaded')

    @shatterpoint_commands.command(
        name="manage",
        description="Manage a shatterpoint"
    )
    @commands.check(is_admin)
    async def shatterpoint_manage(self, ctx: ApplicationContext):
        shatterpoint = await get_shatterpoint(self.bot, ctx.guild.id)

        ui = ShatterpointSettingsUI.new(self.bot, ctx.author, shatterpoint)
        await ui.send_to(ctx)
        await ctx.delete()