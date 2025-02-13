import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI, DENIED_EMOJI
from Resolute.helpers.general_helpers import try_delete
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.bot import G0T0Context
from Resolute.models.objects.enum import ApplicationType, WebhookType
from Resolute.models.objects.applications import PlayerApplication
from Resolute.models.objects.exceptions import (ApplicationNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.objects.webhook import G0T0Webhook
from Resolute.models.views.applications import (CharacterSelectUI,
                                                LevelUpRequestModal, NewCharacterRequestUI)
from Resolute.models.views.character_view import (CharacterGetUI,
                                                  CharacterManageUI,
                                                  CharacterSettingsUI,
                                                  RPPostUI)

log = logging.getLogger(__name__)

# TODO: Add Character Birthday for server date

def setup(bot: G0T0Bot):
    bot.add_cog(Character(bot))


class Character(commands.Cog):
    """
    Cog for handling character-related commands and interactions.
    Attributes:
        bot (G0T0Bot): The bot instance.
        character_admin_commands (discord.SlashCommandGroup): Group of character administration commands.
    Methods:
        __init__(bot):
            Initializes the Character cog with the given bot instance.
        character_say(ctx: discord.ApplicationContext):
            Command for making a character say something in the chat.
        character_manage(ctx: discord.ApplicationContext, member: discord.Option):
            Command for managing a player's character(s).
        character_get(ctx: discord.ApplicationContext, member: discord.Option):
            Command for displaying character information for a player's character.
        character_settings(ctx: discord.ApplicationContext):
            Command for accessing character settings.
        rp_request(ctx: discord.ApplicationContext):
            Command for making an RP board request.
        character_level_request(ctx: discord.ApplicationContext):
            Command for making a level request for a character.
        new_character_request(ctx: discord.ApplicationContext):
            Command for making a new character request.
        edit_application(ctx: discord.ApplicationContext, application_id: discord.Option):
            Command for editing an application.
    """
    bot: G0T0Bot
    character_admin_commands = discord.SlashCommandGroup("character_admin", "Character administration commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Characters\' loaded')    

    @commands.command(
        name="say",
        guild_only=True
    )
    async def character_say(self, ctx: G0T0Context):
        """
        Handles the character say command, allowing a player to send a message as one of their characters.
        Args:
            ctx (discord.ApplicationContext): The context of the command invocation.
        Raises:
            CharacterNotFound: If the player has no characters.
        Workflow:
            1. Extracts the content of the message.
            2. Deletes the original message.
            3. Checks if the content is empty or just the command invocation.
            4. Retrieves the player and their characters.
            5. Searches for a character in the player's list of characters based on the content.
            6. If no character is found, retrieves a webhook character for the player.
            7. Handles character mentions in the content.
            8. Splits the content into chunks and sends each chunk as a webhook message.
            9. Updates post stats and activity points if applicable.
            10. Sends a response ping if the message is a reply to another message.
        """
        await G0T0Webhook(ctx, WebhookType.say).run()
        await try_delete(ctx.message)
        

                
    @character_admin_commands.command(
        name="manage",
        description="Manage a players character(s)"
    )
    async def character_manage(self, ctx: G0T0Context,
                               member: discord.Option(discord.SlashCommandOptionType(6), description="Player", required=True)):
        """
        Manages a player's character.
        Args:
            ctx (discord.ApplicationContext): The context of the command.
            member (discord.Option): The player whose character is to be managed.
        Returns:
            None
        """
        player = await self.bot.get_player(member.id, ctx.guild.id)

        ui = CharacterManageUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="get",
        description="Displays character information for a player's character"
    )
    async def character_get(self, ctx: G0T0Context,
                            member: discord.Option(discord.SlashCommandOptionType(6), description="Player to get the information of",
                                           required=False)):
        """
        Retrieves and displays information about a player's characters.
        Parameters:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            member (discord.Option, optional): The player to get the information of. If not provided, defaults to the command author.
        Returns:
            None
        """
        await ctx.defer()

        player = ctx.player if not member else await self.bot.get_player(member.id, ctx.guild.id if ctx.guild else None,
                                                    ctx=ctx)

        if len(player.characters) == 0:
            return await ctx.respond(embed=PlayerOverviewEmbed(player, self.bot.compendium))


        ui = CharacterGetUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()
    
    @commands.slash_command(
            name="settings",
            description="Character settings"
    )
    async def character_settings(self, ctx: G0T0Context):
        """
        Handles the character settings command.
        This command allows a player to manage their character settings within the game.
        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
        Raises:
            CharacterNotFound: If the player has no characters.
        Returns:
            None
        """       
        if not ctx.player.characters:
            raise CharacterNotFound(ctx.player.member)
        
        ui = CharacterSettingsUI.new(self.bot, ctx.author, ctx.player)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
            name="rp_request",
            description="RP Board Request",
    )
    async def rp_request(self, ctx: G0T0Context):
        """
        Handles a roleplay request from a user.
        This method is triggered when a user initiates a roleplay request. It retrieves the player's
        information and checks if the player has any characters. If no characters are found, it raises
        a CharacterNotFound exception. Otherwise, it creates a new RPPostUI instance and sends it to
        the context. Finally, it deletes the original context message.
        Args:
            ctx (discord.ApplicationContext): The context of the application command.
        Raises:
            CharacterNotFound: If the player has no characters.
        """
        if not ctx.player.characters:
            raise CharacterNotFound(ctx.player.member)
        
        ui = RPPostUI.new(self.bot, ctx.player)
        await ui.send_to(ctx)
        await ctx.delete()
        

    @commands.slash_command(
        name="level_request",
        description="Level Request"
    )
    async def character_level_request(self, ctx: G0T0Context):
        """
        Handles a character level request from a user.
        This method is triggered when a user requests to level up their character.
        It checks if the user has any characters, and if so, whether the character
        is already at the maximum level for the server. If the user has multiple
        characters, it presents a UI for the user to select which character to level up.
        Args:
            ctx (discord.ApplicationContext): The context of the interaction, including
                                      information about the user and the guild.
        Raises:
            CharacterNotFound: If the user has no characters.
            G0T0Error: If the user's character is already at the maximum level for the server.
        """
        application = PlayerApplication(self.bot, ctx.author, type=ApplicationType.level)
        if not ctx.player.characters:
            raise CharacterNotFound(ctx.player.member)
        elif len(ctx.player.characters) == 1:
            if ctx.player.characters[0].level >= ctx.player.guild.max_level:
                raise G0T0Error("Character is already at max level for the server")
            application.application.character = ctx.player.characters[0]
            modal = LevelUpRequestModal(ctx.player.guild, application.application)
            return await ctx.send_modal(modal)
        else:
            ui = CharacterSelectUI.new(application, ctx.player)
            await ui.send_to(ctx)
            await ctx.delete()

    @commands.slash_command(
        name="new_character_request",
        description="New Character Request"
    )
    async def new_character_request(self, ctx: G0T0Context):
        """
        Handles the request to create a new character.
        This function retrieves the player information and their character application,
        then presents the appropriate UI for character selection or new character request.
        Args:
            ctx (discord.ApplicationContext): The context of the application command.
        Returns:
            None
        """
        application: PlayerApplication = PlayerApplication(self.bot, ctx.author)
        await application.load()
        if application.application and application.application.type not in [ApplicationType.death, ApplicationType.freeroll, ApplicationType.new]:
            application.application = PlayerApplication(self.bot, ctx.author)
            application.cached = False
        
        if ctx.player.characters:
            ui = CharacterSelectUI.new(application, ctx.player)
        else:
            ui = NewCharacterRequestUI.new(application, ctx.player)

        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="edit_application",
        description="Edit an application"
    )
    async def edit_application(self, ctx: G0T0Context,
                               application_id: discord.Option(discord.SlashCommandOptionType(3), description="Application ID", required=False)):
        """
        Edits an application based on the provided application ID or the current channel ID.
        Args:
            ctx (discord.ApplicationContext): The context of the command invocation.
            application_id (discord.Option[str], optional): The ID of the application to edit. Defaults to None.
        Raises:
            G0T0Error: If the application identifier is invalid or the application is already approved or denied.
            ApplicationNotFound: If the application message is not found.
            CharacterNotFound: If no characters are found for the player.
        Returns:
            None
        """        
        if ctx.player.guild.application_channel:
            if application_id:
                try:
                    message = await ctx.player.guild.application_channel.fetch_message(int(application_id))
                except ValueError:
                    raise G0T0Error("Invalid application identifier")
                except discord.NotFound:
                    raise ApplicationNotFound()
            else:
                try:
                    message = await ctx.player.guild.application_channel.fetch_message(ctx.channel.id)
                except:
                    raise ApplicationNotFound()
        

        emoji = [x.emoji.name if hasattr(x.emoji, 'name') else x.emoji for x in message.reactions]
        if any(e in APPROVAL_EMOJI for e in emoji):
            raise G0T0Error("Application is already approved. Cannot edit at this time")
        elif any(e in DENIED_EMOJI for e in emoji):
            raise G0T0Error("Application marked as invalid and cannot me modified")
        
        application = PlayerApplication(self.bot, ctx.author, edit=True)
        await application.load(message)

        if application.application.type in [ApplicationType.new, ApplicationType.death, ApplicationType.freeroll]:
            if ctx.player.characters:
                ui = CharacterSelectUI.new(application, ctx.player)
            else:
                ui = NewCharacterRequestUI.new(application, ctx.player)

            await ui.send_to(ctx)
            await ctx.delete()

        else:
            if not ctx.player.characters:
                raise CharacterNotFound(ctx.player.member)
            elif len(ctx.player.characters) == 1:
                modal = LevelUpRequestModal(ctx.player.guild, application.application)
                return await ctx.send_modal(modal)
            else:
                ui = CharacterSelectUI.new(application, ctx.player)
                await ui.send_to(ctx)
                await ctx.delete()
        
