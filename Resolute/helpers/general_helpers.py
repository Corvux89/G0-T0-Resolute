import discord
import re
import urllib.request as re
from discord import ApplicationContext, Member, Guild, Interaction
from sqlalchemy.util import asyncio

from Resolute.bot import G0T0Bot
from Resolute.constants import BOT_OWNERS, THUMBNAIL
from Resolute.models.objects.guilds import PlayerGuild


def is_owner(ctx: ApplicationContext) -> bool:
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


def is_admin(ctx: ApplicationContext | Interaction) -> bool:
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
    
def is_staff(ctx: ApplicationContext | Interaction) -> bool:
    
    r_list = [discord.utils.get(ctx.guild.roles, name="The Senate"),
              discord.utils.get(ctx.guild.roles, name="Archivist")]

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



def get_positivity(string) -> bool:
    if isinstance(string, bool):  # oi!
        return string
    lowered = string.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off", "cancel"):
        return False
    else:
        return None


async def confirm(ctx, message, delete_msgs=False, bot: G0T0Bot = None, response_check=get_positivity, full_reply: bool = False) -> bool|str:
    msg = await ctx.channel.send(message)
    
    if bot is None:
        bot = ctx.bot

    try:
        reply = await bot.wait_for("message", timeout=30, check=auth_and_chan(ctx))
    except asyncio.TimeoutError:
        return None
    if response_check:
        reply_bool = response_check(reply.content) if reply is not None else None
    elif full_reply:
        reply_bool = reply
    else:
        reply_bool = reply.content
    if delete_msgs:
        try:
            await msg.delete()
            await reply.delete()
        except:
            pass
    return reply_bool


def auth_and_chan(ctx) -> bool:
    if hasattr(ctx, 'author'):
        author = ctx.author
    else:
        author = ctx.user

    def chk(msg):
        return msg.author == author and msg.channel == ctx.channel

    return chk


def process_message(message: str, g: PlayerGuild,  member: Member = None, mappings: dict = None) -> str:
    channel_mentions = re.findall(r'{#([^}]*)}', message)
    role_mentions = re.findall(r'{@([^}]*)}', message)

    for chan in channel_mentions:
        if (channel := discord.utils.get(g.guild.channels, name=chan)):
            message = message.replace("{#"+chan+"}", f"{channel.mention}")
    for r in role_mentions:
        if (role := discord.utils.get(g.guild.roles, name=r)):
            message = message.replace("{@"+r+"}", f"{role.mention}")

    if mappings:
        for mnemonic, value in mappings.items():
            message = message.replace("{"+mnemonic+"}", value)

    if member:
        message = message.replace("{user}", f"{member.mention}")

    return message

async def get_webhook(channel: discord.TextChannel) -> discord.Webhook:
    webhooks = await channel.webhooks()
    for hook in webhooks:
        if (hook.token):
            return hook
        
    hook = await channel.create_webhook(name="G0T0 Hook",
                                 reason="G0T0 Bot Webhook")
    
    return hook


def isImageURL(url: str) -> bool:
    try:
        with re.urlopen(url) as response:
            if response.status == 200:
                content_type = response.getheader("Content-Type")
                return content_type.startswith("image/")
    except:
        pass

    return False