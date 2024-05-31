import discord
import re
from discord import ApplicationContext, Member, Guild, Interaction
from sqlalchemy.util import asyncio

from Resolute.bot import G0T0Bot
from Resolute.constants import BOT_OWNERS


def is_owner(ctx: ApplicationContext):
    """
    User is a bot owner (not just a server owner)

    :param ctx: Context
    :return: True if user is in BOT_OWNERS constant, otherwise False
    """
    if hasattr(ctx, 'author'):
        author = ctx.author
    else:
        author = ctx.user

    return author.id in BOT_OWNERS


def is_admin(ctx: ApplicationContext | Interaction):
    """
    User is a designated administrator

    :param ctx: Context
    :return: True if user is a bot owner, can manage the guild, or has a listed role, otherwise False
    """
    r_list = [discord.utils.get(ctx.guild.roles, name="The Senate")]

    if hasattr(ctx, 'author'):
        author = ctx.author
    else:
        author = ctx.user

    if is_owner(ctx):
        return True
    elif any(r in r_list for r in author.roles):
        return True
    else:
        return False


def get_positivity(string):
    if isinstance(string, bool):  # oi!
        return string
    lowered = string.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    else:
        return None


async def confirm(ctx, message, delete_msgs=False, bot: G0T0Bot = None, response_check=get_positivity):
    """
    Confirms whether a user wants to take an action.
    :rtype: bool|None
    :param ctx: The current Context.
    :param message: The message for the user to confirm.
    :param delete_msgs: Whether to delete the messages.
    :param response_check: A function (str) -> bool that returns whether a given reply is a valid response.
    :type response_check: (str) -> bool
    :return: Whether the user confirmed or not. None if no reply was received
    """
    msg = await ctx.channel.send(message)
    
    if bot is None:
        bot = ctx.bot

    try:
        reply = await bot.wait_for("message", timeout=30, check=auth_and_chan(ctx))
    except asyncio.TimeoutError:
        return None
    reply_bool = response_check(reply.content) if reply is not None else None
    if delete_msgs:
        try:
            await msg.delete()
            await reply.delete()
        except:
            pass
    return reply_bool


def auth_and_chan(ctx):
    """Message check: same author and channel"""

    if hasattr(ctx, 'author'):
        author = ctx.author
    else:
        author = ctx.user

    def chk(msg):
        return msg.author == author and msg.channel == ctx.channel

    return chk


def process_message(message: str, guild: Guild,  member: Member = None, mappings: dict = None):
    channel_mentions = re.findall(r'{#([^}]*)}', message)
    role_mentions = re.findall(r'{@([^}]*)}', message)

    for chan in channel_mentions:
        if (channel := discord.utils.get(guild.channels, name=chan)):
            message = message.replace("{#"+chan+"}", f"{channel.mention}")
    for r in role_mentions:
        if (role := discord.utils.get(guild.roles, name=r)):
            message = message.replace("{@"+r+"}", f"{role.mention}")

    if mappings:
        for mnemonic, value in mappings.items():
            message = message.replace("{"+mnemonic+"}", value)

    if member:
        message = message.replace("{user}", f"{member.mention}")

    return message

    