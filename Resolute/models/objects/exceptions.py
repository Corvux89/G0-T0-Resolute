import discord
from discord.ext import commands


# Aplication Command Errors
class G0T0CommandError(commands.CommandError):
    def __init__(self, message):
        super().__init__(f"{message}")


class G0T0Error(discord.ApplicationCommandError):
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


class ArenaNotFound(G0T0Error):
    def __init__(self):
        super().__init__(
            f"There is no active arena in this channel. If you're a host you can use `/arena claim` to start a new arena"
        )


class ObjectNotFound(G0T0Error):
    def __init__(self):
        super().__init__(f"Object not found")


class ActivityNotFound(G0T0Error):
    def __init__(self, activity: str):
        super().__init__(f"Activity `{activity}` not found")


class LogNotFound(G0T0Error):
    def __init__(self, log: str = None):
        super().__init__(f"Log {f'`{log}`' if log else 'from message'} not found")


class InvalidCurrencySelection(G0T0Error):
    def __init__(self):
        super().__init__(f"Invalid Currency Selection")


class TransactionError(G0T0Error):
    def __init__(self, message):
        super().__init__(f"{message}")


class TimeoutError(G0T0Error):
    def __init__(self):
        super().__init__("Timed out waiting for a response or invalid response.")


class SelectionCancelled(G0T0Error):
    def __init__(self):
        super().__init__("Selection timed out or was cancelled.")


class DBError(G0T0Error):
    def __init__(self):
        super().__init__("Try again in a few seconds. I'm not quite awake yet")


class Unauthorized(G0T0Error):
    def __init__(self):
        super().__init__("You do not have access to do this.")
