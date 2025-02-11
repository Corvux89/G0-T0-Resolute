import logging
from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.channel_admin import ChannelEmbed
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)

owner_overwrites = discord.PermissionOverwrite(view_channel=True,
                                    manage_messages=True,
                                    send_messages=True)

general_overwrites = discord.PermissionOverwrite(view_channel=True,
                                        send_messages=False)

bot_overwrites = discord.PermissionOverwrite(view_channel=True,
                                    send_messages=True,
                                    manage_messages=True,
                                    manage_channels=True)                                             

readonly_overwrites = discord.PermissionOverwrite(view_channel=True,
                                        send_messages=False,
                                        add_reactions=False,
                                        read_messages=True,
                                        send_tts_messages=False,
                                        manage_messages=False,
                                        manage_roles=False,
                                        send_messages_in_threads=False)


class ChannelAdmin(InteractiveView):
    """
    ChannelAdmin class for handling administrative interactions within a specific channel.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to be copied in the menu.
        bot (G0T0Bot): Instance of the bot.
        channel (discord.TextChannel): The text channel associated with this admin view.
    """

    __menu_copy_attrs__ = ("bot", "channel")
    bot: G0T0Bot
    channel: discord.TextChannel = None

class ChannelAdminUI(ChannelAdmin):
    """
    ChannelAdminUI class provides a user interface for managing Discord channels.
    Methods:
        new(cls, bot, owner):
            Creates a new instance of ChannelAdminUI with the given bot and owner.
        _before_send(self):
            Prepares the UI before sending by enabling or disabling the player channel based on the selected channel.
        channel_select(self, c: discord.ui.Select, interaction: discord.Interaction):
            Handles the selection of a channel to manage and refreshes the content accordingly.
        new_player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
            Initiates the process to create a new player channel.
        player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
            Checks if the selected channel is managed by a player and defers to the edit player channel process if true.
        exit(self, *_):
            Exits the UI and handles timeout.
        get_content(self) -> Mapping:
            Returns the content to be displayed in the UI, including an embed for the selected channel or a prompt to pick an option.
    """

    @classmethod
    def new(cls, bot, owner):
        inst = cls(owner=owner)
        inst.bot = bot
        return inst
    
    async def _before_send(self):
        self.player_channel.disabled = False if self.channel else True

    @discord.ui.channel_select(placeholder="Channel to manage", channel_types=[discord.ChannelType(0)])
    async def channel_select(self, c : discord.ui.Select, interaction: discord.Interaction):
        self.channel = c.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="New Player Channel", style=discord.ButtonStyle.primary, row=2)
    async def new_player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_NewPlayerchannel, interaction)

    @discord.ui.button(label="Edit Player Channel", style=discord.ButtonStyle.primary, row=2)
    async def player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        managed = False
        for target in self.channel.overwrites:
            if isinstance(target, discord.Member):
                if self.channel.overwrites[target].manage_messages == True:
                    managed = True
        
        if not managed:
            raise G0T0Error("This doesn't look to be a player managed channel")
        else:
            await self.defer_to(_EditPlayerChannel, interaction)

    # TODO: Archive channel - Save to attachment
    # @discord.ui.button(label="Archive Channel", style=discord.discord.ButtonStyle.primary, row=3)
    # async def archive_channel(self, _: discord.ui.Button, interaction: discord.discord.Interaction):
    #     await self.refresh_content(interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=4)
    async def exit(self, *_):
        await self.on_timeout()

    async def get_content(self) -> Mapping:
        if not self.channel:
            return {"embed": None, "content": "Pick an option"}
        else:
            return {"embed": ChannelEmbed(self.channel), "content": ""}
    
