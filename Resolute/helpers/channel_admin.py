import discord

owner_overwrites = discord.PermissionOverwrite(view_channel=True,
                                               manage_messages=True,
                                               send_messages=True)

general_overwrites = discord.PermissionOverwrite(view_channel=True,
                                                 send_messages=False)

bot_overwrites = discord.PermissionOverwrite(view_channel=True,
                                             send_messages=True)

readonly_overwrites = discord.PermissionOverwrite(view_channel=True,
                                                  send_messages=False,
                                                  add_reactions=False,
                                                  read_messages=True,
                                                  send_tts_messages=False,
                                                  manage_messages=False,
                                                  manage_roles=False,
                                                  send_messages_in_threads=False)

async def add_owner(channel: discord.TextChannel, member: discord.Member):
    channel_overwrites = channel.overwrites

    channel_overwrites[member] = owner_overwrites

    await channel.edit(overwrites=channel_overwrites)

async def remove_owner(channel: discord.TextChannel, member: discord.Member):
    channel_overwrites = channel.overwrites

    del channel_overwrites[member]

    await channel.edit(overwrites=channel_overwrites)

async def create_channel(name: str, category: discord.TextChannel, member: discord.Member) -> discord.TextChannel:
    channel_overwrites = {}

    channel_overwrites[member] = owner_overwrites
    
    if bot_role := discord.utils.get(member.guild.roles, name="Bots"):
        channel_overwrites[bot_role] = bot_overwrites

    if citizen_role := discord.utils.get(member.guild.roles, name="Citizen"):
        channel_overwrites[citizen_role] = general_overwrites

    if acolyte_role := discord.utils.get(member.guild.roles, name="Acolyte"):
        channel_overwrites[acolyte_role] = general_overwrites

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


