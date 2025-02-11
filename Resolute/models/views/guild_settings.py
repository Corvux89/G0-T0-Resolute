import re

import discord
import discord.ui

from Resolute.bot import G0T0Bot
from Resolute.constants import DAYS_OF_WEEK
from Resolute.helpers.general_helpers import get_positivity
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.guilds import GuildEmbed, ResetEmbed
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.ref_objects import RefWeeklyStipend
from Resolute.models.views.base import InteractiveView
from Resolute.models.views.npc import NPCSettingsUI


class GuildSettings(InteractiveView):
    """
    GuildSettings is a class that represents the settings for a guild in the application.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple containing the attributes to be copied in the menu.
        bot (G0T0Bot): An instance of the bot.
        owner (discord.Member, optional): The owner of the guild. Defaults to None.
        guild (PlayerGuild, optional): The guild associated with the settings. Defaults to None.
    Methods:
        commit: Asynchronously commits the current settings to the guild and dispatches a refresh event.
    """

    __menu_copy_attrs__ = ("guild", "bot")
    bot: G0T0Bot
    owner: discord.Member = None
    guild: PlayerGuild = None

    async def commit(self):
        self.guild = await self.guild.upsert()
        self.bot.dispatch("refresh_guild_cache", self.guild)
    
class GuildSettingsUI(GuildSettings):
    """
    A user interface class for managing guild settings in a Discord bot.
    Methods
    -------
    new(cls, bot, owner, guild)
        Class method to create a new instance of GuildSettingsUI.
    async get_content()
        Asynchronously retrieves the content to be displayed in the UI.
    async guild_limits(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Guild Limits" button click event, prompting a modal for guild limits settings.
    async guild_update_reset(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Update Reset" button click event, deferring to the _GuildResetView.
    async guild_update_stipend(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Update Stipends" button click event, deferring to the _GuildStipendView.
    async more_settings(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "More Settings" button click event, deferring to the _GuildSettings2 view.
    async exit(self, *_)
        Handles the "Exit" button click event, triggering the timeout behavior.
    """

    @classmethod
    def new(cls, bot, owner, guild):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.guild = guild
        return inst
    
    async def get_content(self):
        embed = GuildEmbed(self.guild)

        return {"embed": embed, "content": None}
    
    @discord.ui.button(label="Guild Limits", style=discord.ButtonStyle.primary, row=1)
    async def guild_limits(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = GuildLimitsModal(self.guild)
        response = await self.prompt_modal(interaction, modal)
        self.guild = response.guild
        await self.refresh_content(interaction)

    @discord.ui.button(label="Update Reset", style=discord.ButtonStyle.primary, row=1)
    async def guild_update_reset(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_GuildResetView, interaction)

    @discord.ui.button(label="Update Stipends", style=discord.ButtonStyle.primary, row=1)
    async def guild_update_stipend(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_GuildStipendView, interaction)

    @discord.ui.button(label="More Settings", style=discord.ButtonStyle.primary, row=2)
    async def more_settings(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_GuildSettings2, interaction)
    
    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=2)
    async def exit(self, *_):
        await self.on_timeout()

