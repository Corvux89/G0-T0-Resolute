from typing import Optional, List

import discord
from discord import ApplicationContext, Member, Bot, Role

from Resolute.compendium import Compendium
from Resolute.bot import G0T0Bot
from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, PlayerGuild, LevelCaps, CharacterStarship
from Resolute.models.schemas import CharacterSchema, PlayerCharacterClassSchema, CharacterStarshipSchema, LogSchema, AdventureSchema
from Resolute.queries import *


async def manage_player_roles(ctx: ApplicationContext, member: Member, character: PlayerCharacter, reason: Optional[str]):
    acolyte_role = discord.utils.get(ctx.guild.roles, name="Acolyte")
    citizen_role = discord.utils.get(ctx.guild.roles, name="Citizen")
    if not acolyte_role or not citizen_role:
        return
    elif character.level < 3 and (acolyte_role not in member.roles) and (citizen_role not in member.roles):
        await member.add_roles(acolyte_role, reason=reason)
    elif character.level >= 3:
        if acolyte_role in member.roles:
            await member.remove_roles(acolyte_role, reason=reason)

        if citizen_role not in member.roles:
            await member.add_roles(citizen_role, reason=reason)


async def get_character_quests(bot: Bot, character: PlayerCharacter) -> PlayerCharacter:
    """
    Gets the Level 1 / 2 required first step quests

    :param bot: Bot
    :param character: PlayerCharacter
    :return: Update PlayerCharacter
    """

    async with bot.db.acquire() as conn:
        rp_list = await conn.execute(
            get_log_by_player_and_activity(character.id, bot.compendium.get_object("c_activity", "RP").id))
        arena_list = await conn.execute(
            get_log_by_player_and_activity(character.id,
                                           bot.compendium.get_object("c_activity", "ARENA").id))
        arena_host_list = await conn.execute(get_log_by_player_and_activity(character.id,
                                                                            bot.compendium.get_object("c_activity",
                                                                                                      "ARENA_HOST").id))

    rp_count = rp_list.rowcount
    arena_count = arena_list.rowcount + arena_host_list.rowcount

    character.completed_rps = rp_count if character.level == 1 else rp_count - 1 if rp_count > 0 else 0
    character.needed_rps = 1 if character.level == 1 else 2
    character.completed_arenas = arena_count if character.level == 1 else arena_count - 1 if arena_count > 0 else 0
    character.needed_arenas = 1 if character.level == 1 else 2

    return character


async def get_character(bot: Bot, player_id: int, guild_id: int) -> PlayerCharacter | None:
    """
    Retrieves the given players active character on the server

    :param bot: Bot
    :param player_id: Character Member ID
    :param guild_id: guild_id
    :return: PlayerCharacter if found, else None
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_active_character(player_id, guild_id))
        row = await results.first()

    if row is None:
        return None
    else:
        character: PlayerCharacter = CharacterSchema(bot.compendium).load(row)
        return character

async def get_all_player_characters(bot: G0T0Bot, player_id: int, guild_id: int) -> []:
    characters = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_all_characters(player_id, guild_id)):
            if row is not None:
                character: PlayerCharacter = CharacterSchema(bot.compendium).load(row)
                characters.append(character)

    return characters


async def get_character_from_char_id(bot: Bot, char_id: int) -> PlayerCharacter | None:
    """
    Retrieves the given PlayerCharacter

    :param bot: Bot
    :param char_id: Character ID
    :return: PlayerCharacter if found, else None
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_character_from_id(char_id))
        row = await results.first()

    if row is None:
        return None

    character: PlayerCharacter = CharacterSchema(bot.compendium).load(row)
    return character


async def get_player_character_class(bot: Bot, char_id: int) -> List[PlayerCharacterClass] | None:
    """
    Gets all of a given Playercharacter's PlayerCharacterClasses

    :param bot: Bot
    :param char_id: Character ID
    :return: List[PlayercharacterClass] if found, else None
    """
    class_ary = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_character_class(char_id)):
            if row is not None:
                char_class: PlayerCharacterClass = PlayerCharacterClassSchema(bot.compendium).load(row)
                class_ary.append(char_class)

    if len(class_ary) == 0:
        return None
    else:
        return class_ary


async def get_player_starships(bot: Bot, char_id: int) -> List[CharacterStarship] | None:
    ship_ary = []

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_character_starships(char_id)):
            if row is not None:
                ship: CharacterStarship = CharacterStarshipSchema(bot.compendium).load(row)
                ship_ary.append(ship)

    if len(ship_ary) == 0:
        return None
    else:
        return ship_ary


async def get_player_starship_from_transponder(bot: Bot, transponder: str) -> CharacterStarship | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_starship_by_transponder(transponder))
        row = await results.first()

    if row is None:
        return None
    else:
        c_ship: CharacterStarship = CharacterStarshipSchema(bot.compendium).load(row)
        return c_ship



def get_level_cap(character: PlayerCharacter, guild: PlayerGuild, compendium: Compendium,
                  adjust: bool = True) -> LevelCaps:
    cap: LevelCaps = compendium.get_object("c_level_caps", character.level)
    return_cap = LevelCaps(cap.id, cap.max_cc)

    # Adjustment
    if adjust:
        if character.level < guild.max_level - 100:
            return_cap.max_cc = cap.max_cc * 2

    return return_cap

async def get_character_stats(bot: G0T0Bot, character: PlayerCharacter, stats_ary: [] = []):
    stats = {"total": 0,
             "adventures": [],
             "cc_add": 0,
             "cc_minus": 0,
             "cc_init": 0,
             "char": character}

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_player_logs(character.id)):
            if row is not None:
                log: DBLog = LogSchema(bot.compendium).load(row)
                stats["total"] += 1
                if log.activity.value != "NEW_CHARACTER":
                    if log.cc > 0:
                        stats["cc_add"] += log.cc
                    else:
                        stats["cc_minus"] += log.cc

                    if log.adventure_id:
                        a = await conn.execute(get_adventure_by_id(log.adventure_id))
                        a = await a.first()
                        adventure: Adventure = AdventureSchema(bot.compendium).load(a)
                        if adventure.id not in [x.id for x in stats["adventures"]]:
                            stats["adventures"].append(adventure)
                else:
                    stats["cc_init"] = log.cc

                if character.freeroll_from:
                    old_char: PlayerCharacter = await get_character_from_char_id(bot, character.freeroll_from)
                    await get_character_stats(bot, old_char, stats_ary)
        stats_ary.append(stats)
        stats_ary.sort(key=lambda x: x['char'].active, reverse=True)
        return