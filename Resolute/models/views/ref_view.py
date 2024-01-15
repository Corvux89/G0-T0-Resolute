from typing import Type, Mapping

import discord
from discord import ChannelType, Embed, User
from discord.ui import InputText, Modal

from Resolute.helpers import get_character
from Resolute.models.db_objects import PlayerCharacter, CharacterSpecies, CharacterArchetype, CharacterClass, \
    NewCharacterApplication
from Resolute.bot import G0T0Bot


class AutomationRequestView(Modal):
    def __init__(self):
        super().__init__(title="Automation Request")

        self.add_item(
            InputText(label="Request Summary", style=discord.InputTextStyle.short, required=True, custom_id="summary",
                      placeholder="Short description of request/issue"))
        self.add_item(InputText(label="Notes", style=discord.InputTextStyle.long, required=False, custom_id="notes",
                                placeholder="Additional information/details"))
        self.add_item(InputText(label="Link", style=discord.InputTextStyle.short, required=False, custom_id="link",
                                placeholder="Link to issue/reference material"))

    async def callback(self, interaction: discord.Interaction):
        if alias_channel := discord.utils.get(interaction.guild.channels, name="aliasing-and-snippet-help"):
            title = f'''{interaction.user.display_name}: {self.children[0].value}'''
            message = f'''**Request Title**: {self.children[0].value}\n\n**Requestor**: {interaction.user.mention}\n**Notes**: {self.children[1].value}\n**Reference  URL**: {self.children[2].value} '''

            thread = await alias_channel.create_thread(auto_archive_duration=10080,
                                                       name=title[0:100], type=ChannelType.public_thread)
            await thread.send(content=message)
            return await interaction.response.send_message("Request submitted!", ephemeral=True)
        return await interaction.response.send_message("Issue submitting request", ephemeral=True)


class LevelUpRequestView(Modal):
    character = None

    def __init__(self, character: PlayerCharacter = None):
        super().__init__(title=f"Level Up Request")
        self.character = character

        self.add_item(InputText(label="Level", style=discord.InputTextStyle.short, required=True, custom_id="level",
                                placeholder=f"Level", value=f"{character.level + 1}"))
        self.add_item(InputText(label="HP", style=discord.InputTextStyle.short, required=True, custom_id="hp",
                                placeholder="HP"))
        self.add_item(InputText(label="New Features", style=discord.InputTextStyle.long, required=True,
                                custom_id="feats", placeholder="New Features or NA"))
        self.add_item(InputText(label="Changes", style=discord.InputTextStyle.long, required=True,
                                custom_id="changes", placeholder="Changes or NA"))
        self.add_item(InputText(label="Link", style=discord.InputTextStyle.short, required=True, custom_id="link",
                                placeholder="Link to character sheet"))

    async def callback(self, interaction: discord.Interaction):
        if (character_app_channel := discord.utils.get(interaction.guild.channels, name="character-apps")) and (
        arch_role := discord.utils.get(interaction.guild.roles, name="Archivist")):
            message = f'''**Level Up** | {arch_role.mention}\n'''
            message += f'''**Name:** {self.character.name}\n'''
            message += f'''**New Level:** {self.children[0].value}\n'''
            message += f'''**HP:** {self.children[1].value}\n'''
            message += f'''**New Features:** {self.children[2].value}\n'''
            message += f'''**Changes:** {self.children[3].value}\n'''
            message += f'''**Link:** {self.children[4].value}'''

            await character_app_channel.send(content=message)
            return await interaction.response.send_message("Request submitted!", ephemeral=True)
        return await interaction.response.send_message("Issue submitting request", ephemeral=True)

class BaseScoreView1(Modal):
    application: NewCharacterApplication
    def __init__(self, application:NewCharacterApplication):
        super().__init__(title="Base Scores")
        self.application = application

        self.add_item(InputText(label="Strength", style=discord.InputTextStyle.short, required=True, custom_id="str",
                                placeholder="Strength", value=self.application.base_scores.str))

        self.add_item(InputText(label="Dexterity", style=discord.InputTextStyle.short, required=True, custom_id="dex",
                                placeholder="Dexterity", value=self.application.base_scores.str))

        self.add_item(InputText(label="Constitution", style=discord.InputTextStyle.short, required=True, custom_id="con",
                                placeholder="Constitution", value=self.application.base_scores.con))

    async def callback(self, interaction: discord.Interaction):
        self.application.base_scores.str = self.children[0].value
        self.application.base_scores.dex = self.children[1].value
        self.application.base_scores.con = self.children[2].value
        await interaction.response.defer()
        self.stop()