class _GuildSettings2(GuildSettings):
    @discord.ui.button(label="Server Date", style=discord.ButtonStyle.primary, row=1)
    async def update_server_date(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ServerDateModal(self.guild)

        response = await self.prompt_modal(interaction, modal)

        self.guild.server_date = response.guild.server_date
        self.guild.epoch_notation = response.guild.epoch_notation

        await self.refresh_content(interaction)

    @discord.ui.button(label="New Player Messages", style=discord.ButtonStyle.primary, row=1)
    async def new_player_messages(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NewPlayerMessageModal(self.guild)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.primary, row=1)
    async def npcs(self, _: discord.ui.Button, interaction: discord.Interaction):
        view = NPCSettingsUI.new(self.bot, self.owner, self.guild, _GuildSettings2)
        await view.send_to(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(GuildSettingsUI, interaction)

    async def get_content(self):
        embed = GuildEmbed(self.guild)

        return {"embed": embed, "content": None}

class _GuildResetView(GuildSettings):
    @discord.ui.button(label="Update Announcements", style=discord.ButtonStyle.primary, row=1)
    async def reset_announcements(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = GuildAnnouncementModal(self.guild)
        response = await self.prompt_modal(interaction, modal)

        self.guild.reset_message = response.guild.reset_message
        self.guild.weekly_announcement = response.guild.weekly_announcement

        await self.refresh_content(interaction)

    @discord.ui.button(label="Preview Reset", style=discord.ButtonStyle.primary, row=1)
    async def preview_reset(self, _: discord.ui.Button, interaction: discord.Interaction):
        await interaction.channel.send(embed=ResetEmbed(self.guild, 1.23), content=f"{f'{self.guild.entry_role.name} {self.guild.member_role.name}' if self.guild.ping_announcement else ''}", delete_after=5)
        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Reset Day", row=2)
    async def reset_day(self, day: discord.ui.Select, interaction: discord.Interaction):
        if day.values[0] == "None":
            self.guild._reset_day = None
            self.guild._reset_hour = None
        else:
            self.guild._reset_day = int(day.values[0])
        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Reset Time (GMT)", row=3)
    async def reset_time(self, time: discord.ui.Select, interaction: discord.Interaction):
        self.guild._reset_hour = int(time.values[0])
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(GuildSettingsUI, interaction)

    async def _before_send(self):
        time_options = [discord.SelectOption(label=f"{str(i).zfill(2)}:00 (GMT)", value=f"{str(i)}", default=True if self.guild._reset_hour == i else False) for i in range(24)]

        day_options = [discord.SelectOption(label=f"{day[0]}", value=f"{day[1]}", default=True if str(self.guild._reset_day) == day[1] else False) for day in DAYS_OF_WEEK]

        self.reset_time.options = time_options
        self.reset_day.options = day_options
        pass

    async def get_content(self):
        embed = GuildEmbed(self.guild)

        return {"embed": embed, "content": None}
    
class _GuildStipendView(GuildSettings):
    role: discord.Role

    @discord.ui.role_select(placeholder="Stipend discord.Role", row=1)
    async def guild_role_select(self, role : discord.ui.Select, interaction: discord.Interaction):
        self.role = role.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add/Modify Stipend", style=discord.ButtonStyle.primary, row=2)
    async def guild_edit_stipend(self, _: discord.ui.Button, interaction: discord.Interaction):
        stipend: RefWeeklyStipend = next((s for s in self.guild.stipends if s.role_id == self.role.id),
                                         RefWeeklyStipend(self.bot.db, role_id=self.role.id, guild_id=self.guild.id))
        
        modal = GuildStipendModal(stipend, self.role)

        response = await self.prompt_modal(interaction, modal)

        stipend = response.stipend
        await stipend.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Stipend", style=discord.ButtonStyle.red, row=2)
    async def guild_remove_stipend(self, _: discord.ui.Button, interaction: discord.Interaction):
        stipend: RefWeeklyStipend = next((s for s in self.guild.stipends if s.role_id == self.role.id),None)

        if stipend is None:
            await interaction.channel.send(f"No stipend for `{self.role.name}`",delete_after=5)
        
        else:
            await stipend.delete() 

        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(GuildSettingsUI, interaction)

    async def get_content(self):
        embed = GuildEmbed(self.guild)

        return {"embed": embed, "content": None}


class GuildLimitsModal(discord.ui.Modal):
    guild: PlayerGuild

    def __init__(self, guild: PlayerGuild):
        super().__init__(title="Guild Limits")    
        self.guild = guild

        self.add_item(discord.ui.InputText(label="Max Level", required=True, placeholder="Max Level", max_length=2, value=self.guild.max_level))
        self.add_item(discord.ui.InputText(label="Max # Characters", required=True, placeholder="Max Characters", max_length=2, value=self.guild.max_characters))
        self.add_item(discord.ui.InputText(label="Handicap Amount", required=True, placeholder="Handicap Amount", max_length=3, value=self.guild.handicap_cc))
        self.add_item(discord.ui.InputText(label="Diversion Limit (CC)", required=True, placeholder="Diversion Limit", max_length=3, value=self.guild.div_limit))
        self.add_item(discord.ui.InputText(label="Log Reward Points Threshold", required=False, placeholder="Log Reward Points Threshold", max_length=3, value=self.guild.reward_threshold))

    async def callback(self, interaction: discord.Interaction):
        err_str = []
        values = [
            (self.children[0].value, "max_level", "Max level must be a number!"),
            (self.children[1].value, "max_characters", "Max characters must be a number!"),
            (self.children[2].value, "handicap_cc", "Handicap amount must be a number!"),
            (self.children[3].value, "div_limit", "Diversion limit must be a number!")
        ]

        for value, node, err_msg in values:
            try:
                setattr(self.guild, node, int(value))
            except:
                err_str.append(err_msg)

        if self.children[4].value:
            try:
                self.guild.reward_threshold = int(self.children[4].value)
            except:
                err_str.append("Reward threshold must be a number!")
        else:
            self.guild.reward_threshold = None
        

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()

        self.stop()

class GuildStipendModal(discord.ui.Modal):
    stipend: RefWeeklyStipend

    def __init__(self, stipend: RefWeeklyStipend, role: discord.Role):
        super().__init__(title=f"Stipend for {role.name}")
        self.stipend = stipend

        self.add_item(discord.ui.InputText(label="Amount", required=True, placeholder="Amount", max_length=3, value=self.stipend.amount))
        self.add_item(discord.ui.InputText(label="Reason", required=False, placeholder="Reason", value=self.stipend.reason))
        self.add_item(discord.ui.InputText(label="Leadership Stipend", required=False, max_length=5, placeholder="Leadership Stipend", value=self.stipend.leadership if self.stipend.leadership else False))
    
    async def callback(self, interaction: discord.Interaction):
        self.stipend.amount = self.children[0].value
        self.stipend.reason = self.children[1].value

        leadership = True if self.children[2] and get_positivity(self.children[2].value.lower()) else False

        self.stipend.leadership = leadership

        await interaction.response.defer()
        self.stop()

class GuildAnnouncementModal(discord.ui.Modal):
    guild: PlayerGuild

    def split_string(self, input_string) -> []:
        parts = re.findall(r'"(.*?)"', input_string, re.DOTALL)
        if not parts or parts is None:
            return []

        return parts

    def __init__(self, guild: PlayerGuild):
        super().__init__(title=f"Guild Reset Announcements")
        self.guild = guild

        announcement_string = ",".join(['"' + x + '"' for x in self.guild.weekly_announcement])

        self.add_item(discord.ui.InputText(label="Reset Message", style=discord.InputTextStyle.long, required=False, placeholder="Reset Message", max_length=3500, value=self.guild.reset_message))
        self.add_item(discord.ui.InputText(label="Weekly Announcements", style=discord.InputTextStyle.long, required=False, placeholder="Weekly Announcements", value=announcement_string))
        self.add_item(discord.ui.InputText(label="Ping on announcement?", required=False, placeholder="Ping on announcement?", value=f"{guild.ping_announcement}"))

    async def callback(self, interaction: discord.Interaction):    
        self.guild.reset_message = self.children[0].value or None
        self.guild.weekly_announcement = self.split_string(self.children[1].value)
        self.guild.ping_announcement = True if self.children[2] and get_positivity(self.children[2].value.lower()) else False

        await interaction.response.defer()
        self.stop()

class ServerDateModal(discord.ui.Modal):
    guild: PlayerGuild

    def __init__(self, guild: PlayerGuild):
        super().__init__(title=f"Server Date")
        self.guild = guild

        self.add_item(discord.ui.InputText(label="Year", required=False, placeholder="Year", max_length=5, value=self.guild.server_year))
        self.add_item(discord.ui.InputText(label="Month", required=False, placeholder="Month", max_length=50, value=self.guild.server_month.display_name if self.guild.server_month is not None else ""))
        self.add_item(discord.ui.InputText(label="Day", required=False, placeholder="Day", max_length=3, value=self.guild.server_day))
        self.add_item(discord.ui.InputText(label="Notation", required=False, placeholder="Notation", max_length=20, value=guild.epoch_notation))

    async def callback(self, interaction: discord.Interaction):
        self.guild.epoch_notation = self.children[3].value or None

        month = next((month for month in self.guild.calendar if month.display_name.lower() == self.children[1].value.lower()), None)

        if self.children[0] and month and self.children[2]:
            try:
                self.guild.server_date = self.guild.get_internal_date(int(self.children[2].value), self.guild.calendar.index(month)+1, int(self.children[0].value))
            except:
                await interaction.channel.send(embed=ErrorEmbed(f"Error setting server date"), delete_after=5)
    
        await interaction.response.defer()
        self.stop()

class NewPlayerMessageModal(discord.ui.Modal):
    guild: PlayerGuild

    def __init__(self, guild: PlayerGuild):
        super().__init__(title=f"New Player Messages")
        self.guild = guild

        self.add_item(discord.ui.InputText(label="New discord.Member Greeting", style=discord.InputTextStyle.long, max_length=1000, required=False, value=self.guild.greeting))
        self.add_item(discord.ui.InputText(label="New Character Message", style=discord.InputTextStyle.multiline, max_length=500, required=False, value=self.guild.first_character_message))

    async def callback(self, interaction: discord.Interaction):
        self.guild.greeting = self.children[0].value
        self.guild.first_character_message = self.children[1].value

        await interaction.response.defer()
        self.stop()
