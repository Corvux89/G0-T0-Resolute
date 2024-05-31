import discord

from discord import InputText
from discord.ui import Modal
from Resolute.models.objects.applications import LevelUpApplication
from Resolute.models.objects.characters import PlayerCharacter

class LevelUpRequestView(Modal):
    character = None
    application: LevelUpApplication = LevelUpApplication()

    def __init__(self, owner, character: PlayerCharacter = None, application: LevelUpApplication = LevelUpApplication()):
        super().__init__(title=f"Level Up Request")
        self.owner=owner
        self.character = character
        self.application = application

        self.add_item(InputText(label="Level", placeholder=f"Level", max_length=3, value=f"{self.application.level if self.application.level != '' else character.level +1}"))
        self.add_item(InputText(label="HP", placeholder="HP", max_length=500, value=self.application.hp))
        self.add_item(InputText(label="New Features", style=discord.InputTextStyle.long, placeholder="New Features or NA", value=self.application.feats))
        
        self.add_item(InputText(label="Changes", style=discord.InputTextStyle.long, required=True,
                                custom_id="changes", placeholder="Changes or NA", value=self.application.changes))
        self.add_item(InputText(label="Link", required=True, custom_id="link",
                                placeholder="Link to character sheet", value=self.application.link))

    async def callback(self, interaction: discord.Interaction):
        if (character_app_channel := discord.utils.get(interaction.guild.channels, name="character-apps")) and (
        arch_role := discord.utils.get(interaction.guild.roles, name="Archivist")):
            self.application.level = self.children[0].value
            self.application.hp = self.children[1].value
            self.application.feats = self.children[2].value
            self.application.changes = self.children[3].value
            self.application.link = self.children[4].value

            message = self.application.format_app(interaction.user, self.character, arch_role)

            if self.application.message:
                await self.application.message.edit(content=message)
                return await interaction.response.send_message("Request updated!", ephemeral=True)
            else:
                msg = await character_app_channel.send(content=message)
                thread = await msg.create_thread(name=f"{self.character.name}", auto_archive_duration=10080)
                await thread.send(f'''Need to make an edit? Use:\n''')
                await thread.send(f'''`/edit_application`''')
                await msg.edit(content=message)
                return await interaction.response.send_message("Request submitted!", ephemeral=True)
        return await interaction.response.send_message("Issue submitting request", ephemeral=True)