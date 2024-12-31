import re

import discord
import requests
from discord import ApplicationContext, Interaction, Member
from sqlalchemy.util import asyncio

from Resolute.bot import G0T0Bot
from Resolute.constants import BOT_OWNERS
from Resolute.helpers.guilds import get_guild
from Resolute.models.objects.exceptions import SelectionCancelled
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


async def is_admin(ctx: ApplicationContext | Interaction) -> bool:
    """
    User is a designated administrator

    :param ctx: Context
    :return: True if user is a bot owner, can manage the guild, or has a listed role, otherwise False
    """

    
    g = await get_guild(ctx.bot, ctx.guild.id)

    r_list = [g.admin_role] if g.admin_role else []

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
    
async def is_staff(ctx: ApplicationContext | Interaction) -> bool:
    g = await get_guild(ctx.bot, ctx.guild.id)
    
    r_list = []
    
    if g.admin_role:
        r_list.append(g.admin_role)
    
    if g.staff_role:
        r_list.append(g.staff_role)

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
       response = requests.head(url, allow_redirects=True)

       if response.status_code == 200:
           content_type = response.headers.get('Content-Type', '').lower()

           return content_type.startswith('image/')
       elif response.status_code == 429 and 'imgur.com' in url:
           # Give a pass to imgur I guess
           return True
    except:
        pass

    return False

def paginate(choices: list[str], per_page: int) -> list[list[str]]:
    out = []
    for idx in range(0, len(choices), per_page):
        out.append(choices[idx:idx+per_page])
    return out

async def try_delete(message: discord.Message):
    try:
        await message.delete()
    except:
        pass

async def get_selection(ctx: discord.ApplicationContext, choices: list[str], delete: bool = True, dm: bool=False, message: str = None, force_select: bool = False, query_message: str = None):
    if len(choices) == 1 and not force_select:
        return choices[0]
    
    page = 0
    pages = paginate(choices, 10)
    m = None
    select_msg = None

    def check(msg):
        content = msg.content.lower()
        valid = content in ("c", "n", "p")

        try:
            valid = valid or (1 <= int(content) <= len(choices))
        except ValueError:
            pass

        return msg.author == ctx.author and msg.channel.id == ctx.channel.id and valid

    for n in range(200):
        _choices = pages[page]
        embed = discord.Embed(title="Multiple Matches Found")
        select_str = (
            f"{query_message}\n"
            f"Which one were you looking for? (Type the number or `c` to cancel)\n"
        )

        if len(pages) > 1:
            select_str += "`n` to go to the next page, or `p` for the previous \n"
            embed.set_footer(text=f"Page {page+1}/{len(pages)}")

        for i, r in enumerate(_choices):
            select_str += f"**[{i+1+page*10}]** - {r}\n"
        
        embed.description = select_str
        embed.color = discord.Color.random()

        if message:
            embed.add_field(
                name="Note",
                value=message,
                inline=False)

        if select_msg:
            await try_delete(select_msg)
        
        if not dm:
            select_msg = await ctx.channel.send(embed=embed)
        else:
            select_msg = await ctx.author.send(embed=embed)

        try:
            m = await ctx.bot.wait_for("message", timeout=30, check=check)
        except:
            m = None

        if m is None:
            break

        if m.content.lower() == 'n':
            if page+1 < len(pages):
                page += 1
            else:
                await ctx.channel.send("You are already on the last page")
        elif m.content.lower() == 'p':
            if page-1 >=0:
                page -=1
            else:
                await ctx.channel.send("You are already on the first page")
        else:
            break

    if delete and not dm:
        await try_delete(select_msg)
        if m is not None:
            await try_delete(m)

    if m is None or m.content.lower() == 'c':
        raise SelectionCancelled()
    
    idx = int(m.content) - 1

    return choices[idx]

        
