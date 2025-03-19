import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.helpers import is_staff
from Resolute.models.objects.players import Player
from Resolute.models.views.character_view import CharacterManageUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Users(bot))


class Users(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Users' loaded")

    @commands.user_command(name="Manage")
    @commands.check(is_staff)
    async def user_manage(self, ctx: G0T0Context, user: discord.Member):
        player = await Player.get_player(self.bot, user.id, user.guild.id)
        ui = CharacterManageUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()
