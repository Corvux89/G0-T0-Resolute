import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import ZWSP3
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds import PlayerEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.exceptions import (
    AdventureNotFound,
    CharacterNotFound,
    G0T0Error,
)
from Resolute.models.views.adventures import AdventureSettingsUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Adventures(bot))


class Adventures(commands.Cog):
    """
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
    """

    bot: G0T0Bot
    adventure_commands = discord.SlashCommandGroup(
        "adventure", "Adventure commands", guild_only=True
    )

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Adventures' loaded")

    @commands.slash_command(
        name="adventures", description="Shows active adventures for a player"
    )
    async def adventure_get(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player to get the information of",
            required=False,
        ),
        phrase: discord.Option(
            str, description="Additional question/phrase to add", required=False
        ),
        phrase2: discord.Option(
            str, description="Additional question/phrase to add", required=False
        ),
    ):
        """
        Retrieves information about a player's adventure.
        Parameters:
            ctx (G0T0Context): The context of the command invocation.
            member (discord.Option): The player to get the information of. Optional.
            phrase (discord.Option): Additional question/phrase to add. Optional.
            phrase2 (discord.Option): Additional question/phrase to add. Optional.
        Raises:
            CharacterNotFound: If the player has no characters.
        Returns:
            Coroutine: A coroutine that sends an embed with the player's adventure information.
        """
        await ctx.defer()

        player = (
            ctx.player
            if not member
            else await self.bot.get_player(
                member.id, ctx.guild.id if ctx.guild else None
            )
        )

        if not ctx.player.characters:
            raise CharacterNotFound(member)

        phrases = [p for p in [phrase, phrase2] if p]

        embed = PlayerEmbed(
            player.member,
            title=f"Adventure information for {player.member.display_name}",
        )

        dm_str = (
            "\n".join(
                [
                    f"{ZWSP3}{adventure.name} ({adventure.role.mention})"
                    for adventure in player.adventures
                    if player.id in adventure.dms
                ]
            )
            if len(player.adventures) > 0
            else None
        )

        if dm_str:
            embed.add_field(name="DM'ing Adventures", value=dm_str, inline=False)

        for character in player.characters:
            adventure_str = (
                "\n".join(
                    [
                        f"{ZWSP3}{adventure.name} ({adventure.role.mention})"
                        for adventure in player.adventures
                        if character.id in adventure.characters
                    ]
                )
                if len(player.adventures) > 0
                else "None"
            )

            class_str = ",".join(
                [f" {c.get_formatted_class()}" for c in character.classes]
            )

            embed.add_field(
                name=f"{character.name} - Level {character.level} [{class_str}]",
                value=adventure_str or "None",
                inline=False,
            )

        if phrases:
            for p in phrases:
                out_str = p.split("|")
                embed.add_field(
                    name=out_str[0],
                    value=f"{out_str[1] if len(out_str) > 1 else ''}",
                    inline=False,
                )

        return await ctx.respond(embed=embed)

    async def faction_autocomplete(self, ctx: discord.AutocompleteContext) -> list[str]:
        return [f.value for f in self.bot.compendium.faction[0].values()] or []

    @adventure_commands.command(name="create", description="Creates a new adventure")
    async def adventure_create(
        self,
        ctx: G0T0Context,
        adventure_name: discord.Option(
            str,
            description="The name of the adventure as it should show up"
            "in the category and channel names",
            required=True,
        ),
        role_name: discord.Option(
            str,
            description="The name of the Role to be created for adventure"
            "participants",
            required=True,
        ),
        dm: discord.Option(
            discord.SlashCommandOptionType(6),
            description="The DM of the adventure.",
            required=True,
        ),
        faction1: discord.Option(
            str,
            description="First faction this adventure is for",
            autocomplete=faction_autocomplete,
            required=False,
        ),
        faction2: discord.Option(
            str,
            description="Second faction this adventure is for",
            autocomplete=faction_autocomplete,
            required=False,
        ),
    ):
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
            g = ctx.player.guild
            adventure_role: discord.Role = await g.guild.create_role(
                name=role_name,
                mentionable=True,
                reason=f"Created by {ctx.author.nick} for adventure"
                f"{adventure_name}",
            )

            # Setup role permissions
            category_permissions = dict()

            category_permissions[adventure_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )

            if bots_role := discord.utils.get(g.guild.roles, name="Bots"):
                category_permissions[bots_role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )

            if goto_role := discord.utils.get(g.guild.roles, name="G0-T0 Resolute"):
                category_permissions[goto_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True,
                )

            category_permissions[g.guild.default_role] = discord.PermissionOverwrite(
                view_channel=False, send_messages=False
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
                    view_channel=True, send_messages=True
                )

            new_adventure_category: discord.CategoryChannel = (
                await g.guild.create_category_channel(
                    name=adventure_name,
                    overwrites=category_permissions,
                    reason=f"Creating category for {adventure_name}",
                )
            )

            ic_channel: discord.TextChannel = await g.guild.create_text_channel(
                name=adventure_name,
                category=new_adventure_category,
                overwrites=ic_overwrites,
                position=0,
                reason=f"Creating adventure {adventure_name} IC Room",
            )

            ooc_channel: discord.TextChannel = await g.guild.create_text_channel(
                name=f"{adventure_name}-ooc",
                category=new_adventure_category,
                overwrites=ooc_overwrites,
                position=1,
                reason=f"Creating adventure {adventure_name} OOC Room",
            )

            adventure: Adventure = Adventure(
                self.bot.db,
                g.guild.id,
                adventure_name,
                adventure_role,
                new_adventure_category,
                dms=[dm.id],
                factions=[
                    self.bot.compendium.get_object(Faction, f)
                    for f in (faction1, faction2)
                    if f
                ],
            )

            await adventure.update_dm_permissions(dm)

            await adventure.upsert()

            await ooc_channel.send(
                f"Adventure {adventure.name} successfully created!\n"
                f"Role: {adventure_role.mention}\n"
                f"IC Room: {ic_channel.mention}\n"
                f"OOC Room: {ooc_channel.mention}\n\n"
                f"{dm.mention} - Please ensure your permissions are correct in these rooms! "
                f"If so, you can start adding players with `/adventure manage`"
            )

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
        description="Manage an adventure. Either run in the adventure channel or specify a role/category",
    )
    async def adventure_manage(
        self,
        ctx: G0T0Context,
        role: discord.Option(
            discord.Role, description="Role of the adventure", required=False
        ),
        channel_category: discord.Option(
            discord.CategoryChannel,
            description="Adventure Channel Category",
            required=False,
        ),
    ):
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
            adventure = await self.bot.get_adventure_from_category(
                ctx.channel.category.id
            )

        if adventure is None:
            raise AdventureNotFound()

        ui = AdventureSettingsUI.new(self.bot, ctx.author, adventure, ctx.playerGuild)
        await ui.send_to(ctx)
        await ctx.delete()
