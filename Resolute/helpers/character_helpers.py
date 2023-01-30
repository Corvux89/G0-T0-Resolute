from typing import Optional, List

import discord
from discord import ApplicationContext, Member, Bot, Role

from ProphetBot.compendium import Compendium
from ProphetBot.models.db_objects import PlayerCharacter, PlayerCharacterClass, PlayerGuild, LevelCaps
from ProphetBot.models.schemas import CharacterSchema, PlayerCharacterClassSchema
from ProphetBot.queries import get_log_by_player_and_activity, get_active_character, get_character_class, \
    get_character_from_id


async def remove_fledgling_role(ctx: ApplicationContext, member: Member, reason: Optional[str]):
    """
    Removes the Fledgling role from the given member

    :param ctx: Context
    :param member: Member to remove the role from
    :param reason: Reason in the audit to remove the role
    """
    fledgling_role = discord.utils.get(ctx.guild.roles, name="Fledgling")
    initiate_role = discord.utils.get(ctx.guild.roles, name="Guild Initiate")
    if fledgling_role and (fledgling_role in member.roles):
        await member.remove_roles(fledgling_role, reason=reason)

        if initiate_role and not(initiate_role in member.roles):
            await member.add_roles(initiate_role, reason=reason)


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
                                                                            bot.compendium.get_object("c_activity", "ARENA_HOST").id))

    rp_count = rp_list.rowcount
    arena_count = arena_list.rowcount + arena_host_list.rowcount

    character.completed_rps = rp_count if character.get_level() == 1 else rp_count - 1 if rp_count > 0 else 0
    character.needed_rps = 1 if character.get_level() == 1 else 2
    character.completed_arenas = arena_count if character.get_level() == 1 else arena_count - 1 if arena_count > 0 else 0
    character.needed_arenas = 1 if character.get_level() == 1 else 2

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


def get_faction_roles(compendium: Compendium, player: Member) -> List[Role] | None:
    """
    Get the associated roles for all factions excluding Guild Member

    :param compendium: Compendium
    :param player: Member
    :return: List[Roles] if found, else None
    """
    faction_names = [f.value for f in list(compendium.c_faction[0].values())]
    faction_names.remove("Guild Member")

    roles = list(filter(lambda r: r.name in faction_names, player.roles))

    if len(roles) == 0:
        return None
    return roles


def get_level_cap(character: PlayerCharacter, guild: PlayerGuild, compendium: Compendium, adjust: bool=True) -> LevelCaps:
    cap: LevelCaps = compendium.get_object("c_level_caps", character.get_level())
    return_cap = LevelCaps(cap.id, cap.max_gold, cap.max_xp)

    # Adjustment
    if adjust:
        if character.get_level() < guild.max_level - 2:
            return_cap.max_gold = cap.max_gold * 2
            return_cap.max_xp = cap.max_xp * 2

    return return_cap
