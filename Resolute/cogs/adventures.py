import logging

from discord import (ApplicationContext, CategoryChannel, Forbidden,
                     HTTPException, InvalidArgument, Option,
                     PermissionOverwrite, Role, SlashCommandGroup,
                     SlashCommandOptionType, TextChannel, Thread, User, utils)
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers.adventures import update_dm
from Resolute.helpers.autocomplete import get_faction_autocomplete
from Resolute.helpers.characters import handle_character_mention
from Resolute.helpers.general_helpers import get_webhook, split_content
from Resolute.models.embeds.adventures import AdventuresEmbed
from Resolute.models.objects.adventures import (Adventure)
from Resolute.models.objects.exceptions import (AdventureNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.views.adventures import AdventureSettingsUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Adventures(bot))

class Adventures(commands.Cog):
    '''
    A Cog that handles adventure-related commands and events for the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        adventure_commands (SlashCommandGroup): A group of slash commands related to adventures.
    Methods:
        __init__(bot):
            Initializes the Adventures cog with the given bot instance.
        on_command_error(ctx, error):
        adventure_get(ctx, member, phrase, phrase2):
        adventure_create(ctx, adventure_name, role_name, dm, faction1, faction2):
        create_error(ctx, error):
        adventure_manage(ctx, role, channel_category):
    '''
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    adventure_commands = SlashCommandGroup("adventure", "Adventure commands", guild_only=True)

    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Adventures\' loaded')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """
        Handles errors that occur when a command is invoked.
        This function checks if the context has a bot with a database, and if the command was invoked in a guild and a channel category.
        If an adventure is found for the category, and the author is a DM in the adventure, it processes the command as an NPC command.
        Args:
            ctx (commands.Context): The context in which the command was invoked.
            error (Exception): The error that was raised.
        Returns:
            None
        """

        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db") and ctx.guild and ctx.channel.category:
            if adventure := await self.bot.get_adventure_from_category(ctx.channel.category.id):
                if ctx.author.id in adventure.dms and (npc := next((npc for npc in adventure.npcs if npc.key == ctx.invoked_with), None)):
                    player = await self.bot.get_player(ctx.author.id, ctx.guild.id)
                    content = ctx.message.content.replace(f'>{npc.key}', '')
                    content = await handle_character_mention(ctx, content)

                    await player.update_command_count("npc")
                    webhook = await get_webhook(ctx.channel)
                    chunks = split_content(content)

                    for chunk in chunks:
                        if isinstance(ctx.channel, Thread):
                            await webhook.send(username=npc.name,
                                                avatar_url=npc.avatar_url if npc.avatar_url else None,
                                                content=chunk,
                                                thread=ctx.channel)
                        else:
                            await webhook.send(username=npc.name,
                                            avatar_url=npc.avatar_url if npc.avatar_url else None,
                                            content=chunk)
                            
                        if not player.guild.is_dev_channel(ctx.channel):
                            await player.update_post_stats(npc, ctx.message, content=chunk)

                            if len(chunk)>=ACTIVITY_POINT_MINIMUM:
                                await self.bot.update_player_activity_points(player)

                    await ctx.message.delete()

    @commands.slash_command(
        name="adventures",
        description="Shows active adventures for a player"
    )
    async def adventure_get(self, ctx: ApplicationContext,
                            member: Option(SlashCommandOptionType(6), description="Player to get the information of", required=False),
                            phrase: Option(str, description="Additional question/phrase to add", required=False),
                            phrase2: Option(str, description="Additional question/phrase to add", required=False)):
        
        """
        Retrieves and responds with the adventure information of a specified player.
        Parameters:
            ctx (ApplicationContext): The context of the command invocation.
            member (Option, optional): The player to get the information of. Defaults to the command author if not provided.
            phrase (Option, optional): An additional question/phrase to add. Defaults to None.
            phrase2 (Option, optional): An additional question/phrase to add. Defaults to None.
        Raises:
            CharacterNotFound: If the specified player does not have any characters.
        Returns:
            Coroutine: A coroutine that sends an embed with the player's adventure information.
        """

        await ctx.defer()

        if member is None:
            member = ctx.author

        player = await self.bot.get_player(member.id, ctx.guild.id if ctx.guild else None)
        
        if not player.characters:
            raise CharacterNotFound(member)
        
        
        phrases = [p for p in [phrase, phrase2] if p]

        return await ctx.respond(embed=AdventuresEmbed(player, phrases))


    @adventure_commands.command(
        name="create",
        description="Creates a new adventure"
    )
    async def adventure_create(self, ctx: ApplicationContext,
                               adventure_name: Option(str, description="The name of the adventure as it should show up"
                                                                       "in the category and channel names",
                                                      required=True),
                               role_name: Option(str, description="The name of the Role to be created for adventure"
                                                                  "participants", required=True),
                               dm: Option(SlashCommandOptionType(6), description="The DM of the adventure.", required=True),
                               faction1: Option(str, description="First faction this adventure is for", autocomplete=get_faction_autocomplete, required=True),
                               faction2: Option(str, description="Second faction this adventure is for", autocomplete=get_faction_autocomplete, required=True)):
        """
        Creates a new adventure with the specified parameters.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
            adventure_name (str): The name of the adventure as it should appear in the category and channel names.
            role_name (str): The name of the role to be created for adventure participants.
            dm (SlashCommandOptionType): The Dungeon Master (DM) of the adventure.
            faction1 (str): The first faction this adventure is for.
            faction2 (str): The second faction this adventure is for.
        Raises:
            G0T0Error: If a role with the specified role_name already exists.
        Returns:
            None
        """

        await ctx.defer()

        # Create the role
        if utils.get(ctx.guild.roles, name=role_name):
            raise G0T0Error(f"Role `@{role_name}` already exists")
        else:
            g = await self.bot.get_player_guild(ctx.guild.id)
            adventure_role: Role = await ctx.guild.create_role(name=role_name, mentionable=True,
                                                         reason=f"Created by {ctx.author.nick} for adventure"
                                                                f"{adventure_name}")
            
            # Setup role permissions
            category_permissions = dict()

            category_permissions[adventure_role] = PermissionOverwrite(view_channel=True, 
                                                                               send_messages=True)

            if bots_role := utils.get(ctx.guild.roles, name="Bots"):
                category_permissions[bots_role] = PermissionOverwrite(view_channel=True,
                                                                              send_messages=True)

            if goto_role := utils.get(ctx.guild.roles, name="G0-T0 Resolute"):
                category_permissions[goto_role] = PermissionOverwrite(view_channel=True,
                                                                              send_messages=True,
                                                                              manage_messages=True,
                                                                              manage_channels=True)

            category_permissions[ctx.guild.default_role] = PermissionOverwrite(
                view_channel=False,
                send_messages=False
            )

            # Add DM to the role and let them manage messages in their channels
            category_permissions = await update_dm(dm, category_permissions, adventure_role, adventure_name)

            # Copy Overwrites
            ic_overwrites = category_permissions.copy()
            ooc_overwrites = category_permissions.copy()

            # Setup the questers
            if g.quest_role:
                ic_overwrites[g.quest_role] = PermissionOverwrite(
                    view_channel=True
                )

                ooc_overwrites[g.quest_role] = PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

            new_adventure_category: CategoryChannel = await ctx.guild.create_category_channel(
                name=adventure_name,
                overwrites=category_permissions,
                reason=f"Creating category for {adventure_name}"
            )

            ic_channel: TextChannel = await ctx.guild.create_text_channel(
                name=adventure_name,
                category=new_adventure_category,
                overwrites=ic_overwrites,
                position=0,
                reason=f"Creating adventure {adventure_name} IC Room"
            )

            ooc_channel: TextChannel = await ctx.guild.create_text_channel(
                name=f"{adventure_name}-ooc",
                category=new_adventure_category,
                overwrites=ooc_overwrites,
                position=1,
                reason=f"Creating adventure {adventure_name} OOC Room"
            )

            adventure: Adventure = Adventure(guild_id=ctx.guild.id,name=adventure_name, role_id=adventure_role.id, dms=[dm.id],
                                  category_channel_id=new_adventure_category.id, cc=0)
            
            await adventure.upsert()

            await ooc_channel.send(f"Adventure {adventure.name} successfully created!\n"
                                   f"Role: {adventure_role.mention}\n"
                                   f"IC Room: {ic_channel.mention}\n"
                                   f"OOC Room: {ooc_channel.mention}\n\n"
                                   f"{dm.mention} - Please ensure your permissions are correct in these rooms! "
                                   f"If so, you can start adding players with `/adventure manage`")

            await ctx.delete()

    @adventure_create.error
    async def create_error(self, ctx, error):
        """
        Handles errors that occur during the execution of a command.
        Parameters:
            ctx (Context): The context in which the error occurred.
            error (Exception): The error that was raised.
        Raises:
            G0T0Error: If the error is of type Forbidden, HTTPException, or InvalidArgument.
        """

        if isinstance(error, Forbidden):
            raise G0T0Error(f"Bot isn't allowed to do that for some reason")
        elif isinstance(error, HTTPException):
            raise G0T0Error(f"Error createing new role")
        elif isinstance(error, InvalidArgument):
            raise G0T0Error(f"Invalid Argument: {error}")

    @adventure_commands.command(
        name="manage",
        description="Manage an adventure. Either run in the adventure channel or specify a role/category"
    )
    async def adventure_manage(self, ctx: ApplicationContext,
                               role: Option(Role, description="Role of the adventure", required=False),
                               channel_category: Option(CategoryChannel, description="Adventure Channel Category", required=False)):
        """
        Manages the settings of an adventure based on the provided role or channel category.
        Parameters:
        -----------
        ctx : ApplicationContext
            The context in which the command was invoked.
        role : Option(Role), optional
            The role associated with the adventure (default is None).
        channel_category : Option(CategoryChannel), optional
            The channel category associated with the adventure (default is None).
        Raises:
        -------
        AdventureNotFound
            If no adventure is found for the given role or channel category.
        """
        if role:
            adventure = await self.bot.get_adventure_from_role(role.id)
        elif channel_category:
            adventure = await self.bot.get_adventure_from_category(channel_category.id)
        else:
            adventure = await self.bot.get_adventure_from_category(ctx.channel.category.id)

        if adventure is None:
            raise AdventureNotFound()
        
        ui = AdventureSettingsUI.new(self.bot, ctx.author, adventure)
        await ui.send_to(ctx)
        await ctx.delete()