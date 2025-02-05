import logging

from discord import (ApplicationContext, Option, SlashCommandOptionType,
                     WebhookMessage)
from discord.commands import SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import CHANNEL_BREAK
from Resolute.helpers.autocomplete import get_arena_type_autocomplete
from Resolute.helpers.general_helpers import confirm
from Resolute.models.categories import ArenaTier, ArenaType
from Resolute.models.embeds.arenas import (ArenaPhaseEmbed, ArenaStatusEmbed)
from Resolute.models.embeds.players import ArenaPostEmbed
from Resolute.models.objects.players import ArenaPost
from Resolute.models.objects.arenas import Arena
from Resolute.models.objects.exceptions import (ArenaNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.views.arena_view import (ArenaCharacterSelect,
                                              ArenaRequestCharacterSelect,
                                              CharacterArenaViewUI)

log = logging.getLogger(__name__)

def setup(bot):
    bot.add_cog(Arenas(bot))


class Arenas(commands.Cog):
    '''
    Arenas Cog for managing arena-related commands and events in the bot.
    This cog provides several commands and event listeners to handle arena interactions,
    including requesting to join an arena, claiming an arena, checking arena status,
    adding or removing players from an arena, recording phase outcomes, and closing arenas.
    Attributes:
        bot (G0T0Bot): The bot instance.
        arena_commands (SlashCommandGroup): A group of slash commands related to arenas.
    Methods:
        __init__(bot):
            Initializes the Arenas cog with the given bot instance.
        on_compendium_loaded():
            Asynchronous method called when the compendium is loaded.
            Adds CharacterArenaViewUI and ArenaCharacterSelect views to the bot.
        arena_request(ctx: ApplicationContext):
            Processes the player's request to join an arena and performs eligibility checks.
        arena_claim(ctx: ApplicationContext, type: Option):
            Allows a user to claim an arena of a specified type in the current channel.
        arena_status(ctx: ApplicationContext):
        arena_add(ctx: ApplicationContext, member: Option):
            Allows a user to add a specified player to an arena if they have at least one character.
        arena_remove(ctx: ApplicationContext, member: Option):
            Allows a user to remove a specified player from the arena.
        arena_phase(ctx: ApplicationContext, result: Option):
            Records the outcome of an arena phase and updates the arena status.
        arena_close(ctx: ApplicationContext):
            Prompts the user for confirmation to close the arena and frees the channel for use.
    '''
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    arena_commands = SlashCommandGroup("arena", "Commands for arenas!", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Arenas\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        """
        This asynchronous method is called when the compendium is loaded.
        It adds two views to the bot:
        1. CharacterArenaViewUI
        2. ArenaCharacterSelect
        These views are used for character arena interactions within the bot.
        """

        self.bot.add_view(CharacterArenaViewUI.new(self.bot))
        self.bot.add_view(ArenaCharacterSelect(self.bot))


    @commands.slash_command(
            name="arena_request",
            description="Request to join an arena"
    )
    async def arena_request(self, ctx: ApplicationContext):
        """
        Handles an arena request from a player.
        This method processes a player's request to join an arena. It performs several checks to ensure
        the player and their characters are eligible to join an arena. Depending on the number of characters
        the player has and their eligibility, it either submits the request or raises an appropriate error.
        Args:
            ctx (ApplicationContext): The context of the application command.
        Raises:
            CharacterNotFound: If the player has no characters.
            G0T0Error: If the player or their characters are already in the maximum allowed arenas,
                       if the character is already in an active arena, or if something else goes wrong.
        Returns:
            None
        """
                
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id if ctx.guild else None,
                                           ctx=ctx)
        
        

        if len(player.characters) == 0:
            raise CharacterNotFound(ctx.author)
        elif not player.can_join_arena():
            raise G0T0Error(f"You or your characters are already in the maximum allowed arenas.")
        elif len(player.characters) == 1:
            post = ArenaPost(player, player.characters)

            if player.guild.member_role and player.guild.member_role in player.member.roles:
                ui = ArenaRequestCharacterSelect.new(self.bot, player, post)
                await ui.send_to(ctx)
                return await ctx.delete()
            elif player.can_join_arena(self.bot.compendium.get_object(ArenaType, "COMBAT"), player.characters[0]):
                if await ArenaPostEmbed(post).build():
                    return await ctx.respond(f"Request submitted!", ephemeral=True)
            else:
                raise G0T0Error(f"Character already in an active arena.")
        else:
            ui = ArenaRequestCharacterSelect.new(self.bot, player)
            await ui.send_to(ctx)
            return await ctx.delete()
        
        raise G0T0Error("Something went wrong")
        

    @arena_commands.command(
        name="claim",
        description="Opens an arena in this channel and sets you as host"
    )
    async def arena_claim(self, ctx: ApplicationContext, type: Option(str, description="Arena Type", autocomplete=get_arena_type_autocomplete, required=True, default="COMBAT")):
        """
        Handles the claiming of an arena in the current channel.
        This command allows a user to claim an arena of a specified type in the current channel.
        If an arena is already in use in the channel, an error is raised.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
            type (str): The type of arena to claim. This is an option with autocomplete and a default value of "COMBAT".
        Raises:
            G0T0Error: If an arena is already in use in the current channel.
        Returns:
            None
        """

        await ctx.defer()

        arena: Arena = await self.bot.get_arena(ctx.channel_id)

        if arena:
            raise G0T0Error(f"{ctx.channel.mention} is already in use\n"
                            "Use `/arena status` to check on the status of the current arena in this channel")
        
        tier = self.bot.compendium.get_object(ArenaTier, 1)
        type = self.bot.compendium.get_object(ArenaType, type)

        arena = Arena(self.bot.db, self.bot.compendium, ctx.channel.id, ctx.author.id, tier, type)

        ui = CharacterArenaViewUI.new(self.bot)
        embed = ArenaStatusEmbed(ctx, arena)

        message: WebhookMessage = await ui.send_to(ctx, embed=embed)

        arena.pin_message_id = message.id
        await arena.upsert()

        await ctx.delete()
        

    @arena_commands.command(
        name="status",
        description="Shows the current status of this arena."
    )
    async def arena_status(self, ctx: ApplicationContext):
        """
        Retrieves and sends the status of the current arena in the context channel.
        This method defers the response, fetches the arena associated with the current
        channel, and sends an embedded message with the arena's status. If no arena is
        found, an ArenaNotFound exception is raised.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
        Raises:
            ArenaNotFound: If no arena is found for the current channel.
        Returns:
            Coroutine: A coroutine that sends the embedded arena status message.
        """

        await ctx.defer()
        arena = await self.bot.get_arena(ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        
        embed=ArenaStatusEmbed(ctx, arena)
        await embed.update()
        return await ctx.respond(embed=embed)

    @arena_commands.command(
        name="add",
        description="Adds the specified player to this arena"
    )
    async def arena_add(self, ctx: ApplicationContext,
                        member: Option(SlashCommandOptionType(6), description="Player to add to arena", required=True)):
        """
        Adds a player to an arena.
        This command allows a user to add a specified player to an arena. The player must have at least one character to be added.
        Args:
            ctx (ApplicationContext): The context in which the command was invoked.
            member (Option): The player to add to the arena.
        Raises:
            ArenaNotFound: If the arena does not exist.
            G0T0Error: If the player to be added is the host of the arena.
            CharacterNotFound: If the player does not have any characters.
        """
        
        arena = await self.bot.get_arena(ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        
        if member.id == arena.host_id:
            raise G0T0Error("Cannot add the host to an arena")

        player = await self.bot.get_player(member.id, ctx.guild.id)

        if not player.characters:
            raise CharacterNotFound(member)
        elif len(player.characters) == 1:
            await player.add_to_arena(ctx, player.characters[0], arena)
        else:
            ui = ArenaCharacterSelect.new(self.bot, player, ctx.author.id)
            await ui.send_to(ctx)
            await ctx.delete()

    @arena_commands.command(
        name="remove",
        description="Removes the specified player from this arena"
    )
    async def arena_remove(self, ctx: ApplicationContext,
                           member: Option(SlashCommandOptionType(6), description="Player to remove from arena", required=True)):
        """
        Removes a player from the arena.
        Args:
            ctx (ApplicationContext): The context of the command.
            member (Option): The player to remove from the arena.
        Raises:
            ArenaNotFound: If the arena does not exist.
            G0T0Error: If the member is the host or not an arena participant.
        Returns:
            None: Sends a response indicating the player has been removed from the arena.
        """
        
        arena = await self.bot.get_arena(ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        
        if member.id == arena.host_id:
            raise G0T0Error("Cannot add the host to an arena")
        
        remove_char = next((c for c in arena.player_characters if c.player_id == member.id), None)
        if remove_char:
            arena.player_characters.remove(remove_char)
            arena.characters.remove(remove_char.id)

            if arena.completed_phases == 0:
                arena.update_tier()
            
            await arena.upsert()
            await ArenaStatusEmbed(ctx, arena).update()              
            return await ctx.respond(f"{member.mention} has been removed from the arena.")
        else:
            raise G0T0Error(f"{member.mention} is not an arena participant")

    @arena_commands.command(
        name="phase",
        description="Records the outcome of an arena phase"
    )
    async def arena_phase(self, ctx: ApplicationContext,
                          result: Option(str, description="The result of the phase", required=True,
                                         choices=["WIN", "LOSS"])):

        """
        Handles the completion of a phase in the arena.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
            result (str): The result of the phase, either "WIN" or "LOSS".
        Raises:
            ArenaNotFound: If the arena is not found.
        This method performs the following actions:
            - Retrieves the arena associated with the current channel.
            - Increments the number of completed phases for the arena.
            - Logs the phase completion for the host and each player character.
            - Awards bonus rewards to players if applicable.
            - Updates the arena status embed.
            - Responds with the phase result embed.
            - Closes the arena if the maximum number of phases is reached or the result is "LOSS".
        """
        
        arena = await self.bot.get_arena(ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        
        arena.completed_phases += 1
        await arena.upsert()

        # Host Log
        host = await self.bot.get_player(arena.host_id, ctx.guild.id)
        await self.bot.log(ctx, host, ctx.author, "ARENA_HOST", silent=True)

        # Rewards
        for character in arena.player_characters:
            player = await self.bot.get_player(character.player_id, ctx.guild.id)
            await self.bot.log(ctx, player, ctx.author, "ARENA",
                               character=character,
                               notes=result,
                               silent=True)
            

            if (arena.completed_phases % 2 == 0 or arena.completed_phases == arena.tier.max_phases) and result == "WIN":
                await self.bot.log(ctx, player, ctx.author, "ARENA_BONUS",
                                   character=character,
                                   silent=True)
            
        await ArenaStatusEmbed(ctx, arena).update()
        await ctx.respond(embed=ArenaPhaseEmbed(ctx, arena, result))

        if arena.completed_phases >= arena.tier.max_phases or result == "LOSS":
            await arena.close()
            await ctx.respond(f"Arena closed. This channel is now free for use")
            await ctx.channel.send(CHANNEL_BREAK)

    @arena_commands.command(
        name="close",
        description="Closes out a finished arena"
    )
    async def arena_close(self, ctx: ApplicationContext):
        """
        Closes an active arena in the current channel.
        This method defers the response, retrieves the arena associated with the current channel,
        and prompts the user for confirmation to close the arena. If the user confirms, the arena
        is closed, and a message is sent to indicate that the channel is now free for use.
        Args:
            ctx (ApplicationContext): The context of the command invocation.
        Raises:
            ArenaNotFound: If no arena is found for the current channel.
        Returns:
            None
        """

        await ctx.defer()
        arena = await self.bot.get_arena(ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
           
        conf = await confirm(ctx, f"Are you sure you want to close this arena? (Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not conf:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)

        await arena.close()
        await ctx.respond(f"Arena closed. This channel is now free for use")
        await ctx.channel.send(CHANNEL_BREAK)

