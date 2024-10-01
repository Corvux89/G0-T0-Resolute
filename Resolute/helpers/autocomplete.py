import discord

from Resolute.helpers.players import get_player


async def get_characters_autocomplete(ctx: discord.AutocompleteContext):
    player = await get_player(ctx.bot, ctx.interaction.user.id, ctx.interaction.guild.id if ctx.interaction.guild else None)

    return [c.name for c in player.characters] or []
