import re
from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.helpers import get_webhook, process_message
from Resolute.models.categories import CharacterClass, CharacterSpecies
from Resolute.models.categories.categories import CharacterArchetype, Faction
from Resolute.models.embeds import CharacterEmbed, ErrorEmbed
from Resolute.models.embeds.players import PlayerOverviewEmbed, RPPostEmbed
from Resolute.models.objects.characters import CharacterRenown, PlayerCharacterClass
from Resolute.models.objects.enum import ApplicationType
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import Player, PlayerCharacter, RPPost
from Resolute.models.objects.webhook import G0T0Webhook
from Resolute.models.views.base import InteractiveView


class CharacterViewEmbed(CharacterEmbed):
    def __init__(self, player: Player, character: PlayerCharacter):
        super().__init__(
            player,
            character,
            title=f"Character Info - [{character.level}] {character.name}",
        )

        class_str = f"\n{ZWSP3*2}".join(
            [f"{c.get_formatted_class()}" for c in character.classes]
        )
        class_str = (
            f"\n{ZWSP3*2}{class_str}" if len(character.classes) > 1 else class_str
        )

        self.description = (
            f"**Player**: {player.member.mention}\n"
            f"**Faction**: {character.faction.value if character.faction else '*None*'}\n"
            f"**Total Renown**: {character.total_renown}\n"
            f"**Species**: {character.species.value}\n"
            f"**Credits**: {character.credits:,}\n"
            f"**Class{'es' if len(character.classes) > 1 else ''}**: {class_str}\n"
        )

        if character.renown:
            self.add_field(
                name="Renown Breakdown",
                value="\n".join(
                    [
                        f"{ZWSP3}**{r.faction.value}**: {r.renown}"
                        for r in character.renown
                    ]
                ),
                inline=True,
            )


# Character Manage Base setup
class CharacterManage(InteractiveView):
    """
    CharacterManage class that inherits from InteractiveView.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple containing attribute names to be copied in the menu.
        bot (G0T0Bot): An instance of the G0T0Bot.
        owner (discord.Member, optional): The owner of the character. Defaults to None.
        player (Player): The player associated with the character.
        active_character (PlayerCharacter, optional): The currently active character. Defaults to None.
    """

    __menu_copy_attrs__ = ("bot", "player", "active_character")
    bot: G0T0Bot
    owner: discord.Member = None
    player: Player
    active_character: PlayerCharacter = None

    async def get_content(self) -> Mapping:
        if self.active_character:
            embed = CharacterViewEmbed(self.player, self.active_character)

        else:
            embed = PlayerOverviewEmbed(self.player, self.bot.compendium)

        return {"embed": embed, "content": ""}


# Main Character Manage UI
class CharacterManageUI(CharacterManage):
    """
    A user interface class for managing player characters in the G0-T0-Resolute game.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: discord.Member, player: Player) -> CharacterManageUI
        Class method to create a new instance of CharacterManageUI.
    character_select(self, char: discord.ui.Select, interaction: discord.Interaction)
        Async method to handle character selection from a dropdown menu.
    edit_character(self, _: discord.ui.Button, interaction: discord.Interaction)
        Async method to handle the edit character button click.
    new_character_create(self, _: discord.ui.Button, interaction: discord.Interaction)
        Async method to handle the new/reroll character button click.
    inactivate_character(self, _: discord.ui.Button, interaction: discord.Interaction)
        Async method to handle the inactivate character button click.
    exit(self, *_)
        Async method to handle the exit button click.
    _before_send(self)
        Async method to prepare the UI before sending it to the user.
    get_content(self) -> Mapping
        Async method to get the content to be displayed in the UI.
    """

    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        inst.active_character = (
            player.characters[0] if len(player.characters) > 0 else None
        )

        inst.new_character: PlayerCharacter = PlayerCharacter(
            bot.db, bot.compendium, player_id=player.id, guild_id=player.guild_id
        )
        inst.new_class: PlayerCharacterClass = PlayerCharacterClass(
            bot.db, bot.compendium
        )

        return inst

    @discord.ui.select(placeholder="Select a character to manage", row=1)
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        self.active_character = next(
            (c for c in self.player.characters if c.id == int(char.values[0])), None
        )
        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, row=2)
    async def edit_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_EditCharacter, interaction)

    @discord.ui.button(label="New/Reroll", style=discord.ButtonStyle.green, row=2)
    async def new_character_create(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_NewCharacter, interaction)

    @discord.ui.button(label="Inactivate", style=discord.ButtonStyle.danger, row=2)
    async def inactivate_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_InactivateCharacter, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if len(self.player.characters) == 0:
            self.remove_item(self.edit_character)
            self.remove_item(self.character_select)
            self.new_character_create.label = "New Character"
        else:
            # Build the Character List
            char_list = []
            for char in self.player.characters:
                char_list.append(
                    discord.SelectOption(
                        label=f"{char.name}",
                        value=f"{char.id}",
                        default=(
                            True
                            if self.active_character
                            and char.id == self.active_character.id
                            else False
                        ),
                    )
                )
            self.character_select.options = char_list

        if (
            not self.player.guild.is_admin(self.player.member)
            or len(self.player.characters) == 0
        ):
            self.remove_item(self.inactivate_character)