class BaseScoreView2(Modal):
    application: NewCharacterApplication
    def __init__(self, application:NewCharacterApplication):
        super().__init__(title="Base Scores")
        self.application = application

        self.add_item(InputText(label="Intelligence", style=discord.InputTextStyle.short, required=True, custom_id="int",
                                placeholder="Intelligence", value=self.application.base_scores.int))

        self.add_item(InputText(label="Wisdom", style=discord.InputTextStyle.short, required=True, custom_id="wis",
                                placeholder="Wisdom", value=self.application.base_scores.wis))

        self.add_item(InputText(label="Charisma", style=discord.InputTextStyle.short, required=True, custom_id="con",
                                placeholder="Charisma", value=self.application.base_scores.cha))

    async def callback(self, interaction: discord.Interaction):
        self.application.base_scores.int = self.children[0].value
        self.application.base_scores.wis = self.children[1].value
        self.application.base_scores.cha = self.children[2].value
        await interaction.response.defer()
        self.stop()

class SpeciesView(Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Species Information")
        self.application = application

        self.add_item(InputText(label="Species", style=discord.InputTextStyle.short, required=True, custom_id="species",
                                placeholder="Species", value=self.application.species.species))

        self.add_item(InputText(label="Ability Score Increases", style=discord.InputTextStyle.short, required=True, custom_id="asi",
                                placeholder="ASIs", value=self.application.species.asi))

        self.add_item(InputText(label="Features", style=discord.InputTextStyle.long, required=True, custom_id="feats",
                                placeholder="Features", value=self.application.species.feats))

    async def callback(self, interaction: discord.Interaction):
        self.application.species.species = self.children[0].value
        self.application.species.asi = self.children[1].value
        self.application.species.feats = self.children[2].value
        await interaction.response.defer()
        self.stop()

class BackgroundView(Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Background Information")
        self.application = application

        self.add_item(InputText(label="Background", style=discord.InputTextStyle.short, required=True, custom_id="bkg",
                                placeholder="Background", value=self.application.background.background))

        self.add_item(InputText(label="Skills", style=discord.InputTextStyle.short, required=True, custom_id="skills",
                                placeholder="Skills", value=self.application.background.skills))

        self.add_item(InputText(label="Tools/Languages", style=discord.InputTextStyle.short, required=True, custom_id="tools",
                                placeholder="Tools/Languages", value=self.application.background.tools))

        self.add_item(InputText(label="Feat", style=discord.InputTextStyle.short, required=True, custom_id="feat",
                                placeholder="Feat", value=self.application.background.feat))

        self.add_item(InputText(label="Equipment", style=discord.InputTextStyle.short, required=True, custom_id="equip",
                                placeholder="Equipment", value=self.application.background.equipment))

    async def callback(self, interaction: discord.Interaction):
        self.application.background.background = self.children[0].value
        self.application.background.skills = self.children[1].value
        self.application.background.tools = self.children[2].value
        self.application.background.feat = self.children[3].value
        self.application.background.equipment = self.children[4].value
        await interaction.response.defer()
        self.stop()

class ClassView(Modal):
    application: NewCharacterApplication

    def __init__(self, application: NewCharacterApplication):
        super().__init__(title="Class Information")
        self.application = application

        self.add_item(InputText(label="Class", style=discord.InputTextStyle.short, required=True, custom_id="class",
                                placeholder="Class", value=self.application.char_class.char_class))

        self.add_item(InputText(label="Skills", style=discord.InputTextStyle.long, required=True, custom_id="skills",
                                placeholder="Skills", value=self.application.char_class.skills))

        self.add_item(InputText(label="Features", style=discord.InputTextStyle.long, required=True, custom_id="feats",
                                placeholder="Features", value=self.application.char_class.feats))

        self.add_item(InputText(label="Equipment", style=discord.InputTextStyle.long, required=True, custom_id="equip",
                                placeholder="Equipment", value=self.application.char_class.equipment))

    async def callback(self, interaction: discord.Interaction):
        self.application.char_class.char_class = self.children[0].value
        self.application.char_class.skills = self.children[1].value
        self.application.char_class.feats = self.children[2].value
        self.application.char_class.equipment = self.children[3].value
        await interaction.response.defer()
        self.stop()


# https://github.com/avrae/avrae/blob/master/ui/menu.py#L8
# https://github.com/avrae/avrae/blob/master/ui/charsettings.py#L23
class NewCharacterRequestView(discord.ui.View):
    __menu_copy_attrs__ = ("character", "bot", "application")
    bot: G0T0Bot
    character: PlayerCharacter = None
    application: NewCharacterApplication = NewCharacterApplication()

    def __init__(self, owner: User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.message = None  # type: Optional[discord.Message]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the owner of this application", ephemeral=True)
        return False

    @classmethod
    def from_menu(cls, other: "MenuBase"):
        inst = cls(owner=other.owner)
        inst.message = other.message
        for attr in cls.__menu_copy_attrs__:
            # copy the instance attr to the new instance if available, or fall back to the class default
            sentinel = object()
            value = getattr(other, attr, sentinel)
            if value is sentinel:
                value = getattr(cls, attr, None)
            setattr(inst, attr, value)
        return inst

    async def before_send(self):
        pass

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(view=None)
            await self.message.delete()
        except discord.HTTPException:
            pass

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["MenuBase"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view.before_send()
        await view.refresh_content(interaction)

    async def get_content(self) -> Mapping:
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)

    @staticmethod
    async def prompt_modal(interaction: discord.Interaction, modal):
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal.application

# Base Scores, Class/Species/Background, Misc., Review, Exit
class NewCharacterRequestUI(NewCharacterRequestView):
    @classmethod
    def new(cls, bot, owner, name, character, freeroll):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.character = character
        inst.application.name = name
        inst.application.freeroll = freeroll
        return inst

    @discord.ui.button(label="Base Scores", style=discord.ButtonStyle.primary, row=1)
    async def base_scores(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_BaseScoresUI, interaction)

    @discord.ui.button(label="Class/Species/Background", style=discord.ButtonStyle.primary, row=1)
    async def character(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_CharacterUI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=1)
    async def exit(self, *_):
        await self.on_timeout()

    async def get_content(self):
        embed = Embed(title=f"{'Free Reroll' if self.application.freeroll else 'Reroll' if self.character else 'New Character'} Application for {self.application.name}")
        embed.add_field(name="__Base Scores__",
                        value=f"{self.application.base_scores.status()}",
                        inline=False)

        embed.add_field(name="__Species__",
                        value=f"{self.application.species.status()}",
                        inline=False)

        return {"embed": embed}

class _BaseScoresUI(NewCharacterRequestView):
    @discord.ui.button(label="STR/DEX/CON", style=discord.ButtonStyle.primary, row=1)
    async def edit_base_scores_1(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = BaseScoreView1(self.application)
        self.application = await  self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="INT/WIS/CHA", style=discord.ButtonStyle.primary, row=1)
    async def edit_base_scores_2(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = BaseScoreView2(self.application)
        self.application = await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(NewCharacterRequestUI, interaction)

    async def get_content(self):
        embed = Embed(
            title=f"{'Free Reroll' if self.application.freeroll else 'Reroll' if self.character else 'New Character'} Application for {self.application.name}")
        embed.add_field(name="__Base Scores__",
                        value=self.application.base_scores.output(),
                        inline=False)

        return {"embed": embed}

class _CharacterUI(NewCharacterRequestView):
    @discord.ui.button(label="Class", style=discord.ButtonStyle.primary, row=1)
    async def char_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ClassView(application=self.application)
        self.application = await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Species", style=discord.ButtonStyle.primary, row=1)
    async def species(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = SpeciesView(application=self.application)
        self.application = await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Background", style=discord.ButtonStyle.primary, row=1)
    async def background(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = BackgroundView(application=self.application)
        self.application = await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(NewCharacterRequestUI, interaction)

    async def get_content(self):
        embed = Embed(
            title=f"{'Free Reroll' if self.application.freeroll else 'Reroll' if self.character else 'New Character'} Application for {self.application.name}")

        embed.add_field(name="__Class__",
                        value=f"{self.application.char_class.output()}",
                        inline=False)

        embed.add_field(name="__Species__",
                        value=f"{self.application.species.output()}",
                        inline=False)

        return {"embed": embed}