import asyncio
import logging

import discord
from discord import Embed, Member, Color
from discord.commands import SlashCommandGroup, Option
from discord.commands.context import ApplicationContext
from discord.ext import commands

from ProphetBot.bot import BpBot
from ProphetBot.helpers import get_arena, get_character, add_player_to_arena, update_arena_tier, create_logs, \
    update_arena_status, end_arena, confirm
from ProphetBot.models.db_objects import Arena, PlayerCharacter, Activity
from ProphetBot.models.embeds import ArenaStatusEmbed, ArenaPhaseEmbed
from ProphetBot.models.schemas import CharacterSchema
from ProphetBot.models.views.entity_view import ArenaView
from ProphetBot.queries import insert_new_arena, get_multiple_characters, update_arena

log = logging.getLogger(__name__)

def setup(bot):
    bot.add_cog(Arenas(bot))


class Arenas(commands.Cog):
    bot: BpBot  # Typing annotation for my IDE's sake
    arena_commands = SlashCommandGroup("arena", "Commands for arenas!")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Arenas\' loaded')

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(3.0)
        self.bot.add_view(ArenaView(self.bot.db))

    @arena_commands.command(
        name="claim",
        description="Opens an arena in this channel and sets you as host"
    )
    async def arena_claim(self, ctx: ApplicationContext):
        """
        Claims an arena TextChannel, and sets the user as the Host applying the arena role

        :param ctx: Context
        """
        await ctx.defer()

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)
        character: PlayerCharacter = await get_character(ctx.bot, ctx.author.id, ctx.guild_id)

        if arena is not None:
            return await ctx.respond(f"Error: {ctx.channel.mention} already in use.\n"
                                     f"User `/arena status` to check the current status of this room.")
        elif character is None:
            return await ctx.respond(f"Error: Hosts needs to have a character too")
        else:
            if not (channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name)):
                return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist. \n"
                                         f"A Council member may need to create it")
            else:
                await ctx.author.add_roles(channel_role, reason=f"Claiming {ctx.channel.name}")

                tier = ctx.bot.compendium.get_object("c_arena_tier", 1)

                arena = Arena(channel_id=ctx.channel_id, role_id=channel_role.id, host_id=ctx.author.id,
                              tier=tier, completed_phases=0)

                embed = ArenaStatusEmbed(ctx, arena)

                msg: discord.WebhookMessage = await ctx.respond(embed=embed,
                                                                view=ArenaView(db=ctx.bot.db))

                arena.pin_message_id = msg.id

                async with ctx.bot.db.acquire() as conn:
                    await conn.execute(insert_new_arena(arena))

                await msg.pin(reason=f"Arena claimed by {ctx.author.name}")

    @arena_commands.command(
        name="status",
        description="Shows the current status of this arena."
    )
    async def arena_status(self, ctx: ApplicationContext):
        """
        Shows the current status of the arena the command is in.

        :param ctx: Context
        """
        await ctx.defer()

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)

        if arena is None:
            embed = Embed(title=f"{ctx.channel.name} Free",
                          description=f"There is no active arena in this channel. If you're a host, you can use"
                                      f"`/arena claim` to start an arena here",
                          color=Color.random())
            return await ctx.respond(embed=embed, ephemeral=False)
        elif not (channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name)):
            return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist."
                                     f"A Council member may need to create it", ephemeral=False)
        embed = ArenaStatusEmbed(ctx, arena)

        await ctx.respond(embed=embed, ephemeral=False)

    @arena_commands.command(
        name="add",
        description="Adds the specified player to this arena"
    )
    async def arena_add(self, ctx: ApplicationContext,
                        player: Option(Member, description="Player to add to arena", required=True)):
        """
        Adds a specified player to the current arena
        :param ctx: Context
        :param player: Member
        """

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)

        if arena is None:
            return await ctx.respond(f"Error: No active arena present in this channel", ephemeral=True)
        elif not (channel_role := discord.utils.get(ctx.guild.roles, id=arena.role_id)):
            return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist. "
                                     f"A Council member may need to create it", ephemeral=True)
        elif player.id == arena.host_id:
            return await ctx.respond(f"Error: {player.mention} is the host of the arena.")
        elif player in channel_role.members:
            return await ctx.respond(f"Error: {player.mention} is already a participant in this arena.")
        else:
            await add_player_to_arena(ctx.interaction, player, arena, ctx.bot.db, ctx.bot.compendium)

    @arena_commands.command(
        name="remove",
        description="Removes the specified player from this arena"
    )
    async def arena_remove(self, ctx: ApplicationContext,
                           player: Option(Member, description="Player to remove from arena", required=True)):
        """
        Removes a specified player from the current arena

        :param ctx: Context
        :param player: Member
        """
        await ctx.defer()

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)

        if arena is None:
            return await ctx.respond(f"Error: No active arena present in this channel", ephemeral=True)
        elif not (channel_role := discord.utils.get(ctx.guild.roles, id=arena.role_id)):
            return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist. "
                                     f"A Council member may need to create it", ephemeral=True)
        elif player not in channel_role.members:
            return await ctx.respond(f"Error: {player.mention} is not a participant in this arena.", ephemeral=True)
        else:
            await player.remove_roles(channel_role)

            # Recalculate tier if arena hasn't started
            if arena.completed_phases == 0:
                await update_arena_tier(ctx.interaction, ctx.bot.db, arena, ctx.bot.compendium)

            await update_arena_status(ctx, arena)

            await ctx.respond(f"{player.mention} has been removed from the arena.")

    @arena_commands.command(
        name="phase",
        description="Records the outcome of an arena phase"
    )
    async def arena_phase(self, ctx: ApplicationContext,
                          result: Option(str, description="The result of the phase", required=True,
                                         choices=["WIN", "LOSS"])):
        """
        Logs the outcome of an arena phase

        :param ctx: Context
        :param result: Result of the arena
        """
        await ctx.defer()

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)

        if arena is None:
            return await ctx.respond(f"Error: No active arena present in this channel", ephemeral=True)
        elif not (channel_role := discord.utils.get(ctx.guild.roles, id=arena.role_id)):
            return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist. "
                                     f"A Council member may need to create it", ephemeral=True)
        else:
            arena.completed_phases += 1

            players = [p.id for p in list(set(filter(lambda p: p.id != arena.host_id,
                                                     channel_role.members)))]
            chars = []
            arena_act: Activity = ctx.bot.compendium.get_object("c_activity", "ARENA")
            host_act: Activity = ctx.bot.compendium.get_object("c_activity", "ARENA_HOST")
            bonus_act: Activity = ctx.bot.compendium.get_object("c_activity", "ARENA_BONUS")
            host_char: PlayerCharacter = await get_character(ctx.bot, arena.host_id, ctx.guild_id)

            # Get player characters
            async with ctx.bot.db.acquire() as conn:
                await conn.execute(update_arena(arena))
                async for row in await conn.execute(get_multiple_characters(players, ctx.guild_id)):
                    if row is not None:
                        character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)
                        chars.append(character)

            # Rewards:
            await create_logs(ctx, host_char, host_act, host_act.value)
            for c in chars:
                await create_logs(ctx, c, arena_act, result)

                if arena.completed_phases - 1 >= (arena.tier.max_phases / 2) and result == "WIN":
                    await create_logs(ctx, c, bonus_act, bonus_act.value)

            embed = ArenaPhaseEmbed(ctx, arena, result)

            await ctx.respond(embed=embed)

            await update_arena_status(ctx, arena)

            if arena.completed_phases >= arena.tier.max_phases or result == "LOSS":
                await end_arena(ctx, arena)

    @arena_commands.command(
        name="close",
        description="Closes out a finished arena"
    )
    async def arena_close(self, ctx: ApplicationContext):
        """
        Manually closes an arena

        :param ctx: Context
        """
        await ctx.defer()

        arena: Arena = await get_arena(ctx.bot, ctx.channel_id)

        to_end = await confirm(ctx, "Are you sure you want to close this arena? (Reply with yes/no)", True)

        if to_end is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not to_end:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)


        if arena is None:
            return await ctx.respond(f"Error: No active arena present in this channel", ephemeral=True)
        elif not (channel_role := discord.utils.get(ctx.guild.roles, id=arena.role_id)):
            return await ctx.respond(f"Error: Role @{ctx.channel.name} doesn't exist. "
                                     f"A Council member may need to create it", ephemeral=True)
        await end_arena(ctx, arena)
