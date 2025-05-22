from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.models.embeds import ErrorEmbed, PlayerEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.npc import NonPlayableCharacter
from Resolute.models.views.base import InteractiveView


class NPCSettings(InteractiveView):
    """
    NPCSettings is a view that handles the settings and interactions for NPCs within an adventure or guild context.
    Attributes:
        bot (G0T0Bot): The bot instance.
        guild (PlayerGuild): The player's guild instance.
        adventure (Adventure): The current adventure instance.
        back_menu (type[InteractiveView]): The type of the previous interactive view.
        npc (NPC, optional): The NPC instance. Defaults to None.
        role (Role, optional): The role instance. Defaults to None.
    Methods:
        get_content() -> Mapping:
            Asynchronously generates the content to be displayed in the view, including an embed with NPC information.
        send_to(interaction, *args, **kwargs):
            Asynchronously sends or edits the message with the current view and content.
        commit():
            Asynchronously updates the adventure or guild information from the bot.
    """

    __menu_copy_attrs__ = ("bot", "guild", "adventure", "npc", "back_menu", "role")
    bot: G0T0Bot
    guild: PlayerGuild
    adventure: Adventure
    back_menu: type[InteractiveView]

    npc: NonPlayableCharacter = None
    role: discord.Role = None

    async def get_content(self) -> Mapping:
        embed = PlayerEmbed(self.owner, title="Manage NPCs")

        npc_list = (
            self.adventure.npcs
            if self.adventure and self.adventure.npcs
            else (
                []
                if self.adventure
                else self.guild.npcs if self.guild and self.guild.npcs else []
            )
        )

        npc = self.npc if self.npc else npc_list[0] if npc_list else None

        embed.set_thumbnail(url=npc.avatar_url if npc and npc.avatar_url else None)

        embed.description = (
            f"Avatar for `{npc.key}`: {npc.name}" if npc and npc.avatar_url else ""
        )

        npc_list_str = "\n".join(
            [f"`{n.key}`: {n.name}{'*' if n.avatar_url else ''}" for n in npc_list]
        )

        if npc and len(npc.roles) > 0:
            roles = []
            for rid in npc.roles:
                if role := self.guild.guild.get_role(rid):
                    roles.append(role.mention)
            embed.add_field(name="Available to roles", value="\n".join(roles))

        embed.add_field(
            name="Available NPCs (* = Has avatar)", value=npc_list_str, inline=False
        )

        return {"content": "", "embed": embed}

    async def send_to(self, interaction, *args, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send()

        if interaction.response.is_done():
            await interaction.edit_original_response(
                view=self, **content_kwargs, **kwargs
            )
        else:
            await interaction.response.edit_message(
                view=self, **content_kwargs, **kwargs
            )

    async def commit(self):
        if self.adventure:
            self.adventure = await Adventure.get_from_category_id(
                self.bot, self.adventure.category_channel_id
            )
        elif self.guild:
            self.guild = await self.guild.fetch()


class NPCSettingsUI(NPCSettings):
    """
    NPCSettingsUI is a user interface class for managing NPC settings in a Discord bot.
    Methods:
        new(cls, bot, owner, guild, back_menu, **kwargs):
            Creates a new instance of NPCSettingsUI.
        async _before_send(self):
            Prepares the UI before sending it to the user.
        async npc_select(self, n: discord.ui.Select, interaction: discord.Interaction):
            Handles the selection of an NPC from the dropdown.
        async role_select(self, r: discord.ui.Select, interaction: discord.Interaction):
            Handles the selection of a role from the dropdown.
        async new_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
            Opens a modal to create a new NPC.
        async edit_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
            Opens a modal to edit the selected NPC.
        async delete_npc_button(self, _: discord.ui.Button, interaction: discord.Interaction):
            Deletes the selected NPC.
        async add_npc_role(self, _: discord.ui.Button, interaction: discord.Interaction):
            Adds a role to the selected NPC.
        async remove_npc_role(self, _: discord.ui.Button, interaction: discord.Interaction):
            Removes a role from the selected NPC.
        async back(self, _: discord.ui.Button, interaction: discord.Interaction):
            Navigates back to the previous menu.
    """

    @classmethod
    def new(cls, bot, owner, guild, back_menu, **kwargs):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.back_menu = back_menu
        inst.guild = guild
        inst.adventure = kwargs.get("adventure")
        return inst

    async def _before_send(self):
        npcs = []
        if self.adventure:
            self.remove_item(self.add_npc_role)
            self.remove_item(self.remove_npc_role)
            self.remove_item(self.role_select)

            if not self.guild.is_admin(self.owner):
                self.remove_item(self.new_npc)
                self.remove_item(self.delete_npc_button)
                self.remove_item(self.edit_npc)

            if self.adventure.npcs and len(self.adventure.npcs) > 0:
                npcs = self.adventure.npcs
        else:
            if self.guild.npcs and len(self.guild.npcs) > 0:
                npcs = self.guild.npcs

        if len(npcs) == 0:
            self.remove_item(self.npc_select)
        else:
            if not self.get_item("npc_select"):
                self.add_item(self.npc_select)

            npc_list = [
                discord.SelectOption(
                    label=f"{n.name}",
                    value=f"{n.key}",
                    default=True if self.npc and self.npc.key == n.key else False,
                )
                for n in npcs
            ]

            self.npc_select.options = npc_list

        self.edit_npc.disabled = False if self.npc else True
        self.delete_npc_button.disabled = False if self.npc else True

        self.add_npc_role.disabled = False if self.role else True
        self.remove_npc_role.disabled = False if self.role else True

    @discord.ui.select(placeholder="Select an NPC", row=1, custom_id="npc_select")
    async def npc_select(self, n: discord.ui.Select, interaction: discord.Interaction):
        if self.adventure:
            self.npc = next(
                (i for i in self.adventure.npcs if i.key == n.values[0]), None
            )
        else:
            self.npc = next((i for i in self.guild.npcs if i.key == n.values[0]), None)
        await self.refresh_content(interaction)

    @discord.ui.role_select(placeholder="Select a role", custom_id="role_select", row=2)
    async def role_select(self, r: discord.ui.Select, interaction: discord.Interaction):
        self.role = r.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="New NPC", style=discord.ButtonStyle.primary, row=3)
    async def new_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NPCModal(self.bot, guild=self.guild, adventure=self.adventure)

        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit NPC", style=discord.ButtonStyle.primary, row=3)
    async def edit_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NPCModal(
            self.bot, guild=self.guild, adventure=self.adventure, npc=self.npc
        )
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Delete NPC", style=discord.ButtonStyle.danger, row=3)
    async def delete_npc_button(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.npc.delete()
        self.npc = None
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.primary, row=4)
    async def add_npc_role(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.role.id not in self.npc.roles:
            self.npc.roles.append(self.role.id)
            await self.npc.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.primary, row=4)
    async def remove_npc_role(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.role.id in self.npc.roles:
            self.npc.roles.remove(self.role.id)
            await self.npc.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(self.back_menu, interaction)


class NPCModal(discord.ui.Modal):
    bot: G0T0Bot
    guild: PlayerGuild
    adventure: Adventure
    npc: NonPlayableCharacter

    def __init__(self, bot: G0T0Bot, **kwargs):
        super().__init__(title="New NPC")
        self.bot = bot
        self.npc = kwargs.get("npc")
        self.guild = kwargs.get("guild")
        self.adventure = kwargs.get("adventure")
        if not self.npc:
            self.add_item(
                discord.ui.InputText(
                    label="Key",
                    placeholder="Key",
                    max_length=20,
                    value=self.npc.key if self.npc else None,
                )
            )
        self.add_item(
            discord.ui.InputText(
                label="Name",
                placeholder="Name",
                max_length=100,
                value=self.npc.name if self.npc else None,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Avatar URL",
                placeholder="Avatar URL",
                required=False,
                max_length=100,
                value=self.npc.avatar_url if self.npc else None,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        key = self.children[0].value.strip() if not self.npc else self.npc.key
        name = self.children[1].value if not self.npc else self.children[0].value
        url = self.children[2].value if not self.npc else self.children[1].value

        if (
            not self.npc
            and (npc := next((n for n in self.guild.npcs if n.key == key), None))
            and self.adventure
            and (npc := next((n for n in self.adventure.npcs if n.key == key), None))
        ):
            await interaction.response.send_message(
                embed=ErrorEmbed(f"An NPC already exists with that key"), ephemeral=True
            )
            self.stop()

        elif self.npc:
            self.npc.key = key
            self.npc.name = name
            self.npc.avatar_url = url
        else:
            self.npc = NonPlayableCharacter(
                self.bot.db,
                self.guild.id,
                key,
                name,
                avatar_url=url,
                adventure_id=self.adventure.id if self.adventure else None,
            )

        await self.npc.upsert()
        await self.npc.register_command(self.bot)
        self.bot.dispatch("refresh_guild_cache", self.guild)

        await interaction.response.defer()
        self.stop()
