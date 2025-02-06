from discord import (ButtonStyle, HTTPException, Interaction, Member, Message,
                     SelectOption)
from discord.ui import Button, Select, button, select

from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI, CHANNEL_BREAK
from Resolute.models.categories.categories import Activity
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class LogMap(object):
    """
    A class to represent a log map for a player.
    Attributes:
    ----------
    player : Player
        The player associated with the log map.
    character : PlayerCharacter, optional
        The character associated with the player (default is None).
    host : bool
        Indicates if the player is the host (default is False).
    Methods:
    -------
    __init__(player, **kwargs)
        Initializes the LogMap with a player and optional character.
    """

    player: Player
    character: PlayerCharacter = None
    host: bool = False

    def __init__(self, player, **kwargs):
        self.player = player
        self.character = kwargs.get('character')


class MessageLog(InteractiveView):
    """
    MessageLog class that inherits from InteractiveView.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to copy for the menu.
        bot (G0T0Bot): Instance of the G0T0Bot.
        msg (Message): Instance of the Message.
        activity (Activity, optional): Instance of the Activity. Defaults to None.
        members (list[LogMap]): List of LogMap instances. Defaults to an empty list.
    Methods:
        on_timeout: Asynchronous method that deletes the message if it exists and handles HTTP exceptions.
    """

    __menu_copy_attrs__ = ("bot", "msg", "activity")
    bot: G0T0Bot
    msg: Message
    activity: Activity = None
    members: list[LogMap] = []

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.delete()
        except HTTPException:
            pass

class MessageLogUI(MessageLog):
    """
    A UI class for handling message logs in the G0-T0 bot.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: Member, message: Message)
        Creates a new instance of MessageLogUI.
    _before_send(self)
        Prepares the UI elements before sending the message.
    activity_select(self, act: Select, interaction: Interaction)
        Handles the selection of an activity type.
    host_select(self, host: Select, interaction: Interaction)
        Handles the selection of a host.
    character_select(self, char: Select, interaction: Interaction)
        Handles the selection of a character.
    log(self, _: Button, interaction: Interaction)
        Logs the activity and sends the appropriate reactions and messages.
    exit(self, *_)
        Cancels the logging process and performs cleanup.
    """

    @classmethod
    async def new(cls, bot: G0T0Bot, owner: Member, message: Message):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.msg = message
        inst.members = []

        for member in message.mentions:
            player = await bot.get_player(member.id, owner.guild.id)

            if len(player.characters) == 0:
                raise CharacterNotFound(player.member)

            inst.members.append(LogMap(player, character=player.characters[0] if len(player.characters) == 1 else None))
        return inst
    
    async def _before_send(self):
        act_list = [
            SelectOption(label="RP", value="RP", default=True if self.activity and self.activity.value == "RP" else False),
            SelectOption(label="Snapshot", value="SNAPSHOT", default=True if self.activity and self.activity.value == "SNAPSHOT" else False),
            SelectOption(label="Narrative Arena", value="RP_HOST", default=True if self.activity and self.activity.value == "RP_HOST" else False)
        ]
        self.activity_select.options = act_list

        if self.activity:
                self.remove_item(self.activity_select)

                if self.activity.value == "RP_HOST" and not (host := next((c for c in self.members if c.host == True), None)):
                    member_list = [
                        SelectOption(label=f"{m.player.member.display_name}", value=f"{m.player.id}") for m in self.members
                    ]
                    self.host_select.options = member_list
                    self.add_item(self.host_select)

                elif member := next((c for c in self.members if not c.character and c.host == False), None):
                    if self.get_item("character_select") is None:
                        self.add_item(self.character_select)

                    if self.get_item("host_select") is not None:
                        self.remove_item(self.host_select)

                    self.log.disabled = True

                    chars = [SelectOption(label=f"{c.name}", value=f"{c.id}") for c in member.player.characters]
                    self.character_select.placeholder = f"Select a character for {member.player.member.display_name}"
                    self.character_select.options = chars
                else:
                    self.log.disabled = False
                    self.remove_item(self.character_select)
                    self.remove_item(self.host_select)
            
        else:
            self.remove_item(self.character_select)
            self.remove_item(self.host_select)
            self.log.disabled = True

    @select(placeholder="Select a log type", custom_id="activity_select")
    async def activity_select(self, act: Select, interaction: Interaction):
        self.activity = self.bot.compendium.get_activity(act.values[0])
        await self.refresh_content(interaction)

    @select(placeholder="Select the host", custom_id="host_select")
    async def host_select(self, host: Select, interaction: Interaction):
        if member := next((m for m in self.members if m.player.id == int(host.values[0])), None):
            member.host = True
        await self.refresh_content(interaction)

    @select(placeholder="Select a log character", custom_id="character_select")
    async def character_select(self, char: Select, interaction: Interaction):
        if member := next((c for c in self.members if not c.character and c.host == False), None):
            member.character = next((c for c in member.player.characters if c.id == int(char.values[0])), None)
        await self.refresh_content(interaction)

    @button(label="Log", style=ButtonStyle.primary, row=2)
    async def log(self, _: Button, interaction: Interaction):
        for member in self.members:
            if self.activity.value == "RP_HOST":
                await self.bot.log(interaction, member.player, self.owner, self.activity if member.host else "RP",
                                   character=member.character)
            else:
                await self.bot.log(interaction, member.player, self.owner, self.activity,
                                   character=member.character)
                
        await self.msg.add_reaction(APPROVAL_EMOJI[0])
        if self.activity.value in ["RP", "RP_HOST"]:
            await interaction.channel.send(CHANNEL_BREAK)
        await self.on_timeout()
    
    @button(label="Cancel", style=ButtonStyle.danger, row=2)
    async def exit(self, *_):
        await self.on_timeout()
