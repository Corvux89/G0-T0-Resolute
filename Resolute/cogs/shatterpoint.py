from discord import *
from discord.commands import SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import is_admin
from Resolute.models.views.shatterpoint import ShatterpointSettingsUI

log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Shatterpoints(bot))

class Shatterpoints(commands.Cog):
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
        shatterpoint = await self.bot.get_shatterpoint(ctx.guild.id)

        ui = ShatterpointSettingsUI.new(self.bot, ctx.author, shatterpoint)
        await ui.send_to(ctx)
        await ctx.delete()