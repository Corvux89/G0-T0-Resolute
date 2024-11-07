import discord

from discord import ApplicationCommandError
from discord.ext.commands import CommandError

# TODO: Replace ErrorEmbed with exceptions

# Aplication Command Errors
class G0T0Error(ApplicationCommandError):
    def __init__(self, message):
        super().__init__(f"{message}")

class CharacterNotFound(G0T0Error):
    def __init__(self, member: discord.Member):
        super().__init__(f"No character information found for {member.mention}")

class ApplicationNotFound(G0T0Error):
    def __init__(self):
        super().__init__("Application not found")

class AdventureNotFound(G0T0Error):
    def __init__(self):
        super().__init__("Adventure not found")

class RoleNotFound(G0T0Error):
    def __init__(self, role_name):
        super().__init__(f"Role @{role_name} doesn't exist")


# Command Errors
class G0T0CommandError(CommandError):
    def __init__(self, message):
        super().__init__(f"{message}")