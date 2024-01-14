from typing import Type, Mapping

import discord
from discord import ChannelType, Embed, User
from discord.ui import InputText, Modal

from Resolute.helpers import get_character
from Resolute.models.db_objects import PlayerCharacter, CharacterSpecies, CharacterArchetype, CharacterClass, \
    NewCharacterApplication


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

class BaseScoreView(Modal):
    application: NewCharacterApplication()
    def __init__(self, application:NewCharacterApplication):
        super().__init__(title="Base Scores")
        self.application = application

        self.add_item(InputText(label="Strength", style=discord.InputTextStyle.short, required=True, custom_id="str",
                                placeholder="Strength", value=self.application.base_scores.str))

    async def callback(self, interaction: discord.Interaction):
        self.application.base_scores.str = self.children[0].value
        await interaction.response.defer()
        self.stop()


# https://github.com/avrae/avrae/blob/master/ui/menu.py#L8
# https://github.com/avrae/avrae/blob/master/ui/charsettings.py#L23
class NewCharacterRequestView(discord.ui.View):
    bot = None
    character = None
    application = NewCharacterApplication()

    def __init__(self, owner: User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.message = None  # type: Optional[discord.Message]
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the owner of this application", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(view=None)
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
        await view.refresh_content(interaction)

    async def get_content(self) -> Mapping:
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(veiw=self, **content_kwargs, **kwargs)

    @staticmethod
    async def prompt_modal(interaction: discord.Interaction, modal):
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal.application

class NewCharacterRequestUI(NewCharacterRequestView):
    @classmethod
    def new(cls, bot, owner, name, character):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.character = character
        inst.application.name = name
        return inst

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=1)
    async def exit(self, *_):
        await self.on_timeout()

    @discord.ui.button(label="Edit Base Scores", style=discord.ButtonStyle.primary, row=1)
    async def edit_base_scores(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = BaseScoreView(self.application)

        self.application = await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)


    async def get_content(self):
        embed = Embed(title=f"New Character Application for {self.application.name}")
        embed.add_field(name="__Base Scores__",
                        value=(
                            f"STR: {self.application.base_scores.str}\n"
                            f"DEX: {self.application.base_scores.dex}\n"
                            f"CON: {self.application.base_scores.con}\n"
                            f"INT: {self.application.base_scores.int}\n"
                            f"WIS: {self.application.base_scores.wis}\n"
                            f"CHA: {self.application.base_scores.cha}\n"
                        ),
                        inline=False)

        return {"embed": embed}

