import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.autocomplete import get_faction_autocomplete
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds.adventures import AdventuresEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.exceptions import (AdventureNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.objects.webhook import G0T0Webhook, WebhookType
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
    bot: G0T0Bot  
    adventure_commands = discord.SlashCommandGroup("adventure", "Adventure commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Adventures\' loaded')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """
        Handles errors that occur during command execution.
        This function is called when an error is raised while invoking a command.
        It checks if the context has a bot with a database, and if the command was
        executed in a guild and within a channel category. If these conditions are
        met, it sends a webhook notification.
        Args:
            ctx (commands.Context): The context in which the command was invoked.
            error (Exception): The error that was raised during command execution.
        """
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db") and ctx.guild and ctx.channel.category:
            await G0T0Webhook(ctx, WebhookType.adventure).run()

    @commands.slash_command(
        name="adventures",
        description="Shows active adventures for a player"
    )
    async def adventure_get(self, ctx: discord.ApplicationContext,
                            member: discord.Option(discord.SlashCommandOptionType(6), description="Player to get the information of", required=False),
                            phrase: discord.Option(str, description="Additional question/phrase to add", required=False),
                            phrase2: discord.Option(str, description="Additional question/phrase to add", required=False)):
        
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
    async def adventure_create(self, ctx: discord.ApplicationContext,
                               adventure_name: discord.Option(str, description="The name of the adventure as it should show up"
                                                                       "in the category and channel names",
                                                      required=True),
                               role_name: discord.Option(str, description="The name of the Role to be created for adventure"
                                                                  "participants", required=True),
                               dm: discord.Option(discord.SlashCommandOptionType(6), description="The DM of the adventure.", required=True),
                               faction1: discord.Option(str, description="First faction this adventure is for", autocomplete=get_faction_autocomplete, required=False),
                               faction2: discord.Option(str, description="Second faction this adventure is for", autocomplete=get_faction_autocomplete, required=False)):
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
        if discord.utils.get(ctx.guild.roles, name=role_name):
            raise G0T0Error(f"Role `@{role_name}` already exists")
        else:
            g = await self.bot.get_player_guild(ctx.guild.id)
            adventure_role: discord.Role = await ctx.guild.create_role(name=role_name, mentionable=True,
                                                         reason=f"Created by {ctx.author.nick} for adventure"
                                                                f"{adventure_name}")
            
            # Setup role permissions
            category_permissions = dict()

            category_permissions[adventure_role] = discord.PermissionOverwrite(view_channel=True, 
                                                                               send_messages=True)

            if bots_role := discord.utils.get(ctx.guild.roles, name="Bots"):
                category_permissions[bots_role] = discord.PermissionOverwrite(view_channel=True,
                                                                              send_messages=True)

            if goto_role := discord.utils.get(ctx.guild.roles, name="G0-T0 Resolute"):
                category_permissions[goto_role] = discord.PermissionOverwrite(view_channel=True,
                                                                              send_messages=True,
                                                                              manage_messages=True,
                                                                              manage_channels=True)

            category_permissions[ctx.guild.default_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False
            )

            # Copy Overwrites
            ic_overwrites = category_permissions.copy()
            ooc_overwrites = category_permissions.copy()

            # Setup the questers
            if g.quest_role:
                ic_overwrites[g.quest_role] = discord.PermissionOverwrite(
                    view_channel=True
                )

                ooc_overwrites[g.quest_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

            new_adventure_category: discord.CategoryChannel = await ctx.guild.create_category_channel(
                name=adventure_name,
                overwrites=category_permissions,
                reason=f"Creating category for {adventure_name}"
            )

            ic_channel: discord.TextChannel = await ctx.guild.create_text_channel(
                name=adventure_name,
                category=new_adventure_category,
                overwrites=ic_overwrites,
                position=0,
                reason=f"Creating adventure {adventure_name} IC Room"
            )

            ooc_channel: discord.TextChannel = await ctx.guild.create_text_channel(
                name=f"{adventure_name}-ooc",
                category=new_adventure_category,
                overwrites=ooc_overwrites,
                position=1,
                reason=f"Creating adventure {adventure_name} OOC Room"
            )

            adventure: Adventure = Adventure(self.bot.db, ctx.guild.id, adventure_name, adventure_role, new_adventure_category, dms=[dm.id],
                                            factions=[self.bot.compendium.get_object(Faction, f) for f in (faction1, faction2) if f])
            
            await adventure.update_dm_permissions(dm)
            
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

        if isinstance(error, discord.Forbidden):
            raise G0T0Error(f"Bot isn't allowed to do that for some reason")
        elif isinstance(error, discord.HTTPException):
            raise G0T0Error(f"Error createing new role")
        elif isinstance(error, discord.InvalidArgument):
            raise G0T0Error(f"Invalid Argument: {error}")

    @adventure_commands.command(
        name="manage",
        description="Manage an adventure. Either run in the adventure channel or specify a role/category"
    )
    async def adventure_manage(self, ctx: discord.ApplicationContext,
                               role: discord.Option(discord.Role, description="Role of the adventure", required=False),
                               channel_category: discord.Option(discord.CategoryChannel, description="Adventure Channel Category", required=False)):
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