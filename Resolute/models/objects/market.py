import discord

from Resolute.models.categories.categories import TransactionSubType, TransactionType
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player


class MarketTransaction(object):
    def __init__(self, player: Player, **kwargs):
        self.player = player

        self.type: TransactionType = kwargs.get('type')
        self.subtype: TransactionSubType = kwargs.get('subtype')
        self.notes = kwargs.get('notes')
        self.cc: int = kwargs.get('cc', 0)
        self.credits: int = kwargs.get('credits', 0)
        self.character: PlayerCharacter = kwargs.get('character')
        self.message: discord.Message = kwargs.get('message')

    @property
    def format_type(self):
        if not self.type:
            return ""
        return f"{self.type.value}{f' ({self.subtype.value})' if self.subtype else ''}"
    
    @property
    def log_notes(self):
        return f"{self.format_type}\n\n{self.notes}"

