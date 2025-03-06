from typing import Mapping

import discord

from Resolute.helpers import get_webhook
from Resolute.models.embeds.applications import NewCharacterRequestEmbed
from Resolute.models.objects.applications import (
    LevelUpApplication,
    NewCharacterApplication,
    PlayerApplication,
)
from Resolute.models.objects.enum import ApplicationType
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class CharacterView(InteractiveView):
    """
    CharacterView class that inherits from InteractiveView.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple of attribute names to be copied in the menu.
        bot (G0T0Bot): Instance of the bot.
        player (Player): Instance of the player.
        character (PlayerCharacter): Instance of the player's character.
        guild (PlayerGuild): Instance of the player's guild.
        levelUp (bool): Flag indicating if the character is leveling up.
        editOnly (bool): Flag indicating if the view is in edit-only mode.
        application (NewCharacterApplication|LevelUpApplication): Instance of the character application, either new or level-up.
    """

    __menu_copy_attrs__ = ("player", "application")
    player: Player
    application: PlayerApplication

    async def commit(self):
        if not self.application.edit:
            await self.application.delete()
            await self.application.insert()


class CharacterSelectUI(CharacterView):
    """
    A UI class for character selection and application management in a bot.
    Methods
    -------
    new(cls, bot, owner, player, levelUp=False, application=None, editOnly=False)
        Creates a new instance of CharacterSelectUI.
    application_select(type: discord.ui.Select, interaction: discord.Interaction)
        Handles the selection of an application type.
    character_select(char: discord.ui.Select, interaction: discord.Interaction)
        Handles the selection of a character to manage.
    application_edit(_: discord.ui.Button, interaction: discord.Interaction)
        Handles the editing of an application.
    application_create(_: discord.ui.Button, interaction: discord.Interaction)
        Handles the creation of a new application.
    exit(*_)
        Handles the exit action.
    _before_send()
        Prepares the UI before sending it to the user.
    get_content() -> Mapping
        Returns the content to be displayed in the UI.
    """

    @classmethod
    def new(cls, application: PlayerApplication, player: Player):
        inst = cls(owner=application.owner)
        inst.player = player
        inst.application = application
        inst.application.application.character = (
            player.characters[0]
            if not application.application.character
            or application.application.character.active == False
            else next(
                (
                    c
                    for c in player.characters
                    if c.id == application.application.character.id
                ),
                None,
            )
        )
        return inst

    @discord.ui.select(
        placeholder="Select an appliation type", custom_id="type_select", row=1
    )
    async def application_select(
        self, type: discord.ui.Select, interaction: discord.Interaction
    ):
        self.application.application.type = ApplicationType[type.values[0]]

        if self.application.application.type == ApplicationType.new:
            self.remove_item(self.character_select)
        else:
            if not self.get_item("char_select"):
                self.add_item(self.character_select)

        await self.refresh_content(interaction)

    @discord.ui.select(
        placeholder="Select a character to manage", custom_id="char_select", row=2
    )
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        self.application.application.character = self.player.characters[
            int(char.values[0])
        ]
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Edit Application", style=discord.ButtonStyle.primary, row=3
    )
    async def application_edit(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.application.application.type == ApplicationType.level:
            modal = LevelUpRequestModal(self.player.guild, self.application.application)
            await self.prompt_modal(interaction, modal)
            await self.on_timeout()
        else:
            await self.defer_to(NewCharacterRequestUI, interaction)

    @discord.ui.button(
        label="New Application", style=discord.ButtonStyle.primary, row=3
    )
    async def application_create(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.application.application.type == ApplicationType.level:
            if (
                self.application.application.character.level
                >= self.player.guild.max_level
            ):
                raise G0T0Error("Character is already at max level for the server")
            else:
                modal = LevelUpRequestModal(
                    self.player.guild, self.application.application
                )
                await self.prompt_modal(interaction, modal)
                await self.on_timeout()
        else:
            self.application.application = NewCharacterApplication(
                type=self.application.application.type,
                character=(
                    self.application.application.character
                    if self.application.application.type
                    in [ApplicationType.death, ApplicationType.freeroll]
                    else None
                ),
            )
            await self.defer_to(NewCharacterRequestUI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        char_list = []
        type_list = [
            discord.SelectOption(
                label=f"{ApplicationType.new.value}",
                value=f"{ApplicationType.new.name}",
                default=(
                    True
                    if self.application.application.type == ApplicationType.new
                    else False
                ),
            )
        ]
        if self.player.characters:
            for char in self.player.characters:
                char_list.append(
                    discord.SelectOption(
                        label=f"{char.name}",
                        value=f"{self.player.characters.index(char)}",
                        default=(
                            True
                            if self.application.application.character
                            and self.player.characters.index(char)
                            == self.player.characters.index(
                                self.application.application.character
                            )
                            else False
                        ),
                    )
                )

            for type in ApplicationType:
                if type not in [ApplicationType.new, ApplicationType.level]:
                    type_list.append(
                        discord.SelectOption(
                            label=f"{type.value}",
                            value=f"{type.name}",
                            default=(
                                True
                                if self.application.application.type == type
                                else False
                            ),
                        )
                    )
        else:
            char_list.append(discord.SelectOption(label="Blank Character", value="0"))
            self.remove_item(self.application_select)
            self.remove_item(self.character_select)

        if self.application.application.type == ApplicationType.level:
            if self.get_item("type_select"):
                self.remove_item(self.application_select)
        elif (
            self.get_item("char_select")
            and self.application.application.type == ApplicationType.new
        ):
            self.remove_item(self.character_select)

        if not self.application.edit and not self.application.cached:
            self.remove_item(self.application_edit)

        if self.application.edit:
            self.remove_item(self.application_create)

        self.application_select.options = type_list
        self.character_select.options = char_list

    async def get_content(self) -> Mapping:
        if self.application.application.type == ApplicationType.level:
            str = "Select a character to level up:\n"
        elif self.application.application.type == ApplicationType.new:
            str = "Select an application type:\n"
        else:
            str = "Select a character to reroll:\n"

        return {"embed": None, "content": str}


class NewCharacterRequestUI(CharacterView):
    """
    A user interface class for handling new character requests in a Discord bot application.
    Methods
    -------
    new(cls, bot, owner, player, levelUp: bool = False, application: NewCharacterApplication = None):
        Class method to create a new instance of NewCharacterRequestUI.
    base_scores(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Base Scores" button interaction.
    char(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Class/Species/Background" button interaction.
    misc(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Misc." button interaction.
    submit(self, _: discord.ui.Button, interaction: discord.Interaction):
        Handles the "Submit" button interaction, submitting the character application.
    exit(self, *_):
        Handles the "Exit" button interaction, exiting the interface.
    _before_send(self):
        Prepares the interface before sending, enabling or disabling the submit button based on application status.
    commit(self):
        Commits the application data to the database.
    get_content(self) -> Mapping:
        Returns the content to be displayed in the interface.
    """

    @classmethod
    def new(cls, application: PlayerApplication, player: Player):
        inst = cls(owner=application.owner)
        inst.player = player
        inst.application = application
        return inst

    @discord.ui.button(label="Base Scores", style=discord.ButtonStyle.primary, row=1)
    async def base_scores(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_BaseScoresUI, interaction)

    @discord.ui.button(
        label="Class/Species/Background", style=discord.ButtonStyle.primary, row=1
    )
    async def char(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_CharacterInformationUI, interaction)

    @discord.ui.button(label="Misc.", style=discord.ButtonStyle.primary, row=1)
    async def misc(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_MiscuUI, interaction)

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, row=2)
    async def submit(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.player.guild.staff_role and self.player.guild.application_channel:
            message = self.application.application.format_app(
                self.owner, self.player.guild.staff_role
            )
            webhook = await get_webhook(self.player.guild.application_channel)

            if len(message) > 2000:
                raise G0T0Error(
                    "Application too long, please shorten your response to a couple of questions and try to resubmit"
                )

            if self.application.application.message:
                await webhook.edit_message(
                    self.application.application.message.id, content=message
                )
                await interaction.response.send_message(
                    "Request Updated", ephemeral=True
                )
            else:
                msg = await webhook.send(
                    username=f"{self.owner.display_name}",
                    avatar_url=self.owner.avatar.url,
                    content=message,
                    wait=True,
                )
                thread = await msg.create_thread(
                    name=f"{self.application.application.name}",
                    auto_archive_duration=10080,
                )
                await thread.send(
                    f"""Need to make an edit? Use: `/edit_application` in this thread"""
                )
                await interaction.response.send_message(
                    "Request submitted!", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "Issue submitting request", ephemeral=True
            )
        await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=2)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if self.application.application.can_submit():
            self.submit.disabled = False
        else:
            self.submit.disabled = True

    async def get_content(self) -> Mapping:
        return {
            "embed": NewCharacterRequestEmbed(self.application.application),
            "content": "",
        }


class _MiscuUI(CharacterView):
    @discord.ui.button(label="Misc. 1", style=discord.ButtonStyle.primary, row=1)
    async def misc(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = MiscModal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Misc. 2", style=discord.ButtonStyle.primary, row=1)
    async def misc2(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = MiscModal2(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="HP/Level", style=discord.ButtonStyle.primary, row=1)
    async def hp_level(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = HPLevelModal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(NewCharacterRequestUI, interaction)

    async def get_content(self) -> Mapping:
        embed = discord.Embed(
            title=f"{self.application.application.type.value} Application"
        )
        embed.add_field(
            name="__Character Name__",
            value=self.application.application.name,
            inline=False,
        )

        embed.add_field(
            name="__Level__", value=self.application.application.level, inline=False
        )
        embed.add_field(
            name="__HP__", value=self.application.application.hp, inline=False
        )
        embed.add_field(
            name="__Starting Credits__",
            value=self.application.application.credits,
            inline=False,
        )
        embed.add_field(
            name="__Homeworld__",
            value=self.application.application.homeworld,
            inline=False,
        )
        embed.add_field(
            name="__Motivation for Joining__",
            value=self.application.application.join_motivation,
            inline=False,
        )
        embed.add_field(
            name="__Motivation for Good__",
            value=self.application.application.good_motivation,
            inline=False,
        )
        embed.add_field(
            name="__Character Sheet Link__",
            value=self.application.application.link,
            inline=False,
        )

        return {"embed": embed, "content": ""}


class _CharacterInformationUI(CharacterView):
    @discord.ui.button(label="Class", style=discord.ButtonStyle.primary, row=1)
    async def char_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ClassModal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Species", style=discord.ButtonStyle.primary, row=1)
    async def species(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = SpeciesModal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Background", style=discord.ButtonStyle.primary, row=1)
    async def background(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = BackgroundModal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(NewCharacterRequestUI, interaction)

    async def get_content(self) -> Mapping:
        embed = discord.Embed(
            title=f"{self.application.application.type.value} Application"
        )
        embed.add_field(
            name="__Class__",
            value=self.application.application.char_class.output(),
            inline=False,
        )
        embed.add_field(
            name="__Species__",
            value=self.application.application.species.output(),
            inline=False,
        )
        embed.add_field(
            name="__Background__",
            value=self.application.application.background.output(),
            inline=False,
        )

        return {"embed": embed, "content": ""}


class _BaseScoresUI(CharacterView):
    @discord.ui.button(label="STR/DEX/CON", style=discord.ButtonStyle.primary, row=1)
    async def base_scores_1(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = BaseScore1Modal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="INT/WIS/CHA", style=discord.ButtonStyle.primary, row=1)
    async def base_scores_2(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        modal = BaseScore2Modal(self.application.application)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(NewCharacterRequestUI, interaction)

    async def get_content(self) -> Mapping:
        embed = discord.Embed(
            title=f"{self.application.application.type.value} Application"
        )
        embed.add_field(
            name="__Base Scores__",
            value=self.application.application.base_scores.output(),
            inline=False,
        )

        return {"embed": embed, "content": ""}


class HPLevelModal(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="HP Rolls")
        self.application = application
        self.add_item(
            discord.ui.InputText(
                label="Character Level",
                placeholder="Character Level",
                value=self.application.level,
                required=False,
                max_length=2,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="HP", required=False, placeholder="HP", value=self.application.hp
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.level = self.children[0].value
        self.application.hp = self.children[1].value

        await interaction.response.defer()
        self.stop()


class MiscModal(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Misc. Information")
        self.application = application

        self.add_item(
            discord.ui.InputText(
                label="Character Name",
                placeholder="Character Name",
                value=self.application.name,
                max_length=2000,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Starting Credits",
                placeholder="Starting Credits",
                value=self.application.credits,
                max_length=150,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Homeworld",
                placeholder="Homeworld",
                value=self.application.homeworld,
                max_length=500,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Motivation for joining the Wardens of the Sky",
                style=discord.InputTextStyle.long,
                placeholder="Motivation",
                value=self.application.join_motivation,
                max_length=1000,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Motivation for doing good?",
                style=discord.InputTextStyle.long,
                placeholder="Motivation",
                value=self.application.good_motivation,
                max_length=1000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.name = self.children[0].value
        self.application.credits = self.children[1].value
        self.application.homeworld = self.children[2].value
        self.application.join_motivation = self.children[3].value
        self.application.good_motivation = self.children[4].value

        await interaction.response.defer()
        self.stop()


class MiscModal2(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Misc. Information")
        self.application = application

        self.add_item(
            discord.ui.InputText(
                label="Character Sheet Link",
                placeholder="Character Sheet Link",
                value=self.application.link,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.link = self.children[0].value

        await interaction.response.defer()
        self.stop()


class BackgroundModal(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Background Information")
        self.application = application

        self.add_item(
            discord.ui.InputText(
                label="Background",
                placeholder="Background",
                value=self.application.background.background,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Skills",
                placeholder="Skills",
                value=self.application.background.skills,
                max_length=500,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Tools/Languages",
                placeholder="Tools/Languages",
                value=self.application.background.tools,
                max_length=500,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Feat",
                placeholder="Feat",
                value=self.application.background.feat,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Equipment",
                placeholder="Equipment",
                value=self.application.background.equipment,
                max_length=1000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.background.background = self.children[0].value
        self.application.background.skills = self.children[1].value
        self.application.background.tools = self.children[2].value
        self.application.background.feat = self.children[3].value
        self.application.background.equipment = self.children[4].value

        await interaction.response.defer()
        self.stop()


class SpeciesModal(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Species Information")
        self.application = application

        self.add_item(
            discord.ui.InputText(
                label="Species",
                placeholder="Species",
                value=self.application.species.species,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Ability Score Increase",
                placeholder="Abilisty Score Increase",
                value=self.application.species.asi,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Features",
                placeholder="Features",
                value=self.application.species.feats,
                max_length=1000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.species.species = self.children[0].value
        self.application.species.asi = self.children[1].value
        self.application.species.feats = self.children[2].value

        await interaction.response.defer()
        self.stop()


class ClassModal(discord.ui.Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Class Information")
        self.application = application

        self.add_item(
            discord.ui.InputText(
                label="Class",
                placeholder="Class",
                value=self.application.char_class.char_class,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Skills",
                placeholder="Skills",
                value=self.application.char_class.skills,
                max_length=500,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Features",
                placeholder="Features",
                value=self.application.char_class.feats,
                max_length=100,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Equipment",
                placeholder="Equipment",
                value=self.application.char_class.equipment,
                max_length=1000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.application.char_class.char_class = self.children[0].value
        self.application.char_class.skills = self.children[1].value
        self.application.char_class.feats = self.children[2].value
        self.application.char_class.equipment = self.children[3].value

        await interaction.response.defer()
        self.stop()


class BaseScore1Modal(discord.ui.Modal):
    appliation: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Base Scores")
        self.appliation = application

        self.add_item(
            discord.ui.InputText(
                label="Strength",
                placeholder="Strength",
                value=self.appliation.base_scores.str,
                max_length=5,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Dexterity",
                placeholder="Dexterity",
                value=self.appliation.base_scores.dex,
                max_length=5,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Constitution",
                placeholder="Constitution",
                value=self.appliation.base_scores.con,
                max_length=5,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.appliation.base_scores.str = self.children[0].value
        self.appliation.base_scores.dex = self.children[1].value
        self.appliation.base_scores.con = self.children[2].value

        await interaction.response.defer()

        self.stop()


class BaseScore2Modal(discord.ui.Modal):
    appliation: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Base Scores")
        self.appliation = application

        self.add_item(
            discord.ui.InputText(
                label="Intelligence",
                placeholder="Intelligence",
                value=self.appliation.base_scores.int,
                max_length=5,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Wisdom",
                placeholder="Wisdom",
                value=self.appliation.base_scores.wis,
                max_length=5,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Charisma",
                placeholder="Charisma",
                value=self.appliation.base_scores.cha,
                max_length=5,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.appliation.base_scores.int = self.children[0].value
        self.appliation.base_scores.wis = self.children[1].value
        self.appliation.base_scores.cha = self.children[2].value

        await interaction.response.defer()
        self.stop()


class LevelUpRequestModal(discord.ui.Modal):
    """
    A modal for submitting or updating a level-up request for a character in a player guild.
    Attributes:
        application (LevelUpApplication): The level-up application associated with the request.
        guild (PlayerGuild): The player guild to which the request is being submitted.
    Methods:
        __init__(guild: PlayerGuild, application: LevelUpApplication = None):
            Initializes the modal with the given guild and application.
        callback(interaction: discord.Interaction):
            Handles the submission of the modal, updating or creating a level-up request message in the guild's application channel.
    """

    application: LevelUpApplication
    guild: PlayerGuild

    def __init__(self, guild: PlayerGuild, application: LevelUpApplication = None):
        super().__init__(title=f"Level Up Request")
        self.application = application
        self.guild = guild

        self.add_item(
            discord.ui.InputText(
                label="Level",
                placeholder=f"Level",
                max_length=3,
                value=self.application.level,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="HP", placeholder="HP", max_length=500, value=self.application.hp
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="New Features",
                style=discord.InputTextStyle.long,
                placeholder="New Features or NA",
                value=self.application.feats,
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Changes",
                style=discord.InputTextStyle.long,
                max_length=2000,
                placeholder="Changes or NA",
                value=self.application.changes,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Link",
                placeholder="Link to character sheet",
                max_length=500,
                value=self.application.link,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        if self.guild.staff_role and self.guild.application_channel:
            self.application.level = self.children[0].value
            self.application.hp = self.children[1].value
            self.application.feats = self.children[2].value
            self.application.changes = self.children[3].value
            self.application.link = self.children[4].value

            message = self.application.format_app(
                interaction.user, self.guild.staff_role
            )
            webhook = await get_webhook(self.guild.application_channel)

            if self.application.message:
                await webhook.edit_message(self.application.message.id, content=message)
                return await interaction.response.send_message(
                    "Request updated!", ephemeral=True
                )
            else:
                msg = await webhook.send(
                    username=interaction.user.display_name,
                    avatar_url=interaction.user.avatar.url,
                    content=message,
                    wait=True,
                )
                thread = await msg.create_thread(
                    name=f"{self.application.character.name}",
                    auto_archive_duration=10080,
                )
                await thread.send(
                    f"""Need to make an edit? Use: `/edit_application` in this thread"""
                )
                await msg.edit(content=message)
                return await interaction.response.send_message(
                    "Request submitted!", ephemeral=True
                )
        return await interaction.response.send_message(
            "Issue submitting request", ephemeral=True
        )
