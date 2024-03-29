import bisect
import re
import random
from datetime import datetime
from statistics import mode

import aiopg
import discord
from discord import ApplicationContext, Member, Role, Bot, Client

from Resolute.compendium import Compendium
from Resolute.models.db_objects import PlayerGuild, PlayerCharacter, Adventure, Arena, DiscordPlayer
from Resolute.models.embeds import ArenaStatusEmbed, StarshipArenaStatusEmbed
from Resolute.models.schemas import GuildSchema, CharacterSchema, AdventureSchema, ArenaSchema, DiscordPlayerSchema
from Resolute.queries import get_guild, insert_new_guild, get_adventure_by_category_channel_id, \
    get_arena_by_channel, get_multiple_characters, update_arena, get_adventure_by_role_id, get_characters, \
    get_logs_in_past, get_discord_player_query, insert_new_discord_player


async def get_or_create_guild(db: aiopg.sa.Engine, guild_id: int) -> PlayerGuild:
    """
    Retrieves the PlayerGuild object for the current server, or will create a shell object if not found

    :param db: DB Engine
    :param guild_id:  Guild ID
    :return: PlayerGuild
    """
    async with db.acquire() as conn:
        results = await conn.execute(get_guild(guild_id))
        g_row = await results.first()

    if g_row is None:
        g = PlayerGuild(id=guild_id, max_level=3, weeks=0, max_reroll=1)

        async with db.acquire() as conn:
            results = await conn.execute(insert_new_guild(g))
            g_row = await results.first()

    g: PlayerGuild = GuildSchema().load(g_row)

    return g


async def update_dm(dm: Member, category_permissions: dict, role: Role, adventure_name: str,
                    remove: bool = False) -> dict:
    """
    Adds/removes a DM from an adventure

    :param dm: Member to add/remove
    :param category_permissions: PermissionOverWrite
    :param role: Role of the Adventure
    :param adventure_name: Name of the adventure for audit purposes
    :param remove: True to remove dm, otherwise add the dm
    :return: Updated PermissionOverwrite dict
    """
    if remove:
        await dm.remove_roles(role, reason=f"Removed from adventure {adventure_name}")
        del category_permissions[dm]
    else:
        await dm.add_roles(role, reason=f"Creating/Modifying adventure {adventure_name}")
        category_permissions[dm] = discord.PermissionOverwrite(manage_messages=True)

    return category_permissions


async def get_adventure(bot: Bot, category_id: int) -> Adventure | None:
    """
    Retrieves the Adventure for the given category_ic

    :param bot: Bot
    :param category_id: Channel Category ID of the Adventure
    :return: Adventure if found, else None
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_adventure_by_category_channel_id(category_id))
        row = await results.first()

    if row is None:
        return None
    else:
        adventure: Adventure = AdventureSchema(bot.compendium).load(row)
        return adventure


async def get_adventure_from_role(bot: Bot, role_id: int) -> Adventure | None:
    """
    Get the Adventure given the role

    :param bot: Bot
    :param role_id: Role id
    :return: Adventure if found, else None
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_adventure_by_role_id(role_id))
        row = await results.first()

    if row is None:
        return None
    else:
        adventure: Adventure = AdventureSchema(bot.compendium).load(row)
        return adventure


