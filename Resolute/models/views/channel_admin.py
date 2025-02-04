import logging
from typing import Mapping

from discord import (ButtonStyle, ChannelType, Embed, Interaction, Member,
                     PermissionOverwrite, TextChannel)
from discord.ui import (Button, InputText, Modal, Select, button,
                        channel_select, user_select)

from Resolute.bot import G0T0Bot
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.channel_admin import ChannelEmbed
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)

owner_overwrites = PermissionOverwrite(view_channel=True,
                                    manage_messages=True,
                                    send_messages=True)

general_overwrites = PermissionOverwrite(view_channel=True,
                                        send_messages=False)

bot_overwrites = PermissionOverwrite(view_channel=True,
                                    send_messages=True,
                                    manage_messages=True,
                                    manage_channels=True)                                             

readonly_overwrites = PermissionOverwrite(view_channel=True,
                                        send_messages=False,
                                        add_reactions=False,
                                        read_messages=True,
                                        send_tts_messages=False,
                                        manage_messages=False,
                                        manage_roles=False,
                                        send_messages_in_threads=False)


class ChannelAdmin(InteractiveView):
    __menu_copy_attrs__ = ("bot", "channel")
    bot: G0T0Bot
    channel: TextChannel = None

class ChannelAdminUI(ChannelAdmin):
    @classmethod
    def new(cls, bot, owner):
        inst = cls(owner=owner)
        inst.bot = bot
        return inst
    
    async def _before_send(self):
        self.player_channel.disabled = False if self.channel else True

    @channel_select(placeholder="Channel to manage", channel_types=[ChannelType(0)])
    async def channel_select(self, c : Select, interaction: Interaction):
        self.channel = c.values[0]
        await self.refresh_content(interaction)

    @button(label="New Player Channel", style=ButtonStyle.primary, row=2)
    async def new_player_channel(self, _: Button, interaction: Interaction):
        await self.defer_to(_NewPlayerchannel, interaction)

    @button(label="Edit Player Channel", style=ButtonStyle.primary, row=2)
    async def player_channel(self, _: Button, interaction: Interaction):
        managed = False
        for target in self.channel.overwrites:
            if isinstance(target, Member):
                if self.channel.overwrites[target].manage_messages == True:
                    managed = True
        
        if not managed:
            raise G0T0Error("This doesn't look to be a player managed channel")
        else:
            await self.defer_to(_EditPlayerChannel, interaction)

    # TODO: Archive channel - Save to attachment
    # @discord.ui.button(label="Archive Channel", style=discord.ButtonStyle.primary, row=3)
    # async def archive_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
    #     await self.refresh_content(interaction)

    @button(label="Exit", style=ButtonStyle.danger, row=4)
    async def exit(self, *_):
        await self.on_timeout()

    async def get_content(self) -> Mapping:
        if not self.channel:
            return {"embed": None, "content": "Pick an option"}
        else:
            return {"embed": ChannelEmbed(self.channel), "content": ""}
    
class _EditPlayerChannel(ChannelAdmin):
    member: Member = None

    @user_select(placeholder="Channel Owner")
    async def channel_owner(self, m: Select, interaction: Interaction):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @button(label="Add Owner", style=ButtonStyle.primary, row=2)
    async def add_owner(self, _: Button, interaction: Interaction):
        if self.member in self.channel.overwrites.keys() and self.channel.overwrites_for(self.member).manage_messages == True:
            await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is already a channel owner."), delete_after=5)
        else:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] added to {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await self.channel.set_permissions(self.member, overwrite=owner_overwrites)
        await self.refresh_content(interaction)

    @button(label="Remove Owner", style=ButtonStyle.red, row=2)
    async def remove_owner(self, _: Button, interaction: Interaction):
        if self.member in self.channel.overwrites.keys() and self.channel.overwrites_for(self.member).manage_messages == True:
            log.info(f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] removed from {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]")
            await self.channel.set_permissions(self.member, overwrite=None)
        else:
            await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not a channel owner."), delete_after=5)
        await self.refresh_content(interaction)

    @button(label="Back", style=ButtonStyle.grey, row=3)
    async def back(self, _: Button, interaction: Interaction):
        await self.defer_to(ChannelAdminUI, interaction)

    async def get_content(self) -> Mapping:
        return {"embed": ChannelEmbed(self.channel), "content": ""}
    
class _NewPlayerchannel(ChannelAdmin):
    category: TextChannel = None
    member: Member = None
    name = None
    
    @user_select(placeholder="Channel Owner")
    async def channel_owner(self, m: Select, interaction: Interaction):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @channel_select(placeholder="Category", channel_types=[ChannelType(4)])
    async def channel_category(self, cat: Select, interaction: Interaction):
        self.category = cat.values[0]
        await self.refresh_content(interaction)

    @button(label="Channel Information", style=ButtonStyle.primary, row=3)
    async def channel_info(self, _: Button, interaction: Interaction):
        modal = ChannelInfoModal(self.name)
        response = await self.prompt_modal(interaction, modal)
        self.name = response.name
        await self.refresh_content(interaction)

    @button(label="Create Channel", style=ButtonStyle.green, row=3, disabled=True)
    async def channel_create(self, _: Button, interaction: Interaction):
        self.channel = await self._create_channel(self.name)
        log.info(f"CHANNEL ADMIN: {self.channel.name} [ {self.channel.id} ] created for {self.member} [ {self.member.id} ] by {interaction.user} [ {interaction.user.id} ]")
        await self.channel.send(f"{self.member.mention} welcome to your new channel.\n"
                                f"Go ahead and set everything up.\n"
                                f"1. Make sure you can delete this message.\n"
                                f"2. Use `/room settings` to see your management options")
        await self.defer_to(ChannelAdminUI, interaction)

    @button(label="Back", style=ButtonStyle.grey, row=4)
    async def back(self, _: Button, interaction: Interaction):
        await self.defer_to(ChannelAdminUI, interaction)

    async def _before_send(self):
        if self.name is not None and self.member is not None and self.category is not None:
            self.channel_create.disabled = False
        else:
            self.channel_create.disabled=True

    async def get_content(self) -> Mapping:
        embed = Embed(title="New Character Channel Information")
        embed.description = f"**Channel Name**: {self.name}\n"\
                            f"**Channel Owner**: {self.member.mention if self.member else 'None'}\n"\
                            f"**Channel Category**: {self.category.mention if self.category else 'None'}\n"
        return {"embed": embed, "content": ""}
    
    async def _create_channel(self, name: str) -> TextChannel:
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



class ChannelInfoModal(Modal):
    name = None

    def __init__(self, name = None):
        super().__init__(title="New Player Channel Information")

        self.add_item(InputText(label="Channel Name", placeholder="Channel Name", max_length=100, value=f"{name}"))

    async def callback(self, interaction: Interaction):
        self.name = self.children[0].value

        await interaction.response.defer()
        self.stop()
    