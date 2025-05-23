from datetime import datetime, timezone
from math import ceil
from typing import Mapping, Type

import discord

from Resolute.bot import G0T0Bot
from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.helpers import confirm
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds import ErrorEmbed, PlayerEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView
from Resolute.models.views.npc import NPCSettingsUI


class AdventureView(InteractiveView):
    """
    AdventureView is a subclass of InteractiveView that manages the interaction
    and display of an adventure within the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        owner (Member, optional): The owner of the adventure. Defaults to None.
        adventure (Adventure): The adventure instance.
        dm_select (bool, optional): Flag indicating if DM selection is enabled. Defaults to False.
        member (Member, optional): The member associated with the view. Defaults to None.
        character (PlayerCharacter, optional): The player character associated with the view. Defaults to None.
    Methods:
        commit(): Commits the current state of the adventure to the database.
        send_to(destination, *args, **kwargs): Sends the view to the specified destination.
        defer_to(view_type, interaction, stop=True): Defers the interaction to another view type.
        get_content(interaction): Retrieves the content to be displayed in the view.
        refresh_content(interaction, **kwargs): Refreshes the content of the view.
    """

    __menu_copy_attrs__ = ("bot", "adventure", "dm_select", "guild")
    bot: G0T0Bot
    owner: discord.Member = None
    adventure: Adventure
    dm_select: bool = False
    member: discord.Member = None
    character: PlayerCharacter = None
    guild: PlayerGuild = None

    async def commit(self):
        await self.adventure.upsert()

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content(destination)
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(
        self,
        view_type: Type["AdventureView"],
        interaction: discord.Interaction,
        stop=True,
    ):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self, interaction: discord.Interaction) -> Mapping:
        embed = PlayerEmbed(interaction.user, title=f"{self.adventure.name}")

        embed.set_thumbnail(url=THUMBNAIL)

        embed.description = (
            f"**Adventure Role**: {self.adventure.role.mention}\n"
            f"**CC Earned to date**: {self.adventure.cc}"
        )

        if len(self.adventure.factions) > 0:
            embed.description += f"\n**Factions**:\n" + "\n".join(
                [f"{ZWSP3}{f.value}" for f in self.adventure.factions]
            )

        embed.add_field(
            name=f"DM{'s' if len(self.adventure.dms) > 1 else ''}",
            value="\n".join(
                [
                    f"{ZWSP3}- {interaction.guild.get_member(dm).mention}"
                    for dm in self.adventure.dms
                    if interaction.guild.get_member(dm)
                ]
            ),
            inline=False,
        )

        if self.adventure.player_characters:
            embed.add_field(
                name="Players",
                value="\n".join(
                    [
                        f"{ZWSP3}- {character.name} ({interaction.guild.get_member(character.player_id).mention})"
                        for character in self.adventure.player_characters
                        if interaction.guild.get_member(character.player_id)
                    ]
                ),
                inline=False,
            )

        return {
            "embed": embed,
            "content": "",
        }

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content(interaction)
        await self._before_send()
        await self.commit()
        if interaction.response.is_done():
            await interaction.edit_original_response(
                view=self, **content_kwargs, **kwargs
            )
        else:
            await interaction.response.edit_message(
                view=self, **content_kwargs, **kwargs
            )


