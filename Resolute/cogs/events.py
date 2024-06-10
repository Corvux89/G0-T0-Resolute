import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.adventures import get_player_adventures
from Resolute.helpers.appliations import upsert_application
from Resolute.helpers.arenas import get_player_arenas
from Resolute.helpers.general_helpers import process_message
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.players import get_player
from Resolute.models.embeds.events import MemberLeaveEmbed

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))

class Events(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Events\' loaded')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Reference Table Cleanup
        await upsert_application(self.bot.db, member.id)
        
        if exit_channel := discord.utils.get(member.guild.channels, name="exit"):
            g = await get_guild(self.bot.db, member.guild.id)
            player = await get_player(self.bot, member.id, member.guild.id)
            player.adventures = await get_player_adventures(self.bot, player)
            player.arenas = await get_player_arenas(self.bot, player)

            try:
                await exit_channel.send(embed=MemberLeaveEmbed(self.bot, member, player))
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                            f"{member.guild.name} [ {member.guild.id} ] for {member.name} [ {member.id} ]")
            

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = await get_guild(self.bot.db, member.guild.id)

        if (entrance_channel := discord.utils.get(member.guild.channels, name="entrance")) and g.greeting:
            message = process_message(g.greeting, member.guild, member)
            await entrance_channel.send(message)
