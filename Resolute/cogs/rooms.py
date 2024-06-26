import logging
import discord

from discord import SlashCommandGroup, ApplicationContext
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.adventures import get_adventure_from_category
from Resolute.helpers.general_helpers import is_admin
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.views.rooms import RoomSettingsUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Room(bot))


class Room(commands.Cog):
    bot: G0T0Bot

    room_commands = SlashCommandGroup("room", "Room commands")
    
    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Room\' loaded')

    @room_commands.command(
        name="settings",
        description="Room settings"
    )
    async def room_settings(self, ctx: ApplicationContext):
        if ctx.channel.overwrites_for(ctx.author).manage_channels == True or is_admin(ctx):
            roles = []

            if (adventure := await get_adventure_from_category(self.bot, ctx.channel.category.id)) and (questor_role := discord.utils.get(ctx.guild.roles, name="Quester")):
                roles.append(questor_role)    
            elif (member_role := discord.utils.get(ctx.guild.roles, name="Citizen")) and (initiate_role := discord.utils.get(ctx.guild.roles, name="Acolyte")):
                roles+=[member_role, initiate_role]
            else:
                return await ctx.respond(embed=ErrorEmbed(description=f"Problem finding roles to manage"), ephemeral=True)
            if roles:
                ui = RoomSettingsUI.new(self.bot, ctx.author, roles, adventure)
                await ui.send_to(ctx)
                await ctx.delete()
            else:
                return await ctx.respond("No roles to manage")
        else:
            return await ctx.respond(embed=ErrorEmbed(description=f"There is nothing in this channel you can do"), ephemeral=True)