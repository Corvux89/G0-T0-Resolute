import discord
import logging

from typing import Mapping
from discord.ui import Modal, InputText

from Resolute.bot import G0T0Bot
from Resolute.helpers.channel_admin import add_owner, create_channel, remove_owner
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.channel_admin import ChannelEmbed
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)


class ChannelAdmin(InteractiveView):
    __menu_copy_attrs__ = ("bot", "channel")
    bot: G0T0Bot
    channel: discord.TextChannel = None

class ChannelAdminUI(ChannelAdmin):
    @classmethod
    def new(cls, bot, owner):
        inst = cls(owner=owner)
        inst.bot = bot
        return inst

    @discord.ui.channel_select(placeholder="Channel to manage", channel_types=[discord.ChannelType(0)])
    async def channel_select(self, c : discord.ui.Select, interaction: discord.Interaction):
        self.channel = c.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="New Player Channel", style=discord.ButtonStyle.primary, row=2)
    async def new_player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_NewPlayerchannel, interaction)

    @discord.ui.button(label="Edit Player Channel", style=discord.ButtonStyle.primary, row=2)
    async def player_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.channel and self.channel is not None:
            managed = False
            for target in self.channel.overwrites:
                if isinstance(target, discord.member.Member):
                    if self.channel.overwrites[target].manage_messages == True:
                        managed = True
            
            if not managed:
                await interaction.channel.send(embed=ErrorEmbed(description="This doesn't look to be a player managed channel"), delete_after=5)
                await self.refresh_content(interaction)
            else:
                await self.defer_to(_EditPlayerChannel, interaction)
        else:
            await interaction.channel.send(embed=ErrorEmbed(description="Select a channel to edit first."), delete_after=5)

    # @discord.ui.button(label="Archive Channel", style=discord.ButtonStyle.primary, row=3)
    # async def archive_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
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
            await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} is already a channel owner."), delete_after=5)
        else:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] added to {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await add_owner(self.channel, self.member)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Owner", style=discord.ButtonStyle.red, row=2)
    async def remove_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.member in self.channel.overwrites.keys() and self.channel.overwrites_for(self.member).manage_messages == True:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] removed from {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await remove_owner(self.channel, self.member)
        else:
            await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} is not a channel owner."), delete_after=5)
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
        self.channel = await create_channel(self.name, self.category, self.member)
        log.info(f"CHANNEL ADMIN: {self.channel.name} [ {self.channel.id} ] created for {self.member} [ {self.member.id} ] by {interaction.user} [ {interaction.user.id} ]")
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


class ChannelInfoModal(Modal):
    name = None

    def __init__(self, name = None):
        super().__init__(title="New Player Channel Information")

        self.add_item(InputText(label="Channel Name", placeholder="Channel Name", max_length=100, value=f"{name}"))

    async def callback(self, interaction: discord.Interaction):
        self.name = self.children[0].value

        await interaction.response.defer()
        self.stop()
    