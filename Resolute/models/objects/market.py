import re

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.categories.categories import TransactionSubType, TransactionType
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player


class MarketTransaction(object):
    """
    Represents a market transaction in the game.
    Attributes:
        player (Player): The player involved in the transaction.
        type (TransactionType): The type of the transaction.
        subtype (TransactionSubType): The subtype of the transaction.
        notes (str): Additional notes about the transaction.
        cc (int): The amount of CC (in-game currency) involved in the transaction.
        credits (int): The amount of credits involved in the transaction.
        character (PlayerCharacter): The character involved in the transaction.
        message (Message): The message associated with the transaction.
    Methods:
        format_type: Returns a formatted string representation of the transaction type and subtype.
        log_notes: Returns a formatted string of the transaction type and notes.
        get_request(bot, message): Asynchronously parses a message to create a MarketTransaction instance.
    """

    def __init__(self, player: Player, **kwargs):
        self.player = player

        self.type: TransactionType = kwargs.get("type")
        self.subtype: TransactionSubType = kwargs.get("subtype")
        self.notes = kwargs.get("notes")
        self.cc: int = kwargs.get("cc", 0)
        self.credits: int = kwargs.get("credits", 0)
        self.character: PlayerCharacter = kwargs.get("character")
        self.message: discord.Message = kwargs.get("message")

    @property
    def format_type(self) -> str:
        if not self.type:
            return ""
        return f"{self.type.value}{f' ({self.subtype.value})' if self.subtype else ''}"

    @property
    def log_notes(self) -> str:
        return f"{self.format_type}\n\n{self.notes}"

    async def get_request(bot: G0T0Bot, message: discord.Message):

        def get_match(pattern, text, group=1, default=None):
            match = re.search(pattern, text, re.DOTALL)
            return (
                match.group(group)
                if match and match.group(group) != "None"
                else default
            )

        try:
            embed = message.embeds[0]
        except:
            raise G0T0Error("This is not the command you're looking for. Move along.")

        player_id = get_match(r"\*\*Player\*\*:\s*<@(\d+)>\n", embed.description)
        char_id = get_match(r"\*\*Character\*\*:.*\[(\d+)\]", embed.description)
        type = get_match(f"(?<=\*\*Type\*\*:)\s(.*?)(?=\n)", embed.description)

        if player_id is None or char_id is None or type is None:
            return None

        subtype = get_match(r"\(([^)]+)\)", type)
        if subtype:
            type = type.replace(f" ({subtype})", "")

        cc = get_match(r"\*\*Total\sCC\*\*:\s*([\d,]+)", embed.description, 1, "0")
        credits = get_match(
            r"\*\*Total\sCredits\*\*:\s*([\d,]+)", embed.description, 1, "0"
        )

        if len(embed.fields) > 0:
            notes = "".join(x.value for x in embed.fields)
        else:
            notes = None

        player = await bot.get_player(int(player_id), message.guild.id)

        if char_id:
            character = await bot.get_character(char_id)
        else:
            character = None

        transaction = MarketTransaction(
            player,
            type=bot.compendium.get_object(TransactionType, type),
            subtype=bot.compendium.get_object(TransactionSubType, subtype),
            notes=notes,
            cc=int(cc.replace(",", "")),
            credits=int(credits.replace(",", "")),
            character=character,
            message=message,
        )

        return transaction
