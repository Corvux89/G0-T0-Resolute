import discord

from Resolute.helpers import get_player


async def get_characters_autocomplete(ctx: discord.AutocompleteContext):
    player = await get_player(ctx.bot, ctx.interaction.user.id, ctx.interaction.guild.id if ctx.interaction.guild else None)

    return [c.name for c in player.characters] or []

async def get_faction_autocomplete(ctx: discord.AutocompleteContext):
    factions = ctx.bot.compendium.faction[0].values()

    return [f.value for f in factions] or []

async def get_arena_type_autocomplete(ctx: discord.AutocompleteContext):
    types = ctx.bot.compendium.arena_type[0].values()

    return [f.value for f in types] or []
