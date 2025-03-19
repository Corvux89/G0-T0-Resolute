from __future__ import annotations
from typing import TYPE_CHECKING, Union

import re

import discord
from sqlalchemy.util import asyncio

from Resolute.constants import BOT_OWNERS
from Resolute.models.objects.exceptions import G0T0CommandError

if TYPE_CHECKING:
    from Resolute.models.objects.guilds import PlayerGuild
    from Resolute.models.objects.characters import PlayerCharacter


def dm_check(ctx: discord.ApplicationContext) -> bool:
    if not ctx.guild:
        raise G0T0CommandError("Command is not available in DM's")
    return True


def is_owner(ctx: discord.ApplicationContext) -> bool:
    """
    User is a bot owner (not just a server owner)

    :param ctx: Context
    :return: True if user is in BOT_OWNERS constant, otherwise False
    """
    if hasattr(ctx, "author"):
        author = ctx.author
    else:
        author = ctx.user

    return author.id in BOT_OWNERS


async def is_admin(ctx: Union[discord.ApplicationContext, discord.Interaction]) -> bool:
    """
    User is a designated administrator

    :param ctx: Context
    :return: True if user is a bot owner, can manage the guild, or has a listed role, otherwise False
    """
    from Resolute.models.objects.guilds import PlayerGuild

    guild = await PlayerGuild.get_player_guild(ctx.bot, ctx.guild.id)

    if hasattr(ctx, "author"):
        author = ctx.author
    else:
        author = ctx.user

    if is_owner(ctx) or guild.is_admin(author):
        return True
    else:
        return False


async def is_staff(ctx: discord.ApplicationContext | discord.Interaction) -> bool:
    """
    Check if the user is a staff member.
    This function checks if the user who initiated the context is a staff member
    by verifying their roles against the admin and staff roles defined in the guild.
    Args:
        ctx (discord.ApplicationContext | discord.Interaction): The context of the command or discord.Interaction.
    Returns:
        bool: True if the user is a staff member or the owner, False otherwise.
    """
    from Resolute.models.objects.guilds import PlayerGuild

    guild = await PlayerGuild.get_player_guild(ctx.bot, ctx.guild.id)

    if hasattr(ctx, "author"):
        author = ctx.author
    else:
        author = ctx.user

    if is_owner(ctx) or guild.is_staff(author):
        return True
    else:
        return False


def get_positivity(string) -> bool:
    """
    Determines the positivity of a given string.
    Args:
        string (str or bool): The input string or boolean to evaluate.
    Returns:
        bool: True if the input represents a positive value (e.g., "yes", "true", "1", "enable", "on").
              False if the input represents a negative value (e.g., "no", "false", "0", "disable", "off", "cancel").
              None if the input does not match any recognized positive or negative values.
    """
    if isinstance(string, bool):  # oi!
        return string
    lowered = string.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off", "cancel"):
        return False
    else:
        return None


async def confirm(
    ctx,
    message,
    delete_msgs=False,
    bot=None,
    response_check=get_positivity,
    full_reply: bool = False,
) -> bool | str:
    """
    Asks for user confirmation by sending a message and waiting for a response.
    Args:
        ctx (Context): The context in which the command was invoked.
        message (str): The message to send to the user.
        delete_msgs (bool, optional): Whether to delete the sent and received messages after processing. Defaults to False.
        bot (Bot, optional): The bot instance to use for waiting for the response. Defaults to None.
        response_check (callable, optional): A function to check the positivity of the response. Defaults to get_positivity.
        full_reply (bool, optional): Whether to return the full reply object instead of just the content. Defaults to False.
    Returns:
        bool | str: The result of the response check, the full reply, or the reply content, depending on the parameters.
    """
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
    """
    Checks if a message is from the same author and channel as the context.
    Args:
        ctx: The context object which contains information about the command invocation.
    Returns:
        bool: A function that takes a message as an argument and returns True if the message
              is from the same author and channel as the context, otherwise False.
    """
    if hasattr(ctx, "author"):
        author = ctx.author
    else:
        author = ctx.user

    def chk(msg):
        return msg.author == author and msg.channel == ctx.channel

    return chk


