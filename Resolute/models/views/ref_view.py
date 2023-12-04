import discord
from discord import ChannelType
from discord.ui import InputText, Modal


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
            thread = await alias_channel.create_thread(auto_archive_duration=10080,
                                                               name=self.children[0].value, type=ChannelType.public_thread)
            message = f'''**Requestor**: {interaction.user.mention}\n**Notes**: {self.children[1].value}\n**Reference  URL**: {self.children[2].value} '''
            await thread.send(content=message)
            return await interaction.response.send_message("Request submitted!", ephemeral=True)
        return await interaction.response.send_message("Issue submitting request", ephemeral=True)
