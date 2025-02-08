import discord

async def get_faction_autocomplete(ctx: discord.AutocompleteContext) -> list[str]:
    """
    Fetches a list of faction names for autocomplete suggestions.
    Args:
        ctx (discord.AutocompleteContext): The context for the autocomplete interaction.
    Returns:
        list[str]: A list of faction names.
    """
    factions = ctx.bot.compendium.faction[0].values()

    return [f.value for f in factions] or []

async def get_arena_type_autocomplete(ctx: discord.AutocompleteContext) -> list[str]:
    """
    Fetches a list of arena types for autocomplete suggestions.
    This asynchronous function retrieves arena types from the bot's compendium
    and formats them for use in autocomplete suggestions.
    Args:
        ctx (discord.AutocompleteContext): The context in which the autocomplete is being requested.
    Returns:
        list[str]: A list of arena type values for autocomplete suggestions.
    """
    types = ctx.bot.compendium.arena_type[0].values()

    return [f.value for f in types] or []
