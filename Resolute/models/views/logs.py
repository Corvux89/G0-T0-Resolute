from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class LogPrompt(InteractiveView):
    """
    LogPrompt is a class that represents an interactive view for logging prompts.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple of attribute names to be copied in the menu.
        owner (discord.Member): The owner of the log prompt.
        member (discord.Member): The member associated with the log prompt.
        bot (G0T0Bot): The bot instance associated with the log prompt.
        activity (str): The activity description.
        credits (int): The number of credits, default is 0.
        cc (int): The cc value, default is 0.
        player (Player): The player associated with the log prompt.
        character (PlayerCharacter): The player character, default is None.
        notes (str): Additional notes, default is None.
        ignore_handicap (bool): Flag to ignore handicap, default is False.
        show_values (bool): Flag to show values, default is False.
    """

    __menu_copy_attrs__ = (
        "bot",
        "player",
        "activity",
        "credits",
        "notes",
        "cc",
        "ignore_handicap",
        "show_values",
        "author",
    )
    owner: discord.Member = None
    bot: G0T0Bot
    activity: str
    credits: int = 0
    cc: int = 0
    player: Player
    author: Player
    character: PlayerCharacter = None
    notes: str = None
    ignore_handicap: bool = False
    show_values: bool = False


class LogPromptUI(LogPrompt):
    """
    LogPromptUI is a user interface class for logging activities in the G0-T0 Resolute bot.
    Methods:
        new(cls, bot: G0T0Bot, owner: discord.Member, member: discord.Member, player: Player, activity: str, **kwargs):
            Class method to create a new instance of LogPromptUI.
        character_select(self, char: discord.ui.Select, interation: discord.Interaction):
            Async method to handle character selection from a dropdown menu.
        confirm_log(self, _: discord.ui.Button, interaction: discord.Interaction):
            Async method to confirm and log the selected activity.
        exit(self, *_):
            Async method to cancel the logging process.
        _before_send(self):
            Async method to prepare the UI before sending it to the user.
        get_content(self) -> Mapping:
            Async method to get the content to be displayed in the UI.
    """

    @classmethod
    def new(cls, bot: G0T0Bot, owner: Player, player: Player, activity: str, **kwargs):
        inst = cls(owner=owner.member)
        inst.bot = bot
        inst.player = player
        inst.author = owner
        inst.activity = activity
        inst.credits = kwargs.get("credits", 0)
        inst.cc = kwargs.get("cc", 0)
        inst.notes = kwargs.get("notes")
        inst.character = player.characters[0] if len(player.characters) > 0 else None
        inst.ignore_handicap = kwargs.get("ignore_handicap", False)
        inst.show_values = kwargs.get("show_values", False)
        return inst

    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(
        self, char: discord.ui.Select, interation: discord.Interaction
    ):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interation)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, row=2)
    async def confirm_log(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.bot.log(
            interaction,
            self.player,
            self.author,
            self.activity,
            character=self.character,
            notes=self.notes,
            cc=self.cc,
            credits=self.credits,
            ignore_handicap=self.ignore_handicap,
            show_values=self.show_values,
        )
        await self.on_timeout()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if not self.player.characters:
            self.on_timeout()

        char_list = []
        for char in self.player.characters:
            char_list.append(
                discord.SelectOption(
                    label=f"{char.name}",
                    value=f"{self.player.characters.index(char)}",
                    default=(
                        True
                        if self.player.characters.index(char)
                        == self.player.characters.index(self.character)
                        else False
                    ),
                )
            )
        self.character_select.options = char_list

    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Select a character to log this for:\n"}
