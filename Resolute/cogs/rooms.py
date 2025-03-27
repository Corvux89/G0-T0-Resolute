import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.helpers import is_admin
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.views.rooms import RoomSettingsUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Room(bot))


class Room(commands.Cog):
    """
    A Cog that handles room-related commands for the bot.
    Attributes:
        bot (G0T0Bot): The bot instance that this cog is attached to.
        room_commands (SlashCommandGroup): A group of slash commands related to room operations.
    Methods:
        __init__(bot):
            Initializes the Room cog with the given bot instance.
        room_settings(ctx: ApplicationContext):
            Handles the room settings command. Checks if the user has the necessary permissions
            and then provides a UI for managing room settings.
    """

    bot: G0T0Bot

    room_commands = discord.SlashCommandGroup(
        "room", "Room commands", contexts=[discord.InteractionContextType.guild]
    )

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Room' loaded")

    @room_commands.command(name="settings", description="Room settings")
    async def room_settings(self, ctx: G0T0Context):
        """
        Handles the room settings for a given context.
        This method checks if the author of the context has the necessary permissions
        to manage the room settings. If the author has the required permissions, it
        retrieves the relevant roles and initializes the RoomSettingsUI to manage
        the room settings.
        Args:
            ctx (ApplicationContext): The context of the application command.
        Raises:
            G0T0Error: If the author does not have the required permissions, if there
                       are no roles to manage, or if something goes wrong during the
                       process.
        """
        if not ctx.channel.category:
            raise G0T0Error("This command won't work here")

        channel: discord.TextChannel = ctx.guild.get_channel(ctx.channel.id)
        if ctx.author in channel.overwrites or await is_admin(ctx):
            roles = []
            guild = await PlayerGuild.get_player_guild(self.bot, ctx.guild.id)

            if (adventure := await Adventure.fetch_from_ctx(ctx)) and guild.quest_role:
                roles.append(guild.quest_role)
            elif guild.entry_role and guild.member_role:
                roles += [guild.entry_role, guild.member_role]
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