# Character Manage - New Character
class _NewCharacter(CharacterManage):
    new_type: ApplicationType = None
    new_character: PlayerCharacter = None
    new_class: PlayerCharacterClass = None
    transfer_renown: bool = False
    new_cc: int = 0
    new_credits: int = 0

    @discord.ui.select(placeholder="Select new type", row=1)
    async def new_character_type(
        self, type: discord.ui.Select, interaction: discord.Interaction
    ):
        self.new_type = ApplicationType[type.values[0]]
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Basic Information", style=discord.ButtonStyle.primary, row=3
    )
    async def new_character_information(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = NewCharacterInformationModal(
            self.new_character,
            self.active_character,
            self.new_cc,
            self.new_credits,
            self.new_type,
        )
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_cc = response.new_cc
        self.new_credits = response.new_credits

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Species/Class Information", style=discord.ButtonStyle.primary, row=3
    )
    async def new_character_species(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = NewCharacterClassSpeciesModal(
            self.new_character, self.new_class, self.bot.compendium
        )
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_class = response.char_class

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Create Character", style=discord.ButtonStyle.green, row=4, disabled=True
    )
    async def new_character_create(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.new_character = await self.player.create_character(
            self.new_type,
            self.new_character,
            self.new_class,
            old_character=self.active_character,
        )
        log_entry = await self.bot.log(
            interaction,
            self.player,
            self.owner,
            "NEW_CHARACTER",
            character=self.new_character,
            notes="Initial Log",
            cc=self.new_cc,
            credits=self.new_credits,
            ignore_handicap=True,
            silent=True,
        )

        self.player = await self.bot.get_player(self.player.id, self.player.guild_id)
        await self.bot.manage_player_tier_roles(self.player, "Character Created!")

        embed = CharacterEmbed(
            self.player,
            self.new_character,
            title=f"Character Created - {self.new_character.name}",
            description=(
                f"**Player**: {log_entry.player.member.mention}\n"
                f"**Level**: {log_entry.character.level}\n"
                f"**Species**: {log_entry.character.species.value}\n"
                f"**Class**: {log_entry.character.classes[0].get_formatted_class()}\n"
                f"**Starting Credits**: {log_entry.credits:,}\n"
                f"{f'**CC Adjustment**: {log_entry.cc:,}' if log_entry.cc != 0 and log_entry.cc != None else ''}"
            ),
        )

        embed.set_footer(
            text=f"Created by: {log_entry.author.member.name} - Log #: {log_entry.id}",
            icon_url=log_entry.author.member.display_avatar.url,
        )

        await interaction.channel.send(embed=embed)

        if (
            self.player.guild.first_character_message
            and self.player.guild.first_character_message != ""
            and self.player.guild.first_character_message is not None
            and len(self.player.characters) == 1
            and not self.active_character
        ):
            mappings = {
                "character.name": self.new_character.name,
                "character.level": str(self.new_character.level),
            }
            await interaction.channel.send(
                process_message(
                    self.player.guild.first_character_message,
                    self.player.guild,
                    self.player.member,
                    mappings,
                )
            )

        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)

    async def _before_send(self):
        if not self.new_character:
            self.new_character = PlayerCharacter(self.bot.db, self.bot.compendium)

        if not self.new_class:
            self.new_class = PlayerCharacterClass(self.bot.db, self.bot.compendium)

        new_character_type_options = []
        for type in ApplicationType:
            if type == ApplicationType.new:
                if (
                    len(self.player.characters) == 0
                    or len(self.player.characters) < self.player.guild.max_characters
                ):
                    new_character_type_options.append(
                        discord.SelectOption(
                            label=f"{type.value}",
                            value=f"{type.name}",
                            default=(
                                True
                                if self.new_type == type
                                or len(self.player.characters) == 0
                                else False
                            ),
                        )
                    )
                    self.new_type = (
                        ApplicationType.new if not self.new_type else self.new_type
                    )
            elif len(self.player.characters) > 0:
                new_character_type_options.append(
                    discord.SelectOption(
                        label=f"{type.value}",
                        value=f"{type.name}",
                        default=True if self.new_type == type else False,
                    )
                )

        self.new_character_type.options = new_character_type_options

        if (
            self.new_type
            and self.new_character.is_valid(self.player.guild.max_level)
            and self.new_class.is_valid()
            and (self.player.cc + self.new_cc >= 0)
        ):
            self.new_character_create.disabled = False
        else:
            self.new_character_create.disabled = True

        pass

    async def get_content(self) -> Mapping:
        embed = CharacterEmbed(
            self.player,
            self.new_character,
            title=f"Information for {self.player.member.display_name}",
            description=(
                f"**Name**: {self.new_character.name if self.new_character.name else ''}\n"
                f"**Level**: {self.new_character.level}{f' (*Too high for server. Max server level is `{self.player.guild.max_level}`*)' if self.new_character.level > self.player.guild.max_level else ''}\n"
                f"**Species**: {self.new_character.species.value if hasattr(self.new_character.species, 'value') else ''}\n"
                f"**Class**: {self.new_class.get_formatted_class() if hasattr(self.new_class, 'primary_class') else ''}\n"
                f"**Starting Credits**: {self.new_credits:,}\n"
            ),
        )

        if self.new_cc != 0:
            embed.description += f"**CC Adjustment**: {self.new_cc}{f''' (*This would put the player at {self.player.cc + self.new_cc:,} CC*)''' if self.player.cc + self.new_cc < 0 else ''}\n"
        return {"embed": embed, "content": ""}


# Character Manage - Inactivate Character
class _InactivateCharacter(CharacterManage):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def inactivate_character_confirm(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.active_character.active = False

        await self.bot.log(
            interaction,
            self.player,
            self.owner,
            "MOD_CHARACTER",
            character=self.active_character,
            notes="Inactivating Character",
        )

        await self.bot.manage_player_tier_roles(self.player, "Inactivating character")
        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)

    async def _before_send(self):
        pass


