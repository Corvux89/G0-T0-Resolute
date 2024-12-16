import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.guilds import get_guild

owner_overwrites = discord.PermissionOverwrite(view_channel=True,
                                               manage_messages=True,
                                               send_messages=True)

general_overwrites = discord.PermissionOverwrite(view_channel=True,
                                                 send_messages=False)

bot_overwrites = discord.PermissionOverwrite(view_channel=True,
                                             send_messages=True,
                                             manage_messages=True,
                                             manage_channels=True)                                             

readonly_overwrites = discord.PermissionOverwrite(view_channel=True,
                                                  send_messages=False,
                                                  add_reactions=False,
                                                  read_messages=True,
                                                  send_tts_messages=False,
                                                  manage_messages=False,
                                                  manage_roles=False,
                                                  send_messages_in_threads=False)

async def add_owner(channel: discord.TextChannel, member: discord.Member) -> None:
    await channel.set_permissions(member, overwrite=owner_overwrites)


async def remove_owner(channel: discord.TextChannel, member: discord.Member) -> None:
    await channel.set_permissions(member, overwrite=None)


async def create_channel(bot: G0T0Bot, name: str, category: discord.TextChannel, member: discord.Member) -> discord.TextChannel:
    channel_overwrites = category.overwrites
    g = await get_guild(bot, category.guild.id)

    channel_overwrites[member] = owner_overwrites
    
    if g.bot_role:
        channel_overwrites[g.bot_role] = bot_overwrites

    if g.member_role:
        channel_overwrites[g.member_role] = general_overwrites

    if g.staff_role:
        channel_overwrites[g.staff_role] = general_overwrites

    channel = await member.guild.create_text_channel(
        name=name,
        category=category,
        overwrites=channel_overwrites,
        reason=f"Channel Admin command"
    )

    await channel.send(f"{member.mention} welcome to your new channel.\n"
                       f"Go ahead and set everything up.\n"
                       f"1. Make sure you can delete this message.\n"
                       f"2. Use `/room settings` to see your management options")
    
    return channel

async def archive_channel(channel: discord.TextChannel) -> None:
    channel_overwrites = {}


