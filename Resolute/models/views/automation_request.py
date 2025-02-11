import discord

from Resolute.models.objects.guilds import PlayerGuild


class AutomationRequestView(discord.ui.Modal):
    """
    A view for handling automation requests within a guild.
    Attributes:
        guild (PlayerGuild): The guild associated with the automation request.
    Methods:
        __init__(guild: PlayerGuild):
            Initializes the AutomationRequestView with the given guild and adds input fields for the request.
        callback(interaction: discord.Interaction):
            Handles the submission of the automation request, creating a thread in the help channel with the request details.
    """

    guild: PlayerGuild

    def __init__(self, guild: PlayerGuild):
        super().__init__(title="Automation Request")
        self.guild = guild

        self.add_item(
            discord.ui.InputText(label="Request Summary", style=discord.InputTextStyle.short, required=True, custom_id="summary",
                      placeholder="Short description of request/issue", max_length=50))
        self.add_item(discord.ui.InputText(label="Notes", style=discord.InputTextStyle.long, required=False, custom_id="notes",
                                placeholder="Additional information/details", max_length=1000))
        self.add_item(discord.ui.InputText(label="Link", style=discord.InputTextStyle.short, required=False, custom_id="link",
                                placeholder="Link to issue/reference material", max_length=200))

    async def callback(self, interaction: discord.Interaction):
        if self.guild.help_channel:
            title = f'''{interaction.user.display_name}: {self.children[0].value}'''
            message = f'''**Request Title**: {self.children[0].value}\n\n**Requestor**: {interaction.user.mention}\n**Notes**: {self.children[1].value}\n**Reference  URL**: {self.children[2].value} '''

            thread = await self.guild.help_channel.create_thread(auto_archive_duration=10080,
                                                       name=title, type=discord.ChannelType.public_thread)
            await thread.send(content=message)
            return await interaction.response.send_message("Request submitted!", ephemeral=True)
        return await interaction.response.send_message("Issue submitting request", ephemeral=True)