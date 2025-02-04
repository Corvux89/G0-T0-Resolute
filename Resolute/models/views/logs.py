from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class LogPrompt(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "member", "activity", "credits", "notes", "cc", "ignore_handicap", "show_values")
    owner: discord.Member = None
    member = discord.Member = None
    bot: G0T0Bot
    activity: str
    credits: int = 0
    cc: int = 0
    player: Player
    character: PlayerCharacter = None
    notes: str = None
    ignore_handicap: bool = False
    show_values: bool = False

   
    
class LogPromptUI(LogPrompt):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, member: discord.Member, player: Player, activity: str, **kwargs):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.member = member
        inst.player = player
        inst.activity = activity
        inst.credits = kwargs.get('credits', 0)
        inst.cc = kwargs.get('cc', 0)
        inst.notes = kwargs.get('notes')
        inst.character = player.characters[0] if len(player.characters) > 0 else None
        inst.ignore_handicap = kwargs.get('ignore_handicap', False)
        inst.show_values = kwargs.get('show_values', False)
        return inst

    
    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(self, char: discord.ui.Select, interation: discord.Interaction):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interation)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, row=2)
    async def confirm_log(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.bot.log(interaction, self.player, self.owner, self.activity,
                           character=self.character,
                           notes=self.notes,
                           cc=self.cc,
                           credits=self.credits,
                           ignore_handicap=self.ignore_handicap,
                           show_values=self.show_values)
        await self.on_timeout()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if not self.player.characters:
            self.on_timeout()
        
        char_list = []
        for char in self.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{self.player.characters.index(char)}", default=True if self.player.characters.index(char) == self.player.characters.index(self.character) else False))
        self.character_select.options = char_list   
    
    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Select a character to log this for:\n"}
    