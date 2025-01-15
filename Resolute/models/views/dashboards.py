import logging
from typing import Mapping

import discord
from discord import ChannelType, SelectOption

from Resolute.bot import G0T0Bot
from Resolute.helpers.dashboards import get_dashboard_from_post, get_guild_dashboards, update_dashboard, upsert_dashboard
from Resolute.models.categories.categories import DashboardType
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.dashboards import DashboardEditEmbed
from Resolute.models.objects.dashboards import RefDashboard
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)


class DashboardSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "dashboard")
    bot: G0T0Bot
    dashboard: RefDashboard = None

class DashboardSettingsUI(DashboardSettings):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member):
        inst = cls(owner=owner)
        inst.bot = bot
        return inst
    
    @discord.ui.select(placeholder="Select a dashboard", options=[SelectOption(label="Dummy Dashboard")], custom_id="d_select")
    async def dashboard_select(self, dashboard: discord.ui.Select, interaction: discord.Interaction):
        self.dashboard = await get_dashboard_from_post(self.bot, dashboard.values[0])
        await self.refresh_content(interaction)

    @discord.ui.button(label="New Dashboard", style=discord.ButtonStyle.primary, row=2)
    async def new_dashboard(self, _: discord.ui.Select, interaction: discord.Interaction):
        await self.defer_to(_NewDashboardUI, interaction)

    @discord.ui.button(label="Manage Dashboard", style=discord.ButtonStyle.primary, row=2)
    async def manage_dashboard(self, _: discord.ui.Select, interaction: discord.Interaction):
        await self.defer_to(_ManageDashboardUI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        dashboards = await get_guild_dashboards(self.bot, self.owner.guild.id)
        if len(dashboards)>0:
            d_list = []
            if not self.get_item("d_select"):
                self.add_item(self.dashboard_select)
            
            if not self.dashboard:
                self.dashboard = dashboards[0]
            
            for dashboard in dashboards:
                d_list.append(SelectOption(label=f"{dashboard.dashboard_type.value}: {self.bot.get_channel(dashboard.channel_id).name}",
                                           value=f"{dashboard.post_id}", default=True if self.dashboard and self.dashboard.post_id == dashboard.post_id else False))
                
            self.dashboard_select.options = d_list
        else:
            self.remove_item(self.dashboard_select)
            self.remove_item(self.manage_dashboard)

    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Select an Option:\n"}
    

class _NewDashboardUI(DashboardSettings):
    new_dashboard: RefDashboard = RefDashboard()

    @discord.ui.select(placeholder="Dashboard Type")
    async def dashboard_type(self, d_type: discord.ui.Select, interaction: discord.Interaction):
        if type := self.bot.compendium.get_object(DashboardType, int(d_type.values[0])):
            self.new_dashboard.dashboard_type = type

            if type.value.upper() == "RP":
                if not self.get_item("cat_select"):
                    self.add_item(self.dashboard_category)
            else:
                self.remove_item(self.dashboard_category)
        await self.refresh_content(interaction)

    @discord.ui.channel_select(placeholder="Category to represent", channel_types=[ChannelType(4)], custom_id="cat_select")
    async def dashboard_category(self, category: discord.ui.Select, interaction: discord.Interaction):
        self.new_dashboard.category_channel_id = category.values[0].id
        await self.refresh_content(interaction)

    @discord.ui.channel_select(placeholder="Channel to display in", channel_types=[ChannelType(0)])
    async def dashboard_channel(self, channel: discord.ui.Select, interaction: discord.Interaction):
        self.new_dashboard.channel_id = channel.values[0].id

        await self.refresh_content(interaction)

    @discord.ui.button(label="Create Dashboard", style=discord.ButtonStyle.primary, row=4)
    async def dashboard_create(self, _: discord.ui.Button, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.new_dashboard.channel_id)
        d_message = await channel.send(f"Fetching dashboard data. This may take a moment.")
        await d_message.pin(reason=f"{self.new_dashboard.dashboard_type.value} dashboard created by {self.owner.name}")
        self.new_dashboard.post_id = d_message.id

        await upsert_dashboard(self.bot, self.new_dashboard)

        await update_dashboard(self.bot, self.new_dashboard)

        await self.defer_to(DashboardSettingsUI, interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(DashboardSettingsUI, interaction)

    async def _before_send(self):
        type_list = []

        for type in self.bot.compendium.dashboard_type[0].values():
            type_list.append(SelectOption(label=type.value, value=f"{type.id}", default=True if self.new_dashboard and self.new_dashboard.dashboard_type and self.new_dashboard.dashboard_type.id == type.id else False))
        
        self.dashboard_type.options = type_list

        self.dashboard_create.disabled = True

        if self.new_dashboard and self.new_dashboard.dashboard_type:
            if self.new_dashboard.dashboard_type.value.upper() == "RP":
                if self.new_dashboard.category_channel_id and self.new_dashboard.channel_id:
                    self.dashboard_create.disabled = False
            else:
                if self.new_dashboard.channel_id:
                    self.dashboard_create.disabled = False

    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Setup a new dashboard: \n"}
    
class _ManageDashboardUI(DashboardSettings):
    channel: discord.TextChannel = None

    @discord.ui.channel_select(placeholder="Channel", channel_types=[ChannelType(0)])
    async def channel_select(self, chan: discord.ui.Select, interaction: discord.Interaction):
        channel: discord.TextChannel = chan.values[0]

        if hasattr(channel, "category_id") and channel.category_id != self.dashboard.category_channel_id:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel not in this dashbaords category"), delete_after=5)
        else:
            self.channel = channel
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Exclusion", style=discord.ButtonStyle.primary, row=2)
    async def add_exclusion(self, _: discord.ui.Button, interaction: discord.Interaction):
        if not self.channel:
            await interaction.channel.send(embed=ErrorEmbed(f"Select a channel to exclude"), delete_after=5)
        elif self.channel.id in self.dashboard.excluded_channel_ids:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel already excluded"), delete_after=5)
        else:
            self.dashboard.excluded_channel_ids.append(self.channel.id)
            await upsert_dashboard(self.bot, self.dashboard)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Exclusion", style=discord.ButtonStyle.primary, row=2)
    async def remove_exclusion(self, _: discord.ui.Button, interaction: discord.Interaction):
        if not self.channel:
            await interaction.channel.send(embed=ErrorEmbed(f"Select a channel to exclude"), delete_after=5)
        elif self.channel.id not in self.dashboard.excluded_channel_ids:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel not excluded"), delete_after=5)
        else:
            self.dashboard.excluded_channel_ids.remove(self.channel.id)
            await upsert_dashboard(self.bot, self.dashboard)
        await self.refresh_content(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(DashboardSettingsUI, interaction)

    async def _before_send(self):
        if self.dashboard.dashboard_type.value.upper() != "RP":
            self.remove_item(self.channel_select)
            self.remove_item(self.remove_exclusion)
            self.remove_item(self.add_exclusion)

    async def get_content(self) -> Mapping:
        return {"embed": DashboardEditEmbed(self.bot, self.dashboard), "content": ""}