class _EditPlayerChannel(ChannelAdmin):
    member: discord.Member = None

    @discord.ui.user_select(placeholder="Channel Owner")
    async def channel_owner(self, m: discord.ui.Select, interaction: discord.Interaction):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Owner", style=discord.ButtonStyle.primary, row=2)
    async def add_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.member in self.channel.overwrites.keys() and self.channel.overwrites_for(self.member).manage_messages == True:
            await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is already a channel owner."), delete_after=5)
        else:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] added to {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await self.channel.set_permissions(self.member, overwrite=owner_overwrites)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Owner", style=discord.ButtonStyle.red, row=2)
    async def remove_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.member in self.channel.overwrites.keys() and self.channel.overwrites_for(self.member).manage_messages == True:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] removed from {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await self.channel.set_permissions(self.member, overwrite=None)
        else:
            await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not a channel owner."), delete_after=5)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ChannelAdminUI, interaction)

    async def get_content(self) -> Mapping:
        return {"embed": ChannelEmbed(self.channel), "content": ""}
    
class _NewPlayerchannel(ChannelAdmin):
    category: discord.TextChannel = None
    member: discord.Member = None
    name = None
    
    @discord.ui.user_select(placeholder="Channel Owner")
    async def channel_owner(self, m: discord.ui.Select, interaction: discord.Interaction):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @discord.ui.channel_select(placeholder="Category", channel_types=[discord.ChannelType(4)])
    async def channel_category(self, cat: discord.ui.Select, interaction: discord.Interaction):
        self.category = cat.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Channel Information", style=discord.ButtonStyle.primary, row=3)
    async def channel_info(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ChannelInfoModal(self.name)
        response = await self.prompt_modal(interaction, modal)
        self.name = response.name
        await self.refresh_content(interaction)

    @discord.ui.button(label="Create Channel", style=discord.ButtonStyle.green, row=3, disabled=True)
    async def channel_create(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.channel = await self._create_channel(self.name)
        log.info(f"CHANNEL ADMIN: {self.channel.name} [ {self.channel.id} ] created for {self.member} [ {self.member.id} ] by {interaction.user} [ {interaction.user.id} ]")
        await self.channel.send(f"{self.member.mention} welcome to your new channel.\n"
                                f"Go ahead and set everything up.\n"
                                f"1. Make sure you can delete this message.\n"
                                f"2. Use `/room settings` to see your management options")
        await self.defer_to(ChannelAdminUI, interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ChannelAdminUI, interaction)

    async def _before_send(self):
        if self.name is not None and self.member is not None and self.category is not None:
            self.channel_create.disabled = False
        else:
            self.channel_create.disabled=True

    async def get_content(self) -> Mapping:
        embed = discord.Embed(title="New Character Channel Information")
        embed.description = f"**Channel Name**: {self.name}\n"\
                            f"**Channel Owner**: {self.member.mention if self.member else 'None'}\n"\
                            f"**Channel Category**: {self.category.mention if self.category else 'None'}\n"
        return {"embed": embed, "content": ""}
    
    async def _create_channel(self, name: str) -> discord.TextChannel:
        channel_overwrites = self.category.overwrites
        guild = await self.bot.get_player_guild(self.category.guild.id)

        channel_overwrites[self.member] = owner_overwrites

        if guild.bot_role:
            channel_overwrites[guild.bot_role] = bot_overwrites

        if guild.member_role:
            channel_overwrites[guild.member_role] = general_overwrites

        if guild.staff_role:
            channel_overwrites[guild.staff_role] = general_overwrites

        channel = await guild.guild.create_text_channel(
            name=name,
            category=self.category,
            overwrites=channel_overwrites,
            reason=f"Channel admin command"
        )

        return channel

class ChannelInfoModal(discord.ui.Modal):
    name = None

    def __init__(self, name = None):
        super().__init__(title="New Player Channel Information")

        self.add_item(discord.ui.InputText(label="Channel Name", placeholder="Channel Name", max_length=100, value=f"{name}"))

    async def callback(self, interaction: discord.Interaction):
        self.name = self.children[0].value

        await interaction.response.defer()
        self.stop()
    