def find_character(
    name: str, characters: list[PlayerCharacter]
) -> list[PlayerCharacter]:
    """
    Finds characters in a list of PlayerCharacter objects that match a given name.
    Args:
        name (str): The name to search for.
        characters (list[PlayerCharacter]): The list of PlayerCharacter objects to search within.
    Returns:
        list[PlayerCharacter]: A list of PlayerCharacter objects that match the given name.
        If no direct match is found, returns a list of PlayerCharacter objects that partially match the given name.
    """
    direct_match = [c for c in characters if c.name.lower() == name.lower()]

    if not direct_match:
        partial_matches = [c for c in characters if name.lower() in c.name.lower()]
        return partial_matches

    return direct_match


def process_message(
    message: str, g: PlayerGuild, member: discord.Member = None, mappings: dict = None
) -> str:
    def process_message(
        message: str,
        g: PlayerGuild,
        member: discord.Member = None,
        mappings: dict = None,
    ) -> str:
        """
        Processes a message by replacing placeholders with actual mentions and values.
        Args:
            message (str): The message containing placeholders to be replaced.
            g (PlayerGuild): The guild object containing channels and roles.
            member (discord.Member, optional): The member to mention in the message. Defaults to None.
            mappings (dict, optional): A dictionary of additional placeholders and their replacements. Defaults to None.
        Returns:
            str: The processed message with placeholders replaced by actual mentions and values.
        """

    channel_mentions = re.findall(r"{#([^}]*)}", message)
    role_mentions = re.findall(r"{@([^}]*)}", message)

    for chan in channel_mentions:
        if channel := discord.utils.get(g.guild.channels, name=chan):
            message = message.replace("{#" + chan + "}", f"{channel.mention}")

    for r in role_mentions:
        if role := discord.utils.get(g.guild.roles, name=r):
            message = message.replace("{@" + r + "}", f"{role.mention}")

    if mappings:
        for mnemonic, value in mappings.items():
            message = message.replace("{" + mnemonic + "}", value)

    if member:
        message = message.replace("{user}", f"{member.mention}")

    return message


async def get_webhook(channel: discord.TextChannel) -> discord.Webhook:
    """
    Asynchronously retrieves or creates a webhook for the given channel.
    If the channel is a Thread or ForumChannel, it retrieves the parent text channel.
    It then checks for existing webhooks in the text channel and returns the first one with a token.
    If no such webhook exists, it creates a new webhook with the name "G0T0 Hook".
    Args:
        channel (TextChannel): The channel to retrieve or create the webhook for.
    Returns:
        Webhook: The existing or newly created webhook for the channel.
    """
    if isinstance(channel, (discord.Thread, discord.ForumChannel)):
        text_channel = channel.parent
    else:
        text_channel = channel

    webhooks = await text_channel.webhooks()

    for hook in webhooks:
        if hook.token:
            return hook

    hook = await text_channel.create_webhook(
        name="G0T0 Hook", reason="G0T0 Bot Webhook"
    )

    return hook


def paginate(choices: list[str], per_page: int) -> list[list[str]]:
    """
    Splits a list of choices into a list of lists, each containing a maximum number of items specified by per_page.
    Args:
        choices (list[str]): The list of items to be paginated.
        per_page (int): The maximum number of items per page.
    Returns:
        list[list[str]]: A list of lists, where each sublist represents a page of items.
    """
    out = []
    for idx in range(0, len(choices), per_page):
        out.append(choices[idx : idx + per_page])
    return out


async def try_delete(message: discord.Message) -> None:
    """
    Attempts to delete a given message asynchronously.
    Args:
        message (Message): The message object to be deleted.
    Returns:
        None
    Note:
        If an exception occurs during the deletion process, it is silently ignored.
    """
    try:
        await message.delete()
    except:
        pass