# Character Manage - Edit Character
class _EditCharacter(CharacterManage):
    @discord.ui.button(label="Manage Classes", style=discord.ButtonStyle.primary, row=1)
    async def manage_class(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_EditCharacterClass, interaction)

    @discord.ui.button(label="Manage Renown", style=discord.ButtonStyle.primary, row=1)
    async def manage_renown(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_EditCharacterRenown, interaction)

    @discord.ui.button(
        label="Edit Information", style=discord.ButtonStyle.primary, row=2
    )
    async def edit_character_information(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = CharacterInformationModal(self.active_character, self.bot.compendium)
        response: CharacterInformationModal = await self.prompt_modal(
            interaction, modal
        )

        if response.update:
            await self.bot.log(
                interaction,
                self.player,
                self.owner,
                "MOD_CHARACTER",
                character=self.active_character,
                notes="Character modifcation",
                silent=True,
            )
        await self.refresh_content(interaction)

    @discord.ui.button(label="Level Up", style=discord.ButtonStyle.primary, row=2)
    async def level_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.player.highest_level_character.level < 3 and (
            self.player.needed_rps > self.player.completed_rps
            or self.player.needed_arenas > self.player.completed_arenas
        ):

            raise G0T0Error(
                f"{self.player.member.mention} has not completed their requirements to level up.\n"
                f"Completed RPs: {min(self.player.completed_rps, self.player.needed_rps)}/{self.player.needed_rps}\n"
                f"Completed Arena Phases: {min(self.player.completed_arenas, self.player.needed_arenas)}/{self.player.needed_arenas}"
            )

        self.active_character.level += 1
        await self.bot.log(
            interaction,
            self.player,
            self.owner,
            "LEVEL",
            character=self.active_character,
            notes="Player level up",
            silent=True,
        )

        await self.bot.manage_player_tier_roles(self.player, "Level up")

        embed = CharacterEmbed(
            self.player,
            self.active_character,
            title="Level up successful!",
            description=f"{self.active_character.name} ({self.player.member.mention}) is now level {self.active_character.level}",
            timestamp=discord.utils.utcnow(),
        )

        embed.set_footer(
            text=f"Logged by {self.owner.name}", icon_url=self.owner.display_avatar.url
        )

        await interaction.channel.send(embed=embed)

        await self.on_timeout()

    @discord.ui.button(label="Date of Birth", style=discord.ButtonStyle.primary, row=2)
    async def dob_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        old_dob = self.active_character.dob
        modal = CharacterDOBModal(self.player, self.active_character)

        if self.active_character.dob != old_dob:
            await self.bot.log(
                interaction,
                self.player,
                self.owner,
                "MOD_CHARACTER",
                character=self.active_character,
                notes="Character modifcation",
                silent=True,
            )

        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)

    async def _before_send(self):
        if self.active_character.level + 1 > self.player.guild.max_level:
            self.level_character.disabled = True
        else:
            self.level_character.disabled = False
        pass

        if not self.player.guild.is_admin(self.player.member):
            self.remove_item(self.manage_renown)

        if not self.player.guild.calendar:
            self.remove_item(self.dob_character)


