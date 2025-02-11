
import logging
from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)


class AdminView(InteractiveView):
    """
    AdminView class that inherits from InteractiveView.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple containing attributes to be copied in the menu.
        bot (G0T0Bot): An instance of the G0T0Bot class.
    """
    __menu_copy_attrs__ = ("bot")
    bot: G0T0Bot

class AdminMenuUI(AdminView):
    """
    AdminMenuUI is a user interface class for the admin menu in the bot application.
    Methods:
        new(cls, owner, bot):
            Creates a new instance of AdminMenuUI with the specified owner and bot.
        message(self, _: discord.ui.Button, interaction: Interaction):
            Sends a message when the "Send message" button is clicked.
        exit(self, *_):
            Exits the admin menu when the "Exit" button is clicked.
        get_content(self) -> Mapping:
            Returns the content to be displayed in the admin menu.
    """
    @classmethod
    def new(cls, owner, bot):
        inst = cls(owner=owner)
        inst.bot = bot
        return inst
    
    @discord.ui.button(label="Send message", style=discord.ButtonStyle.primary, row=1)
    async def message(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_BotMessage, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()
    
    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Pick an Option"}
    
class _BotMessage(AdminView):
    channel: discord.TextChannel = None

    @discord.ui.channel_select(placeholder="Channel to message", channel_types=[discord.ChannelType(0)])
    async def channel_select(self, c: discord.ui.Select, interaction: discord.Interaction):
        self.channel = c.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.primary, row=2, disabled=True)
    async def send_message(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = MessageModal()
        response = await self.prompt_modal(interaction, modal)

        if response.message is not None and response.message != "":
            log.info(f"ADMIN: Bot message from {interaction.user} [ {interaction.user.id} ] to {self.channel.name} [ {self.channel.id} ]")
            await self.channel.send(response.message)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(AdminMenuUI, interaction)

    async def _before_send(self):
        if self.channel is None:
            self.send_message.disabled = True
        else:
            self.send_message.disabled=False

    async def get_content(self) -> Mapping:
        content = f"{f'**Channel**: {self.channel.name}' if self.channel else 'Pick a channel'}"
        return {"embed": None, "content": content}

class MessageModal(discord.ui.Modal):
    message: str = None

    def __init__(self):
        super().__init__(title="Message Content")

        self.add_item(discord.ui.InputText(label="Message Text", style=discord.ui.InputTextStyle.long, max_length=2000))

    async def callback(self, interaction: discord.Interaction):
        self.message = self.children[0].value 

        await interaction.response.defer()
        self.stop()
