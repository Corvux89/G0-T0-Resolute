import discord


async def character_class_autocomplete(ctx: discord.AutocompleteContext):
    return [c for c in list(ctx.bot.compendium.c_character_class[1].keys())
            if c.lower().startswith(ctx.value.lower())]


async def character_species_autocomplete(ctx: discord.AutocompleteContext):
    return [r for r in list(ctx.bot.compendium.c_character_species[1].keys())
            if r.lower().startswith(ctx.value.lower())]


async def character_archetype_autocomplete(ctx: discord.AutocompleteContext):
    picked_class = ctx.options["character_class"]
    if picked_class is None:
        return []
    char_class = ctx.bot.compendium.get_object("c_character_class", picked_class)
    return [s.value for s in list(ctx.bot.compendium.c_character_archetype[0].values()) if s.parent == char_class.id
            and (s.value.lower().startswith(ctx.value.lower())
                 or ctx.value.lower() in s.value.lower())]


async def global_mod_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_global_modifier[1].keys())


async def global_host_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_host_status[1].keys())

async def rarity_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_rarity[1].keys())

async def starship_size_autocomplete(ctx: discord.AutocompleteContext):
    return [s for s in list(ctx.bot.compendium.c_starship_size[1].keys())
            if s.lower().startswith(ctx.value.lower())]

async def starship_role_autocomplete(ctx: discord.AutocompleteContext):
    size = ctx.bot.compendium.get_object("c_starship_size", ctx.options["ship_size"])
    return [s.value for s in list(ctx.bot.compendium.c_starship_role[0].values()) if s.size == size.id
            and (s.value.lower().startswith(ctx.value.lower()) or ctx.value.lower() in s.value.lower())]