import logging

import discord
from discord import ApplicationContext, Option
from discord.commands import SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import CHANNEL_BREAK
from Resolute.helpers import (add_player_to_arena, build_arena_post,
                              close_arena, confirm, create_log, get_arena,
                              get_guild, get_player, get_player_arenas,
                              update_arena_tier, update_arena_view_embed,
                              upsert_arena)
from Resolute.models.categories import ArenaTier, ArenaType
from Resolute.models.embeds.arenas import ArenaPhaseEmbed, ArenaStatusEmbed
from Resolute.models.objects.arenas import Arena, ArenaPost
from Resolute.models.objects.exceptions import (ArenaNotFound,
                                                CharacterNotFound, G0T0Error,
                                                RoleNotFound)
from Resolute.models.views.arena_view import (ArenaCharacterSelect,
                                              ArenaRequestCharacterSelect,
                                              CharacterArenaViewUI)

log = logging.getLogger(__name__)

def setup(bot):
    bot.add_cog(Arenas(bot))


class Arenas(commands.Cog):
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    arena_commands = SlashCommandGroup("arena", "Commands for arenas!", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Arenas\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        self.bot.add_view(CharacterArenaViewUI.new(self.bot))
        self.bot.add_view(ArenaCharacterSelect(self.bot))


    @commands.slash_command(
            name="arena_request",
            description="Request to join an arena"
    )
    async def arena_request(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if len(player.characters) == 0:
            raise CharacterNotFound(ctx.author)
        elif len(player.characters) == 1:
            await ctx.defer()
            arenas = await get_player_arenas(self.bot, player)

            for arena in arenas:
                if player.characters[0].id in arena.characters and arena.completed_phases < arena.tier.max_phases-1:
                    return await ctx.respond(f"Character already in a new arena.", ephemeral=True)

            post = ArenaPost(player, player.characters)
            if await build_arena_post(ctx, self.bot, post):
                return await ctx.respond(f"Request submitted!", ephemeral=True)
        else:
            ui = ArenaRequestCharacterSelect.new(self.bot, ctx.author, player)
            await ui.send_to(ctx)
            return await ctx.delete()
        
        raise G0T0Error("Something went wrong")
        

    @arena_commands.command(
        name="claim",
        description="Opens an arena in this channel and sets you as host"
    )
    async def arena_claim(self, ctx: ApplicationContext):
        await ctx.defer()

        arena: Arena = await get_arena(self.bot, ctx.channel_id)

        if arena:
            raise G0T0Error(f"{ctx.channel.mention} is already in use\n"
                            "Use `/arena status` to check on the status of the current arena in this channel")
        
        if channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
            await ctx.author.add_roles(channel_role, reason=f"Claiming {ctx.channel.name}")
            tier = self.bot.compendium.get_object(ArenaTier, 1)
            type = self.bot.compendium.get_object(ArenaType, "CHARACTER")

            arena = Arena(ctx.channel.id, channel_role.id, ctx.author.id, tier, type)

            ui = CharacterArenaViewUI.new(self.bot)
            embed = ArenaStatusEmbed(ctx, arena)

            message: discord.WebhookMessage = await ui.send_to(ctx, embed=embed)

            arena.pin_message_id = message.id

            await upsert_arena(self.bot, arena)

            await ctx.delete()
        else:
            raise RoleNotFound(ctx.channel.name)
        

    @arena_commands.command(
        name="status",
        description="Shows the current status of this arena."
    )
    async def arena_status(self, ctx: ApplicationContext):
        await ctx.defer()
        arena = await get_arena(self.bot, ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        elif channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
            embed=ArenaStatusEmbed(ctx, arena)
            await update_arena_view_embed(ctx, arena)
            return await ctx.respond(embed=embed)
        else:
            raise RoleNotFound(ctx.channel.name)

    @arena_commands.command(
        name="add",
        description="Adds the specified player to this arena"
    )
    async def arena_add(self, ctx: ApplicationContext,
                        member: Option(discord.SlashCommandOptionType(6), description="Player to add to arena", required=True)):
        arena = await get_arena(self.bot, ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        elif channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
            if member.id == arena.host_id:
                raise G0T0Error("Cannot add the host to an arena")

            player = await get_player(self.bot, member.id, ctx.guild.id)

            if not player.characters:
                raise CharacterNotFound(member)
            elif len(player.characters) == 1:
                await add_player_to_arena(self.bot, ctx, player, player.characters[0], arena)
            else:
                ui = ArenaCharacterSelect.new(self.bot, player, ctx.author.id)
                await ui.send_to(ctx)
                await ctx.delete()
        else:
            raise RoleNotFound(ctx.channel.name)

    @arena_commands.command(
        name="remove",
        description="Removes the specified player from this arena"
    )
    async def arena_remove(self, ctx: ApplicationContext,
                           member: Option(discord.SlashCommandOptionType(6), description="Player to remove from arena", required=True)):
        arena = await get_arena(self.bot, ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        elif channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
            if member.id == arena.host_id:
                raise G0T0Error("Cannot add the host to an arena")
            
            remove_char = next((c for c in arena.player_characters if c.player_id == member.id), None)
            if remove_char:
                arena.player_characters.remove(remove_char)
                arena.characters.remove(remove_char.id)
                await member.remove_roles(channel_role)

                if arena.completed_phases == 0:
                    update_arena_tier(self.bot, arena)
                
                await upsert_arena(self.bot, arena)
                await update_arena_view_embed(ctx, arena)                
                return await ctx.respond(f"{member.mention} has been removed from the arena.")
            else:
                raise G0T0Error(f"{member.mention} is not an arena participant")
        else:
            raise RoleNotFound(ctx.channel.name)

    @arena_commands.command(
        name="phase",
        description="Records the outcome of an arena phase"
    )
    async def arena_phase(self, ctx: ApplicationContext,
                          result: Option(str, description="The result of the phase", required=True,
                                         choices=["WIN", "LOSS"])):
        
        arena = await get_arena(self.bot, ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        elif channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
            arena.completed_phases += 1
            await upsert_arena(self.bot, arena)

            # Host Log
            host = await get_player(self.bot, arena.host_id, ctx.guild.id)
            await create_log(self.bot, ctx.author, "ARENA_HOST", host)
            arena.players.append(host)

            # Rewards
            for character in arena.player_characters:
                player = await get_player(self.bot, character.player_id, ctx.guild.id)
                await create_log(self.bot, ctx.author, "ARENA", player,
                                 character=character, notes=result)
                arena.players.append(player)

                if (arena.completed_phases % 2 == 0 or arena.completed_phases == arena.tier.max_phases) and result == "WIN":
                    await create_log(self.bot, ctx.author, "ARENA_BONUS", player,
                                     character=character)
                
            await update_arena_view_embed(ctx, arena)
            await ctx.respond(embed=ArenaPhaseEmbed(ctx, arena, result))

            if arena.completed_phases >= arena.tier.max_phases or result == "LOSS":
                await close_arena(self.bot, arena, channel_role)
                await ctx.respond(f"Arena closed. This channel is now free for use")
                await ctx.channel.send(CHANNEL_BREAK)

        else:
            raise RoleNotFound(ctx.channel.name)

    @arena_commands.command(
        name="close",
        description="Closes out a finished arena"
    )
    async def arena_close(self, ctx: ApplicationContext):
        await ctx.defer()
        arena = await get_arena(self.bot, ctx.channel.id)

        if arena is None:
            raise ArenaNotFound()
        elif channel_role := discord.utils.get(ctx.guild.roles, name=ctx.channel.name):
           
            conf = await confirm(ctx, f"Are you sure you want to close this arena? (Reply with yes/no)", True)

            if conf is None:
                return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
            elif not conf:
                return await ctx.respond(f'Ok, cancelling.', delete_after=10)

            await close_arena(self.bot, arena, channel_role)
            await ctx.respond(f"Arena closed. This channel is now free for use")
            await ctx.channel.send(CHANNEL_BREAK)
        else:
           raise RoleNotFound(ctx.channel.name)