async def get_selection(
    ctx: discord.ApplicationContext,
    choices: list[str],
    delete: bool = True,
    dm: bool = False,
    message: str = None,
    force_select: bool = False,
    query_message: str = None,
) -> str:
    """
    Asynchronously prompts the user to select an option from a list of choices.
    Parameters:
        ctx (discord.ApplicationContext): The context in which the command was invoked.
        choices (list[str]): A list of string choices for the user to select from.
        delete (bool, optional): Whether to delete the selection message after selection. Defaults to True.
        dm (bool, optional): Whether to send the selection message as a direct message. Defaults to False.
        message (str, optional): An additional message to display in the embed. Defaults to None.
        force_select (bool, optional): Forces the selection prompt even if there is only one choice. Defaults to False.
        query_message (str, optional): A custom query message to display in the embed. Defaults to None.
    Returns:
        str or None: The selected choice as a string, or None if the selection was cancelled or timed out.
    Raises:
        ValueError: If the user input is not a valid choice number.
    """
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
            embed.add_field(name="Note", value=message, inline=False)

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

        if m.content.lower() == "n":
            if page + 1 < len(pages):
                page += 1
            else:
                await ctx.channel.send("You are already on the last page")
        elif m.content.lower() == "p":
            if page - 1 >= 0:
                page -= 1
            else:
                await ctx.channel.send("You are already on the first page")
        else:
            break

    if delete:
        if not dm:
            await try_delete(select_msg)
        if m is not None:
            await try_delete(m)

    if m is None or m.content.lower() == "c":
        return None

    idx = int(m.content) - 1

    return choices[idx]


def chunk_text(
    text, max_chunk_size=1024, chunk_on=("\n\n", "\n", ". ", ", ", " "), chunker_i=0
):
    """
    Recursively chunks *text* into a list of str, with each element no longer than *max_chunk_size*.
    Prefers splitting on the elements of *chunk_on*, in order.
    """

    if len(text) <= max_chunk_size:  # the chunk is small enough
        return [text]
    if chunker_i >= len(chunk_on):  # we have no more preferred chunk_on characters
        # optimization: instead of merging a thousand characters, just use list slicing
        return [
            text[:max_chunk_size],
            *chunk_text(text[max_chunk_size:], max_chunk_size, chunk_on, chunker_i + 1),
        ]

    # split on the current character
    chunks = []
    split_char = chunk_on[chunker_i]
    for chunk in text.split(split_char):
        chunk = f"{chunk}{split_char}"
        if len(chunk) > max_chunk_size:  # this chunk needs to be split more, recurse
            chunks.extend(chunk_text(chunk, max_chunk_size, chunk_on, chunker_i + 1))
        elif (
            chunks and len(chunk) + len(chunks[-1]) <= max_chunk_size
        ):  # this chunk can be merged
            chunks[-1] += chunk
        else:
            chunks.append(chunk)

    # if the last chunk is just the split_char, yeet it
    if chunks[-1] == split_char:
        chunks.pop()

    # remove extra split_char from last chunk
    chunks[-1] = chunks[-1][: -len(split_char)]
    return chunks


async def get_last_message_in_channel(channel: discord.TextChannel) -> discord.Message:
    """
    Retrieve the last message in a given text channel.
    This function attempts to get the last message in the specified channel.
    It first checks if the channel's `last_message` attribute is set. If not,
    it tries to fetch the last message from the channel's history. If that
    also fails, it attempts to fetch the message using the channel's
    `last_message_id`. If all attempts fail, it returns None.
    Args:
        channel (TextChannel): The text channel from which to retrieve the last message.
    Returns:
        Message: The last message in the channel, or None if it cannot be retrieved.
    """
    if not (last_message := channel.last_message):
        try:
            last_message = next((msg for msg in channel.history(limit=1)), None)
        except:
            try:
                last_message = await channel.fetch_message(channel.last_message_id)
            except:
                return None

    return last_message
