import asyncio
import io
import logging
from typing import Mapping

import chat_exporter
import discord

from Resolute.bot import G0T0Bot
from Resolute.constants import ZWSP3
from Resolute.models.embeds import ErrorEmbed, PaginatedEmbed, PlayerEmbed
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView

log = logging.getLogger(__name__)

OWNER_OVERWRITES = discord.PermissionOverwrite(
    view_channel=True, manage_messages=True, send_messages=True
)

GENERAL_OVERWRITES = discord.PermissionOverwrite(view_channel=True, send_messages=False)

BOT_OVERWRITES = discord.PermissionOverwrite(
    view_channel=True, send_messages=True, manage_messages=True, manage_channels=True
)

READONLY_OVERWRITES = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=False,
    add_reactions=False,
    read_messages=True,
    send_tts_messages=False,
    manage_messages=False,
    manage_roles=False,
    send_messages_in_threads=False,
)


class ChannelAdmin(InteractiveView):
    """
    ChannelAdmin class for handling administrative interactions within a specific channel.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to be copied in the menu.
        bot (G0T0Bot): Instance of the bot.
        channel (discord.TextChannel): The text channel associated with this admin view.
    """

    __menu_copy_attrs__ = ("bot", "channel", "player")
    bot: G0T0Bot
    player: Player
    channel: discord.TextChannel = None

    async def commit(self):
        self.player = await self.bot.get_player(self.player.id, self.player.guild.id)

    async def get_content(self) -> Mapping:
        if not self.channel:
            return {"embed": None, "content": "Pick an option"}
        else:
            embed = PlayerEmbed(
                self.owner,
                title=f"{self.channel.name} Summary",
                description=(
                    f"**Category**: {self.channel.category.mention if self.channel.category else ''}\n"
                ),
            )

            paginated_embed = PaginatedEmbed(embed)

            category_overwrites = (
                self.channel.category.overwrites if self.channel.category else {}
            )
            category_string = "\n".join(get_overwrite_string(category_overwrites))
            paginated_embed.add_field(name="Category Overwrites", value=category_string)

            channel_overwrites = (
                self.channel.overwrites if hasattr(self.channel, "overwrites") else {}
            )
            channel_string = "\n".join(get_overwrite_string(channel_overwrites))
            paginated_embed.add_field(name="Channel Overwrites", value=channel_string)

            return {"embeds": paginated_embed.embeds, "content": ""}


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
    def new(cls, bot, player: Player):
        inst = cls(owner=player.member)
        inst.bot = bot
        inst.player = player
        return inst

    async def _before_send(self):
        self.player_channel.disabled = False if self.channel else True
        if self.get_item("archive_channel"):
            self.archive_channel.disabled = False if self.channel else True

            if self.player.guild.archive_user:
                self.remove_item(self.archive_channel)

        elif not self.player.guild.archive_user:
            self.add_item(self.archive_channel)

    @discord.ui.channel_select(
        placeholder="Channel to manage",
        channel_types=[
            discord.ChannelType(0),
            discord.ChannelType(11),
            discord.ChannelType(15),
        ],
    )
    async def channel_select(
        self, c: discord.ui.Select, interaction: discord.Interaction
    ):
        self.channel = c.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="New Player Channel", style=discord.ButtonStyle.primary, row=2
    )
    async def new_player_channel(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_NewPlayerchannel, interaction)

    @discord.ui.button(
        label="Edit Player Channel", style=discord.ButtonStyle.primary, row=2
    )
    async def player_channel(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        managed = False
        for target in self.channel.overwrites:
            if isinstance(target, discord.Member):
                if self.channel.overwrites[target].manage_messages == True:
                    managed = True

        if not managed:
            raise G0T0Error("This doesn't look to be a player managed channel")
        else:
            await self.defer_to(_EditPlayerChannel, interaction)

    @discord.ui.button(
        label="Archive Channel",
        style=discord.ButtonStyle.primary,
        row=3,
        custom_id="archive_channel",
    )
    async def archive_channel(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.player.guild.archive_user:
            return await interaction.channel.send(
                embed=ErrorEmbed(
                    "Already archiving a channel. Please wait for it to finish first"
                ),
                delete_after=5,
            )
        else:
            self.player.guild.archive_user = self.player.member
            await self.player.guild.upsert()

            asyncio.create_task(_archive_channel(self.bot, self.channel, self.player))
            await interaction.channel.send(
                "Archiving done in background process. You can only archive one channel at a time.",
                delete_after=5,
            )
            await self.refresh_content(interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=4)
    async def exit(self, *_):
        await self.on_timeout()


class _EditPlayerChannel(ChannelAdmin):
    member: discord.Member = None

    @discord.ui.user_select(placeholder="Channel Owner")
    async def channel_owner(
        self, m: discord.ui.Select, interaction: discord.Interaction
    ):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Owner", style=discord.ButtonStyle.primary, row=2)
    async def add_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if (
            self.member in self.channel.overwrites.keys()
            and self.channel.overwrites_for(self.member).manage_messages == True
        ):
            await interaction.channel.send(
                embed=ErrorEmbed(f"{self.member.mention} is already a channel owner."),
                delete_after=5,
            )
        else:
            log.info(
                f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] added to {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]"
            )
            await self.channel.set_permissions(self.member, overwrite=OWNER_OVERWRITES)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Owner", style=discord.ButtonStyle.red, row=2)
    async def remove_owner(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if (
            self.member in self.channel.overwrites.keys()
            and self.channel.overwrites_for(self.member).manage_messages == True
        ):
            log.info(
                f"CHANNEL ADMIN: {self.member} [ {self.member.id} ] removed from {self.channel.name} [ {self.channel.id} ] by {interaction.user} [ {interaction.user.id} ]"
            )
            await self.channel.set_permissions(self.member, overwrite=None)
        else:
            await interaction.channel.send(
                embed=ErrorEmbed(f"{self.member.mention} is not a channel owner."),
                delete_after=5,
            )
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ChannelAdminUI, interaction)


class _NewPlayerchannel(ChannelAdmin):
    category: discord.TextChannel = None
    member: discord.Member = None
    name = None

    @discord.ui.user_select(placeholder="Channel Owner")
    async def channel_owner(
        self, m: discord.ui.Select, interaction: discord.Interaction
    ):
        self.member = m.values[0]
        await self.refresh_content(interaction)

    @discord.ui.channel_select(
        placeholder="Category", channel_types=[discord.ChannelType(4)]
    )
    async def channel_category(
        self, cat: discord.ui.Select, interaction: discord.Interaction
    ):
        self.category = cat.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Channel Information", style=discord.ButtonStyle.primary, row=3
    )
    async def channel_info(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = ChannelInfoModal(self.name)
        response = await self.prompt_modal(interaction, modal)
        self.name = response.name
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Create Channel", style=discord.ButtonStyle.green, row=3, disabled=True
    )
    async def channel_create(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.channel = await self._create_channel(self.name)
        log.info(
            f"CHANNEL ADMIN: {self.channel.name} [ {self.channel.id} ] created for {self.member} [ {self.member.id} ] by {interaction.user} [ {interaction.user.id} ]"
        )
        await self.channel.send(
            f"{self.member.mention} welcome to your new channel.\n"
            f"Go ahead and set everything up.\n"
            f"1. Make sure you can delete this message.\n"
            f"2. Use `/room settings` to see your management options"
        )
        await self.defer_to(ChannelAdminUI, interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ChannelAdminUI, interaction)

    async def _before_send(self):
        if (
            self.name is not None
            and self.member is not None
            and self.category is not None
        ):
            self.channel_create.disabled = False
        else:
            self.channel_create.disabled = True

    async def get_content(self) -> Mapping:
        embed = discord.Embed(title="New Character Channel Information")
        embed.description = (
            f"**Channel Name**: {self.name}\n"
            f"**Channel Owner**: {self.member.mention if self.member else 'None'}\n"
            f"**Channel Category**: {self.category.mention if self.category else 'None'}\n"
        )
        return {"embed": embed, "content": ""}

    async def _create_channel(self, name: str) -> discord.TextChannel:
        channel_overwrites = self.category.overwrites
        guild = await self.bot.get_player_guild(self.category.guild.id)

        channel_overwrites[self.member] = OWNER_OVERWRITES

        if guild.bot_role:
            channel_overwrites[guild.bot_role] = BOT_OVERWRITES

        if guild.member_role:
            channel_overwrites[guild.member_role] = GENERAL_OVERWRITES

        if guild.staff_role:
            channel_overwrites[guild.staff_role] = GENERAL_OVERWRITES

        channel = await guild.guild.create_text_channel(
            name=name,
            category=self.category,
            overwrites=channel_overwrites,
            reason=f"Channel admin command",
        )

        return channel


class ChannelInfoModal(discord.ui.Modal):
    name = None

    def __init__(self, name=None):
        super().__init__(title="New Player Channel Information")

        self.add_item(
            discord.ui.InputText(
                label="Channel Name",
                placeholder="Channel Name",
                max_length=100,
                value=f"{name}",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.name = self.children[0].value

        await interaction.response.defer()
        self.stop()


# --------------------------- #
# Private Methods
# --------------------------- #


async def _archive_channel(
    bot: G0T0Bot,
    channel: discord.TextChannel | discord.Thread | discord.ForumChannel,
    player: Player,
):
    transcript = await chat_exporter.export(channel, guild=player.guild.guild, bot=bot)

    if transcript is None:
        return

    transcript_file = discord.File(
        io.BytesIO(transcript.encode()),
        filename=f"{player.guild.guild.name} - {channel.name} [{channel.id}].html",
    )

    await player.member.send(file=transcript_file)
    player.guild.archive_user = None
    await player.guild.upsert()


def get_overwrite_string(
    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite],
):
    out = []
    for target in overwrites:
        value = f"**{target.mention}**:\n"
        ovr = [x for x in overwrites[target] if x[1] is not None]

        if ovr:
            value += "\n".join([f"{ZWSP3}{o[0]} - {o[1]}" for o in ovr])
        else:
            value += "None\n"

        out.append(value)
    return out
