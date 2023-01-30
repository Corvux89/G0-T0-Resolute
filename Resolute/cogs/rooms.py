import logging

import discord
from discord import SlashCommandGroup, ApplicationContext, Option
from discord.ext import commands

from ProphetBot.bot import BpBot
from ProphetBot.helpers import get_adventure, is_admin
from ProphetBot.models.db_objects import Adventure
from ProphetBot.models.embeds import ErrorEmbed

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Room(bot))


class Room(commands.Cog):
    bot: BpBot

    room_commands = SlashCommandGroup("room", "Room commands")

    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Room\' loaded')

    @room_commands.command(
        name="add_room",
        description="Adds a channel to this adventure category."
    )
    async def room_add(self, ctx: ApplicationContext,
                       room_name: Option(str, description="The name of the new room. "
                                                          "Spaces will become dashes and forced lowercase",
                                         required=True)):
        """
        Adds a TextChannel to the adventure Category. This command must be run in the Category the channel is to be
        added to.

        :param ctx: Context
        :param room_name: Name of the room to add. This will automatically be formatted to Discord standards
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif ctx.author.id not in adventure.dms:
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            category = ctx.channel.category
            new_room = await category.create_text_channel(room_name, reason=f"Additional adventure room created by "
                                                                            f"{ctx.author.name}")
            await ctx.respond(f"Room {new_room.mention} successfully created by {ctx.author.mention}")

    @room_add.error
    async def addroom_errors(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send('Error: Command cannot be used via private messages')
        log.error(error)

    @room_commands.command(
        name="rename",
        description="Changes the name of a room"
    )
    async def room_rename(self, ctx: ApplicationContext,
                          room_name: Option(str, description="Name to change the room to")):
        """
        Renames a TextChannel. This must be run in the room to be renamed.

        :param ctx: Context
        :param room_name: The name to change the TextChannel name to
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif ctx.author.id not in adventure.dms:
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            await ctx.channel.edit(name=room_name)
            await ctx.respond(f"Room name changed to {ctx.channel.mention}")

    @room_commands.command(
        name="view",
        description="Open or close a channel for public viewing"
    )
    async def room_open(self, ctx: ApplicationContext,
                        view: Option(str, description="Open or close the room", choices=['open', 'close'],
                                     required=True),
                        allow_post: Option(bool, description="Whether to allow public posts", required=False,
                                           default=False)):
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)
        room_view = True if view.lower() == "open" else False
        val = "closed" if view == "close" else "open"

        if adventure is None:
            if "holding" in ctx.channel.category.name.lower():
                overwrites = ctx.channel.overwrites
                if ctx.author in overwrites or is_admin(ctx):
                    if guild_member := discord.utils.get(ctx.guild.roles, name="Guild Member"):
                        overwrites[guild_member] = discord.PermissionOverwrite(view_channel=room_view,
                                                                               send_messages=allow_post)

                    if guild_initiate := discord.utils.get(ctx.guild.roles, name="Guild Initiate"):
                        overwrites[guild_initiate] = discord.PermissionOverwrite(view_channel=room_view,
                                                                               send_messages=allow_post)

                    await ctx.channel.edit(overwrites=overwrites)

                    if allow_post:
                        return await ctx.respond(f"{ctx.channel.mention} is now {val} and able to be posted in")
                    else:
                        return await ctx.respond(f"{ctx.channel.mention} is now {val}")

                else:
                    return await ctx.respond(embed=ErrorEmbed(description="Error: You don't have appropriate permissions for this holding"),
                                             ephemeral=True)
            else:
                return await ctx.respond(embed=ErrorEmbed(description="Error: No adventure or holding associated with this channel"),
                                                          ephemeral=True)

        elif ctx.author.id not in adventure.dms and not is_admin(ctx):
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            overwrites = ctx.channel.overwrites

            if quester_role := discord.utils.get(ctx.guild.roles, name="Quester"):
                overwrites[quester_role] = discord.PermissionOverwrite(view_channel=room_view,
                                                                       send_messages=allow_post)
                await ctx.channel.edit(overwrites=overwrites)
                if allow_post:
                    await ctx.respond(f"{ctx.channel.mention} is now {val} and able to be posted in by the "
                                      f"{quester_role.mention} role")
                else:
                    await ctx.respond(f"{ctx.channel.mention} is now {val} to the {quester_role.mention} role")
            else:
                await ctx.respond("Couldn't find the @Quester role")

    @room_commands.command(
        name="move",
        description="Moves the current channel within the adventure category."
    )
    async def room_move(self, ctx: ApplicationContext,
                        position: Option(str, description="Where to move the room", required=True,
                                         choices=['top', 'up', 'down', 'bottom'])):
        """
        Moves the current TextChannel within the current Category
        :param ctx: Context
        :param position: Where to move the Textchannel
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif ctx.author.id not in adventure.dms:
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            category = ctx.channel.category
            channels = category.channels
            old_position = channels.index(ctx.channel)

            match position.lower():
                case 'top':
                    if old_position == 0:
                        return await ctx.respond(f"Error: Channel position is already at top.")
                    else:
                        new_position = 0

                case 'up':
                    if old_position == 0:
                        return await ctx.respond(f"Error: Channel position is already at top.")
                    else:
                        new_position = old_position - 1
                case 'down':
                    if old_position == len(channels) - 1:
                        return await ctx.respond(f"Error: Channel already at the lowest position.")
                    else:
                        new_position = old_position + 1
                case 'bottom':
                    if old_position == len(channels) - 1:
                        return await ctx.respond(f"Error: Channel already at the lowest position.")
                    else:
                        new_position = len(channels) - 1

            channels.insert(new_position, channels.pop(old_position))

            for i, c in enumerate(channels):
                await c.edit(position=i)

            await ctx.respond(f"Channel {ctx.channel.mention} moved to position {new_position + 1} of {len(channels)}")