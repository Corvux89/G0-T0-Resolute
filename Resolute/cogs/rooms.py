import logging

from discord import ApplicationContext, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers import get_adventure_from_category, get_guild, is_admin
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.views.rooms import RoomSettingsUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Room(bot))


class Room(commands.Cog):
    bot: G0T0Bot

    room_commands = SlashCommandGroup("room", "Room commands", guild_only=True)
    
    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Room\' loaded')

    @room_commands.command(
        name="settings",
        description="Room settings"
    )
    async def room_settings(self, ctx: ApplicationContext):
        channel = ctx.guild.get_channel(ctx.channel.id)
        if (ctx.author in channel.overwrites or is_admin(ctx)):
            roles = []
            guild = await get_guild(self.bot, ctx.guild.id)

            if (adventure := await get_adventure_from_category(self.bot, ctx.channel.category.id)) and guild.quester_role:
                roles.append(guild.quester_role)    
            elif guild.citizen_role and guild.acolyte_role:
                roles+=[guild.citizen_role, guild.acolyte_role]
            else:
                raise G0T0Error("Something went wrong")
            if roles:
                ui = RoomSettingsUI.new(self.bot, ctx.author, roles, adventure)
                await ui.send_to(ctx)
                await ctx.delete()
            else:
                raise G0T0Error("No roles to manage")
        else:
            raise G0T0Error("This is not the channel you're searching for")