import asyncio
import bisect
import discord
import logging

from statistics import mode
from datetime import datetime, timezone

from Resolute.bot import G0T0Bot
from Resolute.helpers.characters import get_character
from Resolute.helpers.general_helpers import confirm, get_positivity
from Resolute.helpers.guilds import get_guild
from Resolute.models.categories import ArenaTier
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.arenas import ArenaStatusEmbed
from Resolute.models.objects.arenas import Arena, ArenaPost, ArenaSchema, get_arena_by_channel_query, get_arena_by_host_query, get_character_arena_query, upsert_arena_query
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def get_arena(bot: G0T0Bot, channel_id: int) -> Arena:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_arena_by_channel_query(channel_id))
        row = await results.first()

    if row is None:
        return None
    
    arena: Arena = ArenaSchema(bot.compendium).load(row)

    if arena.characters:
        arena.player_characters = await asyncio.gather(*(get_character(bot, c) for c in arena.characters))

    return arena

async def upsert_arena(bot: G0T0Bot, arena: Arena) -> Arena:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_arena_query(arena))
        row = await results.first()

    if row is None:
        return None
    
    arena = ArenaSchema(bot.compendium).load(row)

    return arena

async def add_player_to_arena(bot: G0T0Bot, interaction: discord.Interaction, player: Player, character: PlayerCharacter, arena: Arena) -> None:
    if character.id in arena.characters:
        return await interaction.response.send_message(embed=ErrorEmbed(description="Character already in the arena"), ephemeral=True)    
    if player.id in {c.player_id for c in arena.player_characters}:
        remove_char = next((c for c in arena.player_characters if c.player_id == player.id), None)
        arena.player_characters.remove(remove_char)
        arena.characters.remove(remove_char.id)

    await interaction.guild.get_member(player.id).add_roles(interaction.guild.get_role(arena.role_id))
    await remove_arena_board_post(interaction, player)
    await interaction.response.send_message(f"{interaction.guild.get_member(player.id).mention} has joined the arena with {character.name}!")

    arena.characters.append(character.id)
    arena.player_characters.append(character)
    update_arena_tier(bot, arena)

    await upsert_arena(bot, arena)
    await update_arena_view_embed(interaction, arena)

async def update_arena_view_embed(interaction: discord.Interaction | discord.ApplicationContext, arena: Arena) -> None:
    message: discord.Message = await interaction.channel.fetch_message(arena.pin_message_id)
    embed = ArenaStatusEmbed(interaction, arena)

    if message:
        await message.edit(embed=embed)


async def remove_arena_board_post(ctx: discord.ApplicationContext | discord.Interaction, player: Player) -> None:
    def predicate(message):
        return message.author == ctx.guild.get_member(player.id)
    
    if arena_board := discord.utils.get(ctx.guild.channels, name="arena-board"):
        try:
            deleted_message = await arena_board.purge(check=predicate)
            log.info(f"{len(deleted_message)} message{'s' if len(deleted_message)>1 else ''} by {ctx.guild.get_member(player.id).name} deleted from #{arena_board.name}")
        except Exception as error:
            if isinstance(error, discord.errors.HTTPException):
                await ctx.send(f'Warning: deleting users\'s post(s) from {arena_board.mention} failed')
            else:
                log.error(error)

def update_arena_tier(bot: G0T0Bot, arena: Arena) -> None:
    if arena.player_characters:
        avg_level = mode(c.level for c in arena.player_characters)
        tier = bisect.bisect([t.avg_level for t in list(bot.compendium.arena_tier[0].values())], avg_level)
        arena.tier = bot.compendium.get_object(ArenaTier, tier)

async def close_arena(bot: G0T0Bot, arena: Arena, arena_role: discord.Role):
    for member in arena_role.members:
        await member.remove_roles(arena_role, reason="Arena Complete")

    arena.end_ts = datetime.now(timezone.utc)

    await upsert_arena(bot, arena)

    channel = await bot.fetch_channel(arena.channel_id)

    msg: discord.Message = await channel.fetch_message(arena.pin_message_id)

    if msg:
        await msg.delete(reason="Closing arena")

async def get_player_arenas(bot: G0T0Bot, player: Player) -> list[Arena]:
    arenas = []
    rows =[]

    async with bot.db.acquire() as conn:
        host_arenas = await conn.execute(get_arena_by_host_query(player.id))
        rows = await host_arenas.fetchall()

    for character in player.characters:
        async with bot.db.acquire() as conn:
            player_arenas = await conn.execute(get_character_arena_query(character.id))
            rows.extend(await player_arenas.fetchall())

    arenas.extend(ArenaSchema(bot.compendium).load(row) for row in rows)
    
    return arenas

async def build_arena_post(ctx: discord.ApplicationContext | discord.Interaction, bot: G0T0Bot, post: ArenaPost) -> bool:
    g = await get_guild(bot, post.player.guild_id)

    content_message = await confirm(ctx, "What do you want to post on the board?", True, bot, None, True)  

    if not content_message or content_message.content == "" or get_positivity(content_message.content) == False:
            return await ctx.respond(f"Request cancelled!", ephemeral=True)
    
    post.content = content_message.content

    if g.arena_board:
        guild_member = g.guild.get_member(post.player.id)
        webhook = await g.arena_board.create_webhook(name=guild_member.name)
        for char in post.characters:
            await webhook.send(content_message.content, username=f"[{char.level}] {char.name} ({guild_member.display_name})", avatar_url=guild_member.display_avatar.url)
        await webhook.delete()
        return True
    return False

    