class AdventureSettingsUI(AdventureView):
    """
    A user interface class for managing adventure settings in the G0-T0 bot.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: Member, adventure: Adventure):
        Creates a new instance of AdventureSettingsUI.
    adventure_dm(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Manage DM(s)" button click event.
    adventure_players(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Manage Player(s)" button click event.
    adventure_reward(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Reward CC" button click event and rewards players and DMs with CC.
    npcs(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "NPCs" button click event and opens the NPC settings UI.
    factions(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Factions" button click event and defers to the adventure factions view.
    adventure_close(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Close Adventure" button click event and closes the adventure after confirmation.
    exit(self, *_):
        Handles the "Exit" button click event and exits the UI.
    _before_send(self):
        Removes certain buttons if the user is not a DM or admin.
    """

    @classmethod
    def new(
        cls,
        bot: G0T0Bot,
        owner: discord.Member,
        adventure: Adventure,
        guild: PlayerGuild,
    ):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.adventure = adventure
        inst.guild = guild

        return inst

    @discord.ui.button(label="Manage DM(s)", style=discord.ButtonStyle.primary, row=1)
    async def adventure_dm(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.dm_select = True
        await self.defer_to(_AdventureMemberSelect, interaction)

    @discord.ui.button(
        label="Manage Player(s)", style=discord.ButtonStyle.primary, row=1
    )
    async def adventure_players(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.dm_select = False
        await self.defer_to(_AdventureMemberSelect, interaction)

    @discord.ui.button(label="Reward CC", style=discord.ButtonStyle.green, row=2)
    async def adventure_reward(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = AdventureRewardModal(self.adventure)
        response = await self.prompt_modal(interaction, modal)

        if response.cc > 0:
            self.adventure.cc += response.cc

            dm_reward = response.cc + ceil(response.cc * 0.25)
            for dm in self.adventure.dms:
                player = await Player.get_player(self.bot, dm, self.adventure.guild_id)
                await DBLog.create(
                    self.bot,
                    interaction,
                    player,
                    self.owner,
                    "ADVENTURE_DM",
                    notes=f"{self.adventure.name}",
                    cc=dm_reward,
                    adventure=self.adventure,
                    silent=True,
                )

            player_reward = response.cc

            for character in self.adventure.player_characters:
                player = await Player.get_player(
                    self.bot, character.player_id, self.adventure.guild_id
                )
                await DBLog.create(
                    self.bot,
                    interaction,
                    player,
                    self.owner,
                    "ADVENTURE",
                    character=character,
                    notes=f"{self.adventure.name}",
                    cc=player_reward,
                    adventure=self.adventure,
                    silent=True,
                )

            embed = PlayerEmbed(
                self.owner,
                title="Adventure Rewards",
                description=(
                    f"**Adventure**: {self.adventure.name}\n"
                    f"**CC Earned**: {response.cc:,}\n"
                    f"**CC Earned to date**: {self.adventure.cc:,}\n"
                ),
                timestamp=discord.utils.utcnow(),
            )

            embed.set_thumbnail(url=THUMBNAIL)
            embed.set_footer(
                text=f"Logged by {self.owner.name}",
                icon_url=self.owner.display_avatar.url,
            )

            embed.add_field(
                name=f"DM{'s' if len(self.adventure.dms) > 1 else ''}",
                value="\n".join(
                    [
                        f"{ZWSP3}- {interaction.guild.get_member(dm).mention}"
                        for dm in self.adventure.dms
                        if interaction.guild.get_member(dm)
                    ]
                ),
                inline=False,
            )

            if self.adventure.player_characters:
                embed.add_field(
                    name="Players",
                    value="\n".join(
                        [
                            f"{ZWSP3}- {character.name} ({interaction.guild.get_member(character.player_id).mention})"
                            for character in self.adventure.player_characters
                            if interaction.guild.get_member(character.player_id)
                        ]
                    ),
                    inline=False,
                )

            await interaction.channel.send(embed=embed)
        await self.refresh_content(interaction)

    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.primary, row=2)
    async def npcs(self, _: discord.ui.Button, interaction: discord.Interaction):
        guild = await PlayerGuild.get_player_guild(self.bot, self.adventure.guild_id)
        view = NPCSettingsUI.new(
            self.bot, self.owner, guild, AdventureSettingsUI, adventure=self.adventure
        )
        await view.send_to(interaction)

    @discord.ui.button(label="Factions", style=discord.ButtonStyle.primary, row=2)
    async def factions(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_AdventureFactions, interaction)

    @discord.ui.button(label="Close Adventure", style=discord.ButtonStyle.danger, row=2)
    async def adventure_close(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        conf = await confirm(
            interaction,
            "Are you sure you want to end this adventure? (Reply with yes/no)",
            True,
            self.bot,
        )

        if conf is None:
            raise TimeoutError()
        elif not conf:
            raise G0T0Error("Ok, cancelling")
        else:
            # Log Renown if applicable
            if len(self.adventure.factions) > 0:
                renown = await confirm(
                    interaction,
                    "Is this being closed due to inactivity? (Reply with yes/no)",
                    True,
                    self.bot,
                )

                if renown is None:
                    raise TimeoutError()
                elif not renown:
                    amount = 1 if len(self.adventure.factions) > 1 else 2

                    for char in self.adventure.player_characters:
                        player = await Player.get_player(
                            self.bot, char.player_id, self.adventure.guild_id
                        )

                        for faction in self.adventure.factions:
                            await DBLog.create(
                                self.bot,
                                interaction,
                                player,
                                self.owner,
                                "RENOWN",
                                character=char,
                                notes=f"Adventure Reward: {self.adventure.name}",
                                renown=amount,
                                faction=faction,
                                silent=True,
                            )

            # Close adventure and clean up role
            self.adventure.end_ts = datetime.now(timezone.utc)
            try:
                await self.adventure.role.delete(reason=f"Closing adventure")
            except:
                pass
            await self.adventure.upsert()

            # NPC Cleanup
            for npc in self.adventure.npcs:
                await npc.delete()

            await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if self.owner.id not in self.adventure.dms and not self.guild.is_admin(
            self.owner
        ):
            self.remove_item(self.adventure_dm)
            self.remove_item(self.adventure_players)
            self.remove_item(self.adventure_close)


class _AdventureMemberSelect(AdventureView):
    @discord.ui.user_select(placeholder="Select a Player", row=1)
    async def member_select(
        self, user: discord.ui.Select, interaction: discord.Interaction
    ):
        member: discord.Member = user.values[0]
        self.member = member
        self.player = await Player.get_player(
            self.bot, self.member.id, interaction.guild.id
        )
        self.character = None
        if not self.dm_select and self.get_item("char_select") is None:
            self.add_item(self.character_select)
        await self.refresh_content(interaction)

    @discord.ui.select(
        placeholder="Select a character",
        options=[discord.SelectOption(label="You should never see me")],
        row=2,
        custom_id="char_select",
    )
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Player", row=3)
    async def add_member(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.dm_select:
            if self.member.id in self.adventure.dms:
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.member.mention} is already a DM of this adventure"
                    ),
                    delete_after=5,
                )
            elif character := next(
                (
                    ch
                    for ch in self.adventure._player_characters
                    if ch.player_id == self.player.id
                ),
                None,
            ):
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.member.mention} can't be a player and a DM"
                    ),
                    delete_after=5,
                )
            else:
                self.adventure.dms.append(self.member.id)
                await self.adventure.update_dm_permissions(self.member)
        else:
            if (
                self.adventure.characters
                and self.character.id in self.adventure.characters
            ):
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.character.name} is already in the adventure"
                    ),
                    delete_after=5,
                )
            elif self.member.id in self.adventure.dms:
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.character.name} is a DM for this adventure"
                    ),
                    delete_after=5,
                )
            elif character := next(
                (
                    ch
                    for ch in self.adventure._player_characters
                    if ch.player_id == self.player.id
                ),
                None,
            ):
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.member.mention} already has a character in the adventure"
                    ),
                    delete_after=5,
                )
            else:
                self.adventure._player_characters.append(self.character)
                self.adventure.characters.append(self.character.id)

                if self.adventure.role not in self.member.roles:
                    await self.member.add_roles(
                        self.adventure.role,
                        reason=f"{self.character.name} added to {self.adventure.name} by {self.owner.name}",
                    )

                await interaction.channel.send(
                    f"{self.character.name} ({self.member.mention}) added to {self.adventure.name}"
                )

        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Player", row=3)
    async def remove_member(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.dm_select:
            if self.member.id not in self.adventure.dms:
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.member.mention} is not a DM of this adventure"
                    ),
                    delete_after=5,
                )
            elif len(self.adventure.dms) == 1:
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"Cannot remove the last DM. Either add another one first, or close the adventure"
                    ),
                    delete_after=5,
                )
            else:
                self.adventure.dms.remove(self.member.id)
                await self.adventure.update_dm_permissions(self.member, True)
                await self.adventure.upsert()
        else:
            if character := next(
                (
                    ch
                    for ch in self.adventure._player_characters
                    if ch.player_id == self.player.id
                ),
                None,
            ):
                self.adventure._player_characters.remove(character)
                self.adventure.characters.remove(character.id)

                if self.adventure.role in self.member.roles:
                    await self.member.remove_roles(
                        self.adventure.role,
                        reason=f"Removed from {self.adventure.name} by {self.owner.name}",
                    )
            else:
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"{self.member.mention} is not part of this adventure"
                    ),
                    delete_after=5,
                )

        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.character = None
        self.player = None
        self.member = None
        await self.defer_to(AdventureSettingsUI, interaction)

    async def _before_send(self):
        if self.member is None or self.dm_select:
            self.remove_item(self.character_select)
        else:
            if self.player.characters:
                if self.character is None:
                    self.character = self.player.characters[0]

                char_list = []
                for char in self.player.characters:
                    char_list.append(
                        discord.SelectOption(
                            label=f"{char.name}",
                            value=f"{self.player.characters.index(char)}",
                            default=(
                                True
                                if self.character
                                and self.player.characters.index(char)
                                == self.player.characters.index(self.character)
                                else False
                            ),
                        )
                    )
                self.character_select.options = char_list
            else:
                self.remove_item(self.character_select)

        if self.dm_select:
            self.member_select.placeholder = "Select a DM"
            self.add_member.label = "Add DM"
            self.remove_member.label = "Remove DM"
        else:
            self.member_select.placeholder = "Select a Player"
            self.add_member.label = "Add Player"
            self.remove_member.label = "Remove Player"

        self.add_member.disabled = (
            False if self.member and (not self.dm_select and self.character) else True
        )
        self.remove_member.disabled = (
            False if self.member and (not self.dm_select and self.character) else True
        )


