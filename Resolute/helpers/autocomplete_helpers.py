import discord


async def character_class_autocomplete(ctx: discord.AutocompleteContext):
    return [c for c in list(ctx.bot.compendium.c_character_class[1].keys())
            if c.lower().startswith(ctx.value.lower())]


async def character_race_autocomplete(ctx: discord.AutocompleteContext):
    return [r for r in list(ctx.bot.compendium.c_character_race[1].keys())
            if r.lower().startswith(ctx.value.lower())]


async def character_subclass_autocomplete(ctx: discord.AutocompleteContext):
    picked_class = ctx.options["character_class"]
    if picked_class is None:
        return []
    char_class = ctx.bot.compendium.get_object("c_character_class", picked_class)
    return [s.value for s in list(ctx.bot.compendium.c_character_subclass[0].values()) if s.parent == char_class.id
            and (s.value.lower().startswith(ctx.value.lower())
                 or ctx.value.lower() in s.value.lower())]


async def character_subrace_autocomplete(ctx: discord.AutocompleteContext):
    picked_race = ctx.options["character_race"]
    if picked_race is None:
        return []
    char_race = ctx.bot.compendium.get_object("c_character_race", picked_race)

    return [s.value for s in list(ctx.bot.compendium.c_character_subrace[0].values()) if s.parent == char_race.id
            and (s.value.lower().startswith(ctx.value.lower())
                 or ctx.value.lower() in s.value.lower())]


async def faction_autocomplete(ctx: discord.AutocompleteContext):
    slist = [c for c in list(ctx.bot.compendium.c_faction[1].keys())]
    slist.remove("Guild Initiate")
    # slist.remove("Guild Member")
    slist.append("None")
    return [c for c in slist if c.lower().startswith(ctx.value.lower())
            or ctx.value.lower() in c.lower()]


async def shop_type_autocomplete(ctx: discord.AutocompleteContext):
    slist = list(ctx.bot.compendium.c_shop_type[1].keys())
    slist += [s.value for s in list(filter(lambda s: "Rune" not in s.value,
                                           list(ctx.bot.compendium.c_blacksmith_type[0].values())))]

    synonyms = [s.synonyms for s in list(ctx.bot.compendium.c_shop_type[0].values())]
    for s in synonyms:
        for v in s:
            if v.lower() not in [x.lower() for x in slist]:
                slist.append(v)
    slist.sort()
    return [s for s in slist if s.lower().startswith(ctx.value.lower())]


async def shop_create_type_autocomplete(ctx: discord.AutocompleteContext):
    slist = list(ctx.bot.compendium.c_shop_type[1].keys())
    slist.sort()
    return [s for s in slist if s.lower().startswith(ctx.value.lower())]

async def upgrade_autocomplete(ctx: discord.AutocompleteContext):
    slist = ['Shelf', 'Network', 'Mastery']

    return slist


async def item_autocomplete(ctx: discord.AutocompleteContext):
    slist = list(ctx.bot.compendium.blacksmith[1].keys())
    slist += list(ctx.bot.compendium.wondrous[1].keys())
    slist += list(ctx.bot.compendium.consumable[1].keys())
    slist += list(ctx.bot.compendium.scroll[1].keys())
    slist.sort()
    return [s for s in slist if s.lower().startswith(ctx.value.lower()) or
            ctx.value.lower() in s.lower()]


async def global_mod_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_global_modifier[1].keys())


async def global_host_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_host_status[1].keys())

async def rarity_autocomplete(ctx: discord.AutocompleteContext):
    return list(ctx.bot.compendium.c_rarity[1].keys())