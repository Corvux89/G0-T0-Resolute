import logging
import re

from discord import (ApplicationContext, NotFound, Option, SlashCommandGroup,
                     SlashCommandOptionType)
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM, APPROVAL_EMOJI, DENIED_EMOJI
from Resolute.helpers.appliations import (get_cached_application,
                                          get_level_up_application,
                                          get_new_character_application)
from Resolute.helpers.characters import handle_character_mention
from Resolute.helpers.general_helpers import split_content
from Resolute.helpers.messages import get_player_from_say_message
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.objects.exceptions import (ApplicationNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.views.applications import (CharacterSelectUI,
                                                LevelUpRequestModal,
                                                NewCharacterRequestUI)
from Resolute.models.views.character_view import (CharacterGetUI,
                                                  CharacterManageUI,
                                                  CharacterSettingsUI,
                                                  RPPostUI)

log = logging.getLogger(__name__)

# TODO: Add Character Birthday for server date

def setup(bot: commands.Bot):
    bot.add_cog(Character(bot))


class Character(commands.Cog):
    """
    Cog for handling character-related commands and interactions.
    Attributes:
        bot (G0T0Bot): The bot instance.
        character_admin_commands (SlashCommandGroup): Group of character administration commands.
    Methods:
        __init__(bot):
            Initializes the Character cog with the given bot instance.
        character_say(ctx: ApplicationContext):
            Command for making a character say something in the chat.
        character_manage(ctx: ApplicationContext, member: Option):
            Command for managing a player's character(s).
        character_get(ctx: ApplicationContext, member: Option):
            Command for displaying character information for a player's character.
        character_settings(ctx: ApplicationContext):
            Command for accessing character settings.
        rp_request(ctx: ApplicationContext):
            Command for making an RP board request.
        character_level_request(ctx: ApplicationContext):
            Command for making a level request for a character.
        new_character_request(ctx: ApplicationContext):
            Command for making a new character request.
        edit_application(ctx: ApplicationContext, application_id: Option):
            Command for editing an application.
    """
    bot: G0T0Bot
    character_admin_commands = SlashCommandGroup("character_admin", "Character administration commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Characters\' loaded')    

    @commands.command(
        name="say",
        guild_only=True
    )
    async def character_say(self, ctx: ApplicationContext):
        """
        Handles the character say command, allowing a player to send a message as one of their characters.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
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
        content = ctx.message.content

        content = content[5:]
        await ctx.message.delete()

        if content == "" or content.lower() == ">say":
            return
        
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id)
        character = None

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        if match := re.match(r"^(['\"“”])(.*?)['\"“”]", content):
            search = match.group(2)
            character = next((c for c in player.characters if search.lower() in c.name.lower()), None)
            if character:
                content = re.sub(r"^(['\"“”])(.*?)['\"“”]\s*", "", content, count=1)
            
        if not character:
            character = await player.get_webhook_character(ctx.channel)

        content = await handle_character_mention(ctx, content)        

        chunks = split_content(content)
        for chunk in chunks:
            try:
                await player.send_webhook_message(ctx, character, chunk)

                if not player.guild.is_dev_channel(ctx.channel):
                    await player.update_post_stats(character, ctx.message, content=chunk)

                    if len(chunk) >= ACTIVITY_POINT_MINIMUM:
                        await self.bot.update_player_activity_points(player)

                 # Message response ping
                if ctx.message.reference is not None:
                    try:
                        if ctx.message.reference.resolved and ctx.message.reference.resolved.author.bot and (orig_player := await get_player_from_say_message(self.bot, ctx.message.reference.resolved)):
                            await orig_player.member.send(f"{ctx.author.mention} replied to your message in:\n{ctx.channel.jump_url}")
                    except Exception as error:
                        log.error(f"Error replying to message {error}")
                        
            except:
                await player.member.send(f"Error sending message in {ctx.channel.jump_url}. Try again: ")
                await player.member.send(f"```{content}```")

        

                
    @character_admin_commands.command(
        name="manage",
        description="Manage a players character(s)"
    )
    async def character_manage(self, ctx: ApplicationContext,
                               member: Option(SlashCommandOptionType(6), description="Player", required=True)):
        """
        Manages a player's character.
        Args:
            ctx (ApplicationContext): The context of the command.
            member (Option): The player whose character is to be managed.
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
    async def character_get(self, ctx: ApplicationContext,
                            member: Option(SlashCommandOptionType(6), description="Player to get the information of",
                                           required=False)):
        """
        Retrieves and displays information about a player's characters.
        Parameters:
            ctx (ApplicationContext): The context in which the command was invoked.
            member (Option, optional): The player to get the information of. If not provided, defaults to the command author.
        Returns:
            None
        """
        await ctx.defer()

        member = member or ctx.author
        player = await self.bot.get_player(member.id, ctx.guild.id if ctx.guild else None,
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
    async def character_settings(self, ctx: ApplicationContext):
        """
        Handles the character settings command.
        This command allows a player to manage their character settings within the game.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
        Raises:
            CharacterNotFound: If the player has no characters.
        Returns:
            None
        """        
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        ui = CharacterSettingsUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
            name="rp_request",
            description="RP Board Request",
    )
    async def rp_request(self, ctx: ApplicationContext):
        """
        Handles a roleplay request from a user.
        This method is triggered when a user initiates a roleplay request. It retrieves the player's
        information and checks if the player has any characters. If no characters are found, it raises
        a CharacterNotFound exception. Otherwise, it creates a new RPPostUI instance and sends it to
        the context. Finally, it deletes the original context message.
        Args:
            ctx (ApplicationContext): The context of the application command.
        Raises:
            CharacterNotFound: If the player has no characters.
        """
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        ui = RPPostUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()
        

    @commands.slash_command(
        name="level_request",
        description="Level Request"
    )
    async def character_level_request(self, ctx: ApplicationContext):
        """
        Handles a character level request from a user.
        This method is triggered when a user requests to level up their character.
        It checks if the user has any characters, and if so, whether the character
        is already at the maximum level for the server. If the user has multiple
        characters, it presents a UI for the user to select which character to level up.
        Args:
            ctx (ApplicationContext): The context of the interaction, including
                                      information about the user and the guild.
        Raises:
            CharacterNotFound: If the user has no characters.
            G0T0Error: If the user's character is already at the maximum level for the server.
        """
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)

        if not player.characters:
            raise CharacterNotFound(player.member)
        elif len(player.characters) == 1:
            if player.characters[0].level >= player.guild.max_level:
                raise G0T0Error("Character is already at max level for the server")
            modal = LevelUpRequestModal(player.guild, player.characters[0])
            return await ctx.send_modal(modal)
        else:
            ui = CharacterSelectUI.new(self.bot, ctx.author, player, True)
            await ui.send_to(ctx)
            await ctx.delete()

    @commands.slash_command(
        name="new_character_request",
        description="New Character Request"
    )
    async def new_character_request(self, ctx: ApplicationContext):
        """
        Handles the request to create a new character.
        This function retrieves the player information and their character application,
        then presents the appropriate UI for character selection or new character request.
        Args:
            ctx (ApplicationContext): The context of the application command.
        Returns:
            None
        """
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)
        application_text = await get_cached_application(self.bot.db, player.id)
        application = None

        if application_text:
            application = await get_new_character_application(self.bot, application_text)

        if player.characters:
            ui = CharacterSelectUI.new(self.bot, ctx.author, player, False, application)
        else:
            ui = NewCharacterRequestUI.new(self.bot, ctx.author, player, False, application)

        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="edit_application",
        description="Edit an application"
    )
    async def edit_application(self, ctx: ApplicationContext,
                               application_id: Option(str, description="Application ID", required=False)):
        """
        Edits an application based on the provided application ID or the current channel ID.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
            application_id (Option[str], optional): The ID of the application to edit. Defaults to None.
        Raises:
            G0T0Error: If the application identifier is invalid, the application is already approved,
                        the application is marked as invalid, the application type is unknown, or the
                        application does not belong to the user.
            ApplicationNotFound: If the application message is not found.
            CharacterNotFound: If no characters are found for the player during a level-up application.
        Returns:
            None
        """
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)
        
        if player.guild.application_channel:
            if application_id:
                try:
                    message = await player.guild.application_channel.fetch_message(int(application_id))
                except ValueError:
                    raise G0T0Error("Invalid application identifier")
                except NotFound:
                    raise ApplicationNotFound()
            else:
                try:
                    message = await player.guild.application_channel.fetch_message(ctx.channel.id)
                except:
                    raise ApplicationNotFound()
        

        emoji = [x.emoji.name if hasattr(x.emoji, 'name') else x.emoji for x in message.reactions]
        if any(e in APPROVAL_EMOJI for e in emoji):
            raise G0T0Error("Application is already approved. Cannot edit at this time")
        elif any(e in DENIED_EMOJI for e in emoji):
            raise G0T0Error("Application marked as invalid and cannot me modified")
        
        appliation_text = message.content
        player_match = re.search(r"^\*\*Player:\*\* (.+)", appliation_text, re.MULTILINE)
        type_match = re.search(r"^\*\*(.*?)\*\*\s\|", appliation_text, re.MULTILINE)
        type = type_match.group(1).strip().replace('*', '') if type_match else None

        if player_match and str(ctx.author.id) in player_match.group(1):
            if type and type in ["New Character", "Reroll", "Free Reroll"]:
                application = await get_new_character_application(self.bot, None, message)

                if player.characters:
                    ui = CharacterSelectUI.new(self.bot, ctx.author, player, False, application, True)
                else:
                    ui = NewCharacterRequestUI.new(self.bot, ctx.author, player, False, application)
                
                await ui.send_to(ctx)
                await ctx.delete()

            elif type and type == "Level Up":
                application = await get_level_up_application(self.bot, None, message)

                if not player.characters:
                    raise CharacterNotFound(player.member)
                elif len(player.characters) == 1:
                    modal = LevelUpRequestModal(player.guild, player.characters[0], application)
                    return await ctx.send_modal(modal)
                else:
                    ui = CharacterSelectUI.new(self.bot, ctx.author, player, True, application, True)
                    await ui.send_to(ctx)
                    await ctx.delete()
            
            else:
                raise G0T0Error("Unsure what type of application this is")
        else:
            raise G0T0Error("Not your application")
