import discord
from PIL import Image, ImageDraw
from discord import ApplicationContext
from sqlalchemy.util import asyncio

from ProphetBot.constants import BOT_OWNERS


def is_owner(ctx: ApplicationContext):
    """
    User is a bot owner (not just a server owner)

    :param ctx: Context
    :return: True if user is in BOT_OWNERS constant, otherwise False
    """
    return ctx.author.id in BOT_OWNERS


def is_admin(ctx: ApplicationContext):
    """
    User is a designated administrator

    :param ctx: Context
    :return: True if user is a bot owner, can manage the guild, or has a listed role, otherwise False
    """
    r_list = [discord.utils.get(ctx.guild.roles, name="Council")]

    if is_owner(ctx):
        return True
    elif any(r in r_list for r in ctx.author.roles):
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


async def confirm(ctx, message, delete_msgs=False, response_check=get_positivity):
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
    try:
        reply = await ctx.bot.wait_for("message", timeout=30, check=auth_and_chan(ctx))
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

    def chk(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel

    return chk


def draw_progress_bar(d, x, y, w, h, progress, bg="black"):
    # draw background
    d.ellipse((x + w, y, x + h + w, y + h), fill=bg)
    d.ellipse((x, y, x + h, y + h), fill=bg)
    d.rectangle((x + (h / 2), y, x + w + (h / 2), y + h), fill=bg, width=10)

    COLOR = [(255, 0, 0), (255, 165, 0), (255, 255, 0), (0, 255, 0), (75, 0, 130), (127,0,255)]

    # draw progress bar
    if progress > .95:
        w *= progress

        d.ellipse((x + w, y, x + h + w, y + h), fill=(127,0,255))
        d.ellipse((x, y, x + h, y + h), fill='red')
        horizontal_gradient(d, Rect(x + (h / 2), y, x + w + (h / 2), y + h), gradient_color, COLOR)

    elif progress < .05:
        w *= progress

        d.ellipse((x, y, x + h, y + h), fill='red')
        d.ellipse((x + w, y, x + h + w, y + h), fill=bg)

    elif progress < .08:
        w *= progress

        d.ellipse((x, y, x + h, y + h), fill='red')
        d.rectangle((x + w, y, x + h + w, y + h), fill=bg, width=10)


    elif progress > 0:
        w *= progress

        d.ellipse((x, y, x + h, y + h), fill='red')
        horizontal_gradient(d, Rect(x + (h / 2), y, x + w + (h / 2), y + h), gradient_color, COLOR)

    return d


class Rect(object):
    def __init__(self, x1, y1, x2, y2):
        minx, maxx = (x1,x2) if x1 < x2 else (x2,x1)
        miny, maxy = (y1,y2) if y1 < y2 else (y2,y1)
        self.min = Point(minx, miny)
        self.max = Point(maxx, maxy)

    width  = property(lambda self: self.max.x - self.min.x)
    height = property(lambda self: self.max.y - self.min.y)

class Point(object):
    def __init__(self, x, y):
        self.x, self.y = x, y

def horizontal_gradient(draw, rect, color_func, color_palette):
    minval, maxval = 1, len(color_palette)
    delta = maxval - minval
    width = float(rect.width)  # Cache.
    for x in range(int(rect.min.x), int(rect.max.x+1)):
        f = (x - rect.min.x) / width
        val = minval + f * delta
        color = color_func(minval, maxval, val, color_palette)
        draw.line([(x, rect.min.y), (x, rect.max.y)], fill=color)

def gradient_color(minval, maxval, val, color_palette):
    """ Computes intermediate RGB color of a value in the range of minval
        to maxval (inclusive) based on a color_palette representing the range.
    """
    max_index = len(color_palette)-1
    delta = maxval - minval
    if delta == 0:
        delta = 1
    v = float(val-minval) / delta * max_index
    i1, i2 = int(v), min(int(v)+1, max_index)
    (r1, g1, b1), (r2, g2, b2) = color_palette[i1], color_palette[i2]
    f = v - i1
    return int(r1 + f*(r2-r1)), int(g1 + f*(g2-g1)), int(b1 + f*(b2-b1))