class _AdventureFactions(AdventureView):
    faction: Faction = None

    async def _before_send(self):
        faction_list = [
            discord.SelectOption(
                label=f"{f.value}",
                value=f"{f.id}",
                default=True if self.faction and self.faction.id == f.id else False,
            )
            for f in self.bot.compendium.get_values(Faction)
        ]

        self.faction_select.options = faction_list

        self.add_faction.disabled = False if self.faction else True
        self.remove_faction.disabled = False if self.faction else True

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def faction_select(
        self, f: discord.ui.Select, interaction: discord.Interaction
    ):
        self.faction = self.bot.compendium.get_object(Faction, int(f.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Faction", style=discord.ButtonStyle.primary, row=2)
    async def add_faction(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.faction and self.faction.id not in [
            f.id for f in self.adventure.factions
        ]:
            if len(self.adventure.factions) >= 2 and not self.guild.is_admin(
                self.owner
            ):
                await interaction.channel.send(
                    embed=ErrorEmbed(
                        f"You do not have the ability to add more than 2 factions to an adventure"
                    ),
                    delete_after=5,
                )
            else:
                self.adventure.factions.append(self.faction)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Faction", style=discord.ButtonStyle.primary, row=2)
    async def remove_faction(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.faction and self.faction.id in [f.id for f in self.adventure.factions]:
            faction = next(
                (f for f in self.adventure.factions if f.id == self.faction.id), None
            )
            self.adventure.factions.remove(faction)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.faction = None
        await self.defer_to(AdventureSettingsUI, interaction)


class AdventureRewardModal(discord.ui.Modal):
    adventure: Adventure
    cc: int = 0

    def __init__(self, adventure: Adventure):
        super().__init__(title=f"{adventure.name} Rewards")
        self.adventure = adventure

        self.add_item(
            discord.ui.InputText(
                label="CC Amount", required=True, placeholder="CC Amount", max_length=3
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            self.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(
                embed=ErrorEmbed(f"Chain codes must be a number!"), delete_after=5
            )

        await interaction.response.defer()
        self.stop()