# Character Manage - Edit Character Class
class _EditCharacterClass(CharacterManage):
    active_class: PlayerCharacterClass = None

    @discord.ui.select(placeholder="Select class", row=1)
    async def select_class(
        self, char_class: discord.ui.Select, interaction: discord.Interaction
    ):
        self.active_class = self.active_character.classes[int(char_class.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Class", style=discord.ButtonStyle.grey, row=2)
    async def new_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterClassModal(self.active_character, self.bot)
        response: CharacterClassModal = await self.prompt_modal(interaction, modal)
        new_class = PlayerCharacterClass(
            self.bot.db,
            self.bot.compendium,
            character_id=self.active_character.id,
            primary_class=response.primary_class,
            archetype=response.archetype,
        )

        if new_class.primary_class:
            new_class = await new_class.upsert()
            self.active_character.classes.append(new_class)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit Class", style=discord.ButtonStyle.grey, row=2)
    async def edit_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterClassModal(self.active_character, self.bot, self.active_class)
        response = await self.prompt_modal(interaction, modal)

        if response.primary_class and (
            response.primary_class != self.active_class.primary_class
            or response.archetype != self.active_class.archetype
        ):
            self.active_class.primary_class = response.primary_class
            self.active_class.archetype = response.archetype
            await self.active_class.upsert()

        await self.refresh_content(interaction)

    @discord.ui.button(label="Delete Class", style=discord.ButtonStyle.red, row=2)
    async def delete_class(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if len(self.active_character.classes) == 1:
            raise G0T0Error(f"Character only has one class")
        else:
            self.active_character.classes.pop(
                self.active_character.classes.index(self.active_class)
            )
            self.active_class.active = False
            await self.active_class.upsert()
            self.active_class = self.active_character.classes[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

    async def _before_send(self):
        if not self.active_class:
            self.active_class = self.active_character.classes[0]
        class_list = []
        for char_class in self.active_character.classes:
            class_list.append(
                discord.SelectOption(
                    label=f"{char_class.get_formatted_class()}",
                    value=f"{self.active_character.classes.index(char_class)}",
                    default=(
                        True
                        if self.active_class
                        and self.active_character.classes.index(char_class)
                        == self.active_character.classes.index(self.active_class)
                        else False
                    ),
                )
            )
        self.select_class.options = class_list


# Character Manage - Edit Renown
class _EditCharacterRenown(CharacterManage):
    faction: Faction = None

    async def _before_send(self):
        faction_list = []

        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(
                discord.SelectOption(
                    label=f"{faction.value}",
                    value=f"{faction.id}",
                    default=(
                        True
                        if self.faction and self.faction.id == faction.id
                        else False
                    ),
                )
            )

        self.select_faction.options = faction_list

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def select_faction(
        self, fac: discord.ui.Select, interaction: discord.Interaction
    ):
        self.faction = self.bot.compendium.get_object(Faction, int(fac.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Add/Remove Renown", style=discord.ButtonStyle.primary, row=2
    )
    async def modify_renown(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        renown = next(
            (
                r
                for r in self.active_character.renown
                if r.faction.id == self.faction.id
            ),
            CharacterRenown(
                self.bot.db,
                self.bot.compendium,
                faction=self.faction,
                character_id=self.active_character.id,
            ),
        )
        modal = CharacterRenownModal(renown)
        response = await self.prompt_modal(interaction, modal)

        if response.amount != 0:
            await self.bot.log(
                interaction,
                self.player,
                self.owner,
                "RENOWN",
                character=self.active_character,
                renown=response.amount,
                faction=self.faction,
                show_values=True,
            )
            self.active_character = await self.bot.get_character(
                self.active_character.id
            )
            await self.on_timeout()
        else:
            self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)


# Character Manage Modals
class NewCharacterInformationModal(discord.ui.Modal):
    character: PlayerCharacter
    active_character: PlayerCharacter
    new_cc: int
    new_credits: int
    new_type: ApplicationType

    def __init__(
        self,
        character,
        active_character,
        new_cc: int = 0,
        new_credits: int = 0,
        new_type: ApplicationType = None,
    ):
        super().__init__(
            title=f"{character.name if character.name else 'New Character'} Setup"
        )
        self.character = character
        self.active_character = active_character
        self.new_cc = new_cc
        self.new_credits = new_credits
        self.new_type = new_type

        self.add_item(
            discord.ui.InputText(
                label="Character Name",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Character Name",
                max_length=2000,
                value=self.character.name if self.character.name else "",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Level",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Level",
                max_length=2,
                value=str(self.character.level),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Credits",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Credits",
                max_length=7,
                value=str(self.new_credits),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="CC Refund/Adjustment",
                style=discord.InputTextStyle.short,
                required=False,
                placeholder="Chain Codes",
                max_length=7,
                value=str(self.new_cc),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        err_str = []
        self.character.name = self.children[0].value
        int_values = [
            (self.children[2].value, "new_credits", "Credits must be a number!"),
            (self.children[3].value, "new_cc", "Chain codes must be a number!"),
        ]

        for value, node, err_msg in int_values:
            try:
                setattr(self, node, int(value))
            except:
                err_str.append(err_msg)

        try:
            self.character.level = int(self.children[1].value)
        except:
            err_str.append("Level must be a number!")

        if len(err_str) > 0:
            await interaction.channel.send(
                embed=ErrorEmbed("\n".join(err_str)), delete_after=5
            )

        await interaction.response.defer()
        self.stop()


class NewCharacterClassSpeciesModal(discord.ui.Modal):
    compendium: Compendium
    character: PlayerCharacter
    char_class: PlayerCharacterClass

    def __init__(self, character, char_class, compendium):
        super().__init__(
            title=f"{character.name if character.name else 'New Character'} Setup"
        )
        self.character = character
        self.char_class = char_class
        self.compendium = compendium

        self.add_item(
            discord.ui.InputText(
                label="Species",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Species",
                max_length=100,
                value=(
                    self.character.species.value
                    if hasattr(self.character.species, "value")
                    else ""
                ),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Class",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Class",
                max_length=100,
                value=(
                    self.char_class.primary_class.value
                    if hasattr(self.char_class, "primary_class")
                    and self.char_class.primary_class
                    else ""
                ),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Archetype",
                style=discord.InputTextStyle.short,
                required=False,
                placeholder="Archetype",
                max_length=100,
                value=(
                    self.char_class.archetype.value
                    if hasattr(self.char_class, "archetype")
                    and self.char_class.archetype
                    else ""
                ),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        err_str = []

        if species := self.compendium.get_object(
            CharacterSpecies, self.children[0].value
        ):
            self.character.species = species
        else:
            err_str.append(f"`{self.children[0].value}` is not a valid species!")

        if primary_class := get_primary_class(
            self.children[1].value, self.compendium, err_str
        ):
            self.char_class.primary_class = primary_class

            if self.children[2].value != "" and (
                archetype := get_archetype(
                    self.children[2].value, primary_class, self.compendium, err_str
                )
            ):
                self.char_class.archetype = archetype
            else:
                self.char_class.archetype = None

        if len(err_str) > 0:
            await interaction.channel.send(
                embed=ErrorEmbed("\n".join(err_str)), delete_after=5
            )

        await interaction.response.defer()
        self.stop()


class CharacterClassModal(discord.ui.Modal):
    compendium: Compendium
    character: PlayerCharacter
    char_class: CharacterClass
    primary_class: CharacterClass
    archetype: CharacterArchetype

    def __init__(
        self, character, bot: G0T0Bot, char_class: PlayerCharacterClass = None
    ):
        super().__init__(title=f"Class for {character.name}")

        self.character = character
        self.char_class: PlayerCharacterClass = char_class or PlayerCharacterClass(
            bot.db, bot.compendium, character_id=character.id
        )
        self.primary_class = self.char_class.primary_class or None
        self.archetype = self.char_class.archetype or None
        self.compendium = bot.compendium

        self.add_item(
            discord.ui.InputText(
                label="Class",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Class",
                max_length=100,
                value=self.primary_class.value if self.primary_class else "",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Archetype",
                style=discord.InputTextStyle.short,
                required=False,
                placeholder="Archetype",
                max_length=100,
                value=self.archetype.value if self.archetype else "",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        err_str = []
        if primary_class := get_primary_class(
            self.children[0].value, self.compendium, err_str
        ):
            self.primary_class = primary_class

            if self.children[1].value != "" and (
                archetype := get_archetype(
                    self.children[1].value, primary_class, self.compendium, err_str
                )
            ):
                self.archetype = archetype
            else:
                self.archetype = None
        else:
            self.primary_class = None

        if self.primary_class:
            for char_class in self.character.classes:
                if (
                    char_class.primary_class == self.primary_class
                    and char_class.archetype == self.archetype
                ):
                    if (
                        hasattr(self.char_class, "id")
                        and self.char_class.id == char_class.id
                    ):
                        pass
                    else:
                        err_str.append(f"Duplicate classes are not allowed")
                        self.primary_class = None
                        self.archetype = None

        if len(err_str) > 0:
            await interaction.channel.send(
                embed=ErrorEmbed("\n".join(err_str)), delete_after=5
            )

        await interaction.response.defer()
        self.stop()


class CharacterInformationModal(discord.ui.Modal):
    character: PlayerCharacter
    compendium: Compendium

    def __init__(self, character: PlayerCharacter, compendium: Compendium):
        super().__init__(title=f"Information for {character.name}")
        self.character = character
        self.compendium = compendium
        self.update = False

        self.add_item(
            discord.ui.InputText(
                label="Character Name",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Character Name",
                max_length=2000,
                value=self.character.name if self.character.name else "",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Species",
                style=discord.InputTextStyle.short,
                required=True,
                placeholder="Species",
                max_length=100,
                value=(
                    self.character.species.value
                    if hasattr(self.character.species, "value")
                    else ""
                ),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        if self.character.name != self.children[0].value:
            self.character.name = self.children[0].value
            self.update = True

        if species := self.compendium.get_object(
            CharacterSpecies, self.children[1].value
        ):
            if self.character.species != species:
                self.character.species = species
                self.update = True
        await interaction.response.defer()
        self.stop()


class CharacterRenownModal(discord.ui.Modal):
    renown: CharacterRenown
    amount: int = 0

    def __init__(self, renown):
        super().__init__(title=f"Modify Renown")
        self.renown = renown

        self.add_item(
            discord.ui.InputText(
                label="Renown Amount (+/-)",
                placeholder="Renown Amount (+/-)",
                max_length=4,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            amount = max(0, self.renown.renown + int(self.children[0].value))
            if amount == 0:
                await interaction.channel.send(
                    embed=ErrorEmbed(f"Renown cannot go below `0`")
                )
            else:
                self.amount = int(self.children[0].value)
        except:
            await interaction.channel.send(
                embed=ErrorEmbed(f"Renown must be a number!")
            )

        await interaction.response.defer()
        self.stop()


# Character Manage View specific helpers
def get_primary_class(class_value: str, compendium: Compendium, err_str: list = []):
    primary_class = compendium.get_object(CharacterClass, class_value)

    if not primary_class:
        class_value = re.sub(f"light|dark", "", class_value)
        primary_class = compendium.get_object(CharacterClass, class_value)

    if primary_class:
        return primary_class
    else:
        err_str.append(f"`{class_value}` is not a valid primary class")
        return None


def get_archetype(
    archetype_value: str,
    primary_class: CharacterClass,
    compendium: Compendium,
    err_str: list = [],
):
    valid_archetypes = [
        x for x in compendium.archetype[0].values() if x.parent == primary_class.id
    ]

    archetype = next(
        (at for at in valid_archetypes if archetype_value.lower() in at.value.lower()),
        None,
    )

    if archetype:
        return archetype
    else:
        err_str.append(
            f"`{archetype_value}` is not a valid archetype for {primary_class.value}"
        )
        return None


# Say Edit
class SayEditModal(discord.ui.Modal):
    """
    A modal dialog for editing a message.
    Attributes:
        message (discord.Message): The message to be edited.
        bot (G0T0Bot): The bot instance.
    Methods:
        __init__(bot: G0T0Bot, message: discord.Message = None):
            Initializes the modal with the given bot and message.
        callback(interaction: discord.Interaction):
            Handles the interaction when the modal is submitted.
    """

    bot: G0T0Bot
    webhook: G0T0Webhook

    def __init__(self, bot: G0T0Bot, webhook: G0T0Webhook):
        super().__init__(title="Edit discord.Message")
        self.bot = bot
        self.webhook = webhook

        self.add_item(
            discord.ui.InputText(
                label="Message",
                placeholder="",
                value=self.webhook.message.content,
                style=discord.InputTextStyle.long,
                max_length=2000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        content = self.children[0].value
        await interaction.response.defer()
        self.stop()
        await self.webhook.edit(content)


# Character Settings
class CharacterSettings(InteractiveView):
    """
    CharacterSettings is an interactive view for managing character settings in the G0-T0 Resolute bot.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to copy when creating a new menu instance.
        bot (G0T0Bot): The bot instance.
        player (Player): The player instance.
        active_character (PlayerCharacter): The currently active character.
        active_channel (TextChannel): The currently active text channel.
    Methods:
        commit(): Commits the current character settings to the database and updates the player instance.
        get_content() -> Mapping: Generates the content to be displayed in the character settings view.
    """

    __menu_copy_attrs__ = ("bot", "player", "active_character")

    bot: G0T0Bot
    player: Player
    active_character: PlayerCharacter = None
    active_channel: discord.TextChannel = None

    async def commit(self):
        await self.active_character.upsert()
        self.player = await self.bot.get_player(self.player.id, self.player.guild.id)

    async def get_content(self) -> Mapping:
        embed = CharacterEmbed(
            self.player,
            self.active_character,
            title=f"Settings for {self.player.member.display_name}",
            description=(
                f"**Character**: {self.active_character.name}{f' (*{self.active_character.nickname}*)' if self.active_character.nickname else ''}\n"
                f"**Faction**: {self.active_character.faction.value if self.active_character.faction else '*None*'}\n"
                f"**Global Character**: {'True' if self.active_character.primary_character else 'False'}"
            ),
        )
        if self.player.guild.calendar and self.active_character.dob:
            embed.description += (
                f"\n**Birthday**: {self.active_character.formatted_dob(self.player.guild)}\n"
                f"**Age**: {self.active_character.age(self.player.guild)}"
            )

        embed.add_field(
            name="Active RP Channels",
            value="\n".join(
                [
                    self.player.member.guild.get_channel(c).mention
                    for c in self.active_character.channels
                    if self.player.member.guild.get_channel(c)
                ]
            ),
        )

        return {"embed": embed, "content": ""}


class CharacterSettingsUI(CharacterSettings):
    """
    A user interface class for managing character settings in a bot application.
    Methods
    -------
    new(cls, bot, owner, player: Player):
        Creates a new instance of CharacterSettingsUI.
    async _before_send(self):
        Prepares the character selection options and updates the state of channel buttons before sending the UI.
    async character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        Handles character selection from the dropdown and refreshes the UI content.
    async character_channel(self, chan: discord.ui.Select, interaction: discord.Interaction):
        Handles channel selection for the active character and updates the character's channel list.
    async add_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        Adds the active channel to the active character's channel list and refreshes the UI content.
    async remove_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        Removes the active channel from the active character's channel list and refreshes the UI content.
    async remove_all_channels(self, _: discord.ui.Button, interaction: discord.Interaction):
        Removes all channels from the active character's channel list and refreshes the UI content.
    async set_default(self, _: discord.ui.Button, interaction: discord.Interaction):
        Sets the active character as the default character and refreshes the UI content.
    async more_settings(self, _: discord.ui.Button, interaction: discord.Interaction):
        Defers to another settings UI for additional settings.
    async exit(self, *_):
        Exits the UI and handles timeout.
    """

    @classmethod
    def new(cls, bot, owner, player: Player):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        inst.active_character = (
            player.get_primary_character()
            if player.get_primary_character()
            else player.characters[0] if len(player.characters) > 0 else None
        )
        return inst

    async def _before_send(self):
        char_list = []

        for char in self.player.characters:
            char_list.append(
                discord.SelectOption(
                    label=f"{char.name}",
                    value=f"{char.id}",
                    default=True if char.id == self.active_character.id else False,
                )
            )
        self.character_select.options = char_list

        self.add_channel.disabled = False if self.active_channel else True
        self.remove_channel.disabled = False if self.active_channel else True

    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        self.active_character = next(
            (c for c in self.player.characters if c.id == int(char.values[0])), None
        )
        await self.refresh_content(interaction)

    @discord.ui.channel_select(
        channel_types=[discord.ChannelType(0)],
        placeholder="Select Channel to use character in",
        row=2,
    )
    async def character_channel(
        self, chan: discord.ui.Select, interaction: discord.Interaction
    ):
        channel = chan.values[0]
        self.active_channel = channel
        for char in self.player.characters:
            if channel.id in char.channels:
                char.channels.remove(channel.id)
                await char.upsert()

        if channel.id not in self.active_character.channels:
            self.active_character.channels.append(channel.id)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Channel", style=discord.ButtonStyle.primary, row=3)
    async def add_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        for char in self.player.characters:
            if self.active_channel.id in char.channels:
                char.channels.remove(self.active_channel.id)
                await char.upsert()

            if self.active_channel.id not in self.active_character.channels:
                self.active_character.channels.append(self.active_channel.id)

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Remove Channel", style=discord.ButtonStyle.secondary, row=3
    )
    async def remove_channel(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.active_channel.id in self.active_character.channels:
            self.active_character.channels.remove(self.active_channel.id)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove All", style=discord.ButtonStyle.danger, row=3)
    async def remove_all_channels(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        self.active_character.channels = []
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Toggle Default Character", style=discord.ButtonStyle.primary, row=4
    )
    async def set_default(self, _: discord.ui.Button, interaction: discord.Interaction):
        for char in self.player.characters:
            if char.primary_character:
                char.primary_character = False
                await char.upsert()

        self.active_character.primary_character = True
        await self.refresh_content(interaction)

    @discord.ui.button(label="More Settings", style=discord.ButtonStyle.primary, row=4)
    async def more_settings(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_CharacterSettings2UI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=4)
    async def exit(self, *_):
        await self.on_timeout()


class _CharacterSettings2UI(CharacterSettings):
    async def _before_send(self):
        faction_list = []
        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(
                discord.SelectOption(
                    label=f"{faction.value}",
                    value=f"{faction.id}",
                    default=(
                        True if self.active_character.faction == faction.id else False
                    ),
                )
            )

        if len(faction_list) > 0:
            self.faction_select.options = faction_list
        else:
            self.remove_item(self.faction_select)

        if not self.player.guild.calendar or self.active_character.dob:
            self.remove_item(self.update_dob)

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def faction_select(
        self, faction: discord.ui.Select, interaction: discord.Interaction
    ):
        self.active_character.faction = self.bot.compendium.get_object(
            Faction, int(faction.values[0])
        )
        await self.active_character.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Update Avatar", style=discord.ButtonStyle.primary, row=2)
    async def update_avatar(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = CharacterAvatarModal(self.bot, self.active_character)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Update Mention Name", style=discord.ButtonStyle.primary, row=2
    )
    async def update_nickname(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = CharacterNicknameModal(self.bot, self.active_character)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Set Birthday", style=discord.ButtonStyle.primary, row=2)
    async def update_dob(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterDOBModal(self.player, self.active_character)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterSettingsUI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()


class CharacterDOBModal(discord.ui.Modal):
    character: PlayerCharacter
    player: Player

    def __init__(self, player: Player, character: PlayerCharacter):
        super().__init__(title="Date of Birth")
        self.player = player
        self.character = character

        self.add_item(
            discord.ui.InputText(
                label="Age (years)",
                placeholder="Age (years)",
                max_length=5,
                value=(
                    self.character.age(self.player.guild) if self.character.dob else ""
                ),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Birth Month",
                placeholder="Birth Month",
                max_length=50,
                value=(
                    self.character.dob_month(self.player.guild).display_name
                    if self.character.dob
                    else ""
                ),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Birth Day",
                placeholder="Birth Day",
                max_length=3,
                value=(
                    self.character.dob_day(self.player.guild)
                    if self.character.dob
                    else ""
                ),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        month = next(
            (
                month
                for month in self.player.guild.calendar
                if month.display_name.lower() == self.children[1].value.lower()
            ),
            None,
        )

        if month:
            try:
                self.character.dob = self.player.guild.get_internal_date(
                    int(self.children[2].value),
                    self.player.guild.calendar.index(month) + 1,
                    self.player.guild.server_year - int(self.children[0].value),
                )
                await self.character.upsert()
            except:
                await interaction.channel.send(
                    embed=ErrorEmbed(f"Error setting birth date"), delete_after=5
                )

        await interaction.response.defer()
        self.stop()


class CharacterAvatarModal(discord.ui.Modal):
    bot: G0T0Bot
    character: PlayerCharacter

    def __init__(self, bot: G0T0Bot, character: PlayerCharacter):
        super().__init__(title="Set Character Avatar")
        self.bot = bot
        self.character = character

        self.add_item(
            discord.ui.InputText(
                label="Avatar Image URL",
                placeholder="",
                value=character.avatar_url,
                required=False,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.character.avatar_url = self.children[0].value
        await self.character.upsert()

        await interaction.response.defer()
        self.stop()


class CharacterNicknameModal(discord.ui.Modal):
    bot: G0T0Bot
    character: PlayerCharacter

    def __init__(self, bot: G0T0Bot, character: PlayerCharacter):
        super().__init__(title="Set Character Mention Name")
        self.bot = bot
        self.character = character

        self.add_item(
            discord.ui.InputText(
                label="Mention Name",
                placeholder="",
                value=character.nickname,
                required=False,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.character.nickname = self.children[0].value
        await self.character.upsert()

        await interaction.response.defer()
        self.stop()


# Character Get View
class CharacterGet(InteractiveView):
    """
    CharacterGet is an interactive view that displays character information.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to copy when creating a new menu instance.
        bot (G0T0Bot): The bot instance.
        player (Player): The player instance.
        active_character (PlayerCharacter, optional): The currently active character. Defaults to None.
    Methods:
        get_content() -> Mapping:
            Asynchronously retrieves the content to be displayed in the view.
            Returns a dictionary with the content and embed.
        on_timeout() -> None:
            Asynchronously handles the timeout event by editing the message to display the player overview embed.
    """

    __menu_copy_attrs__ = ("bot", "player", "active_character")

    bot: G0T0Bot
    player: Player
    active_character: PlayerCharacter = None

    async def get_content(self) -> Mapping:
        if self.active_character:
            embed = CharacterViewEmbed(self.player, self.active_character)
        else:
            embed = PlayerOverviewEmbed(self.player, self.bot.compendium)

        return {"content": "", "embed": embed}

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(
                view=None, embed=PlayerOverviewEmbed(self.player, self.bot.compendium)
            )
        except discord.HTTPException:
            pass


class CharacterGetUI(CharacterGet):
    """
    CharacterGetUI is a subclass of CharacterGet that provides a user interface for character selection and management.
    Methods:
        new(cls, bot, owner, player: Player) -> CharacterGetUI:
            Class method to create a new instance of CharacterGetUI with the specified bot, owner, and player.
        async _before_send(self):
            Prepares the character selection options before sending the UI. It creates a list of discord.SelectOption objects
            representing the player's characters and sets the default selection based on the active character.
        async character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
            Handles the character selection event. It updates the active character based on the selected value and
            refreshes the UI content.
    """

    @classmethod
    def new(cls, bot, owner, player: Player):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        return inst

    async def _before_send(self):
        char_list = [
            discord.SelectOption(
                label="Player Overview",
                default=False if self.active_character else True,
                value="def",
            )
        ]

        for char in self.player.characters:
            char_list.append(
                discord.SelectOption(
                    label=f"{char.name}",
                    value=f"{char.id}",
                    default=(
                        True
                        if self.active_character and char.id == self.active_character.id
                        else False
                    ),
                )
            )
        self.character_select.options = char_list

    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        try:
            self.active_character = next(
                (c for c in self.player.characters if c.id == int(char.values[0])), None
            )
        except:
            self.active_character = None

        await self.refresh_content(interaction)


# Character RP Post Request View
class RPPostView(InteractiveView):
    """
    RPPostView class that inherits from InteractiveView.
    Attributes:
        bot (G0T0Bot): The bot instance.
        player (Player): The player instance.
        posts (list[RPPost]): A list of RPPost instances.
        orig_message (discord.Message): The original message instance.
    Methods:
        get_content():
            Asynchronously retrieves the content for the view.
            Returns a dictionary with an empty content string and an RPPostEmbed instance.
    """

    __menu_copy_attrs__ = ("bot", "player", "posts", "message")

    bot: G0T0Bot
    player: Player
    posts: list[RPPost] = []
    orig_message: discord.Message = None

    async def get_content(self):
        return {"content": "", "embed": RPPostEmbed(self.player, self.posts)}


class RPPostUI(RPPostView):
    """
    A class to represent the UI for creating and managing role-playing posts.
    Attributes
    ----------
    character : PlayerCharacter
        The currently selected character for the post.
    bot : G0T0Bot
        The bot instance.
    player : Player
        The player creating the post.
    orig_message : discord.Message
        The original message being edited, if any.
    posts : list
        A list of RPPost instances representing the posts.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: discord.Member, player: Player, orig_message: discord.Message = None):
        Creates a new instance of RPPostUI.
    async _before_send(self):
        Prepares the UI elements before sending the message.
    async character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        Handles the character selection from the dropdown.
    async queue_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        Sets up a post for the selected character.
    async remove_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        Removes the selected character's post.
    async next_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        Submits the RP post.
    async exit_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        Exits the application.
    async _build_rp_post(self) -> bool:
        Builds and sends the RP post using a webhook.
    """

    character: PlayerCharacter = None

    @classmethod
    def new(cls, bot: G0T0Bot, player: Player, orig_message: discord.Message = None):
        inst = cls(owner=player.member)
        inst.bot = bot
        inst.player = player
        inst.orig_message = orig_message
        inst.posts = []

        if orig_message:
            for field in orig_message.embeds[0].fields:
                if c := next(
                    (c for c in player.characters if c.name == field.name), None
                ):
                    inst.posts.append(RPPost(c, note=field.value))
        return inst

    async def _before_send(self):
        char_list = []
        for char in self.player.characters:
            char_list.append(
                discord.SelectOption(
                    label=f"{char.name}",
                    value=f"{char.id}",
                    default=(
                        True
                        if self.character and char.id == self.character.id
                        else False
                    ),
                )
            )
        self.character_select.options = char_list

        self.queue_character.disabled = False if self.character else True
        self.character_select.disabled = False if len(self.posts) < 3 else True
        self.remove_character.disabled = (
            False
            if self.character
            and next(
                (p for p in self.posts if p.character.id == self.character.id), None
            )
            else True
        )

    @discord.ui.select(
        placeholder="Select a character", row=1, custom_id="character_select"
    )
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        character = await self.bot.get_character(char.values[0])

        if (
            character.player_id != interaction.user.id
            and interaction.user.id != self.owner.id
        ):
            raise G0T0Error("Thats not your character")

        self.character = character

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Setup Post",
        style=discord.ButtonStyle.primary,
        custom_id="add_character",
        row=2,
    )
    async def queue_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        post = next(
            (p for p in self.posts if p.character.id == self.character.id),
            RPPost(self.character),
        )
        modal = RPPostNoteModal(post)
        await self.prompt_modal(interaction, modal)

        if post.character not in [p.character for p in self.posts]:
            self.posts.append(post)

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Remove",
        style=discord.ButtonStyle.red,
        custom_id="remove_character",
        row=2,
    )
    async def remove_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if post := next(
            (p for p in self.posts if p.character.id == self.character.id), None
        ):
            self.posts.remove(post)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary, row=3)
    async def next_application(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if await self._build_rp_post():
            await interaction.respond("Request Submitted!", ephemeral=True)
        else:
            await interaction.channel.send(
                "Something went wrong posting. Your message may be too long. Shorten it up an try it again.",
                delete_after=5,
            )

        await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=3)
    async def exit_application(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.on_timeout()

    async def _build_rp_post(self) -> bool:
        if self.player.guild.rp_post_channel:
            try:
                webhook = await get_webhook(self.player.guild.rp_post_channel)
                if self.orig_message:
                    await webhook.edit_message(
                        self.orig_message.id, embed=RPPostEmbed(self.player, self.posts)
                    )
                else:
                    await webhook.send(
                        username=self.player.member.display_name,
                        avatar_url=self.player.member.display_avatar.url,
                        embed=RPPostEmbed(self.player, self.posts),
                    )
            except:
                return False
            return True
        return False


class RPPostNoteModal(discord.ui.Modal):
    """
    A modal dialog for adding or editing a note on an RPPost.
    Attributes:
        post (RPPost): The post to which the note is being added or edited.
    Methods:
        __init__(post: RPPost):
            Initializes the modal with the given post and adds an input field for the note.
        callback(interaction: discord.Interaction):
            Handles the interaction when the modal is submitted, updates the post's note, and stops the modal.
    """

    post: RPPost

    def __init__(self, post: RPPost):
        super().__init__(title="Post Note")
        self.post = post

        self.add_item(
            discord.ui.InputText(
                label="Note",
                placeholder="",
                value=self.post.note or "",
                required=False,
                style=discord.InputTextStyle.long,
                max_length=1000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        note = self.children[0].value

        self.post.note = note

        await interaction.response.defer()
        self.stop()