async def get_arena(bot: Bot | Client, channel_id: int) -> Arena | None:
    """
    Get the active Arena for the given channel

    :param bot: Bot or Client
    :param channel_id: TextChannel id to get the arena for
    :return: Arena if found, else None
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_arena_by_channel(channel_id))
        row = await results.first()

    if row is None:
        return None
    else:
        arena: Arena = ArenaSchema(bot.compendium).load(row)
        return arena


async def remove_post_from_arena_board(ctx: ApplicationContext | discord.Interaction, member: Member):
    """
    Removes a Member's post from the arena-board channel

    :param ctx: Context
    :param member: Member
    """

    def predicate(message):
        return message.author == member

    if arena_board := discord.utils.get(ctx.guild.channels, name='arena-board'):
        try:
            deleted_message = await arena_board.purge(check=predicate)
            print(f'{len(deleted_message)} messages by {member.name} deleted from #{arena_board.name}')
        except Exception as error:
            if isinstance(error, discord.errors.HTTPException):
                await ctx.send(f'Warning: deleting users\'s post(s) from {arena_board.mention} failed')
            else:
                print(error)

async def remove_post_from_starship_arena_board(ctx: ApplicationContext | discord.Interaction, member: Member):
    """
    Removes a Member's post from the arena-board channel

    :param ctx: Context
    :param member: Member
    """

    def predicate(message):
        return message.author == member

    if arena_board := discord.utils.get(ctx.guild.channels, name='flight-sim-board'):
        try:
            deleted_message = await arena_board.purge(check=predicate)
            print(f'{len(deleted_message)} messages by {member.name} deleted from #{arena_board.name}')
        except Exception as error:
            if isinstance(error, discord.errors.HTTPException):
                await ctx.send(f'Warning: deleting users\'s post(s) from {arena_board.mention} failed')
            else:
                print(error)


async def add_player_to_arena(ctx: discord.Interaction, player: Member, arena: Arena,
                              db: aiopg.sa.Engine, compendium: Compendium):
    """
    Adds a player to the Arena

    :param ctx: Context
    :param player: Member to add
    :param arena: Arena to add the player to
    :param db: Engine
    :param compendium: Compendium for category reference
    """
    await player.add_roles(arena.get_role(ctx))
    await remove_post_from_arena_board(ctx, player)

    await ctx.response.send_message(f"{player.mention} has joined the arena!", ephemeral=False)

    await update_arena_tier(ctx, db, arena, compendium)

    await update_arena_status(ctx, arena)

async def add_player_to_starship_arena(ctx: discord.Interaction, player: Member, arena: Arena,
                              db: aiopg.sa.Engine, compendium: Compendium):
    """
    Adds a player to the Arena

    :param ctx: Context
    :param player: Member to add
    :param arena: Arena to add the player to
    :param db: Engine
    :param compendium: Compendium for category reference
    """
    await player.add_roles(arena.get_role(ctx))
    await remove_post_from_starship_arena_board(ctx, player)

    await ctx.response.send_message(f"{player.mention} has joined the starship arena!", ephemeral=False)

    await update_starship_arena_status(ctx, arena)


async def update_arena_tier(ctx: discord.Interaction, db: aiopg.sa.Engine, arena: Arena, compendium: Compendium):
    """
    Recalculates and updates the arena tier

    :param ctx: Context
    :param db: Engine
    :param arena: Arena
    :param compendium: Compendium
    """
    players = [p.id for p in list(set(filter(lambda p: p.id != arena.host_id,
                                             arena.get_role(ctx).members)))]

    if len(players) > 0:
        chars = []
        async with db.acquire() as conn:
            async for row in await conn.execute(get_multiple_characters(players, ctx.guild_id)):
                if row is not None:
                    character: PlayerCharacter = CharacterSchema(compendium).load(row)
                    chars.append(character)
        if len(chars) > 0:
            avg_level = mode(c.level for c in chars)
            tier = bisect.bisect([t.avg_level for t in list(compendium.c_arena_tier[0].values())], avg_level)
            arena.tier = compendium.get_object("c_arena_tier", tier)

            async with db.acquire() as conn:
                await conn.execute(update_arena(arena))


async def update_arena_status(ctx: ApplicationContext | discord.Interaction, arena: Arena):
    """
    Updates the ArenaStatusEmbed

    :param ctx: Context
    :param arena: Arena
    """
    embed = ArenaStatusEmbed(ctx, arena)

    msg: discord.Message = await ctx.channel.fetch_message(arena.pin_message_id)

    if msg:
        await msg.edit(embed=embed)

async def update_starship_arena_status(ctx: ApplicationContext | discord.Interaction, arena: Arena):
    """
    Updates the ArenaStatusEmbed

    :param ctx: Context
    :param arena: Arena
    """
    embed = StarshipArenaStatusEmbed(ctx, arena)

    msg: discord.Message = await ctx.channel.fetch_message(arena.pin_message_id)

    if msg:
        await msg.edit(embed=embed)

async def end_arena(ctx: ApplicationContext, arena: Arena):
    """
    Ends the current arena

    :param ctx: Context
    :param arena: Arena
    """
    for member in arena.get_role(ctx).members:
        await member.remove_roles(arena.get_role(ctx), reason=f"Arena complete")

    arena.end_ts = datetime.utcnow()

    async with ctx.bot.db.acquire() as conn:
        await conn.execute(update_arena(arena))

    msg: discord.Message = await ctx.channel.fetch_message(arena.pin_message_id)

    if msg:
        await msg.delete(reason="Closing arena")

    await ctx.respond("Arena closed. This channel is now free for use")


async def get_guild_character_summary_stats(bot: Bot, guild_id: int):
    inactive = []
    chars = []
    total = 0

    async with bot.db.acquire() as conn:
        async for row in await conn.execute(get_characters(guild_id)):
            if row is not None:
                character: PlayerCharacter = CharacterSchema(bot.compendium).load(row)
                chars.append(character)
                total += 1

    if len(chars) > 0:
        for c in chars:
            async with bot.db.acquire() as conn:
                results = await conn.execute(get_logs_in_past(c.id))
                row = await results.first()

            if row is None:
                inactive.append(c)

    if len(inactive) == 0:
        inactive = None

    return total, inactive

async def get_player_adventures(bot: Bot | Client, player: Member):
    adventures = {}
    adventures['player'] = []
    adventures['dm'] = []

    for role in player.roles:
        adventure: Adventure = await get_adventure_from_role(bot, role.id)
        if adventure is not None:
            if player.id in adventure.dms:
                adventures['dm'].append(adventure)
            else:
                adventures['player'].append(adventure)

    return adventures

async def get_discord_player(bot: Bot | Client, player_id: int, guild_id: int):
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_discord_player_query(player_id, guild_id))
        p_row = await results.first()

    if p_row is None:
        p = DiscordPlayer(id=player_id, guild_id=guild_id, handicap_amount=0)

        async with bot.db.acquire() as conn:
            results = await conn.execute(insert_new_discord_player(p))
            p_row = await results.first()

    p: DiscordPlayer = DiscordPlayerSchema().load(p_row)

    return p