from typing import Any

from discord import ApplicationContext, Bot

from ProphetBot.helpers.entity_helpers import get_or_create_guild
from ProphetBot.helpers.character_helpers import get_level_cap
from ProphetBot.models.db_objects import PlayerCharacter, Activity, LevelCaps, PlayerGuild, DBLog, Adventure
from ProphetBot.models.schemas import LogSchema
from ProphetBot.queries import insert_new_log, update_character, update_guild, get_log_by_id


def get_activity_amount(character: PlayerCharacter, activity: Activity, cap: LevelCaps, g: PlayerGuild, gold: int,
                        xp: int):
    """
    Primary calculator for log rewards. Takes into consideration the activity, diversion limits, and applies any excess
    to the server weekly xp

    :param character: PlayerCharacter to calculate for
    :param activity: Activity to calculate for
    :param cap: LevelCap
    :param g: PlayerGuild to apply any excess to
    :param gold: Manual override
    :param xp: Manual override
    :return: Character gold, character xp, and server xp
    """
    if activity.ratio is not None:
        # Calculate the ratio unless we have a manual override
        reward_gold = cap.max_gold * activity.ratio if gold == 0 else gold
        reward_xp = cap.max_xp * activity.ratio if xp == 0 else xp
    else:
        reward_gold = gold
        reward_xp = xp

    max_xp = (g.max_level - 1) * 1000
    server_xp, char_gold, char_xp, char_div_xp = 0, 0, 0, 0

    if activity.diversion:  # Apply diversion limits
        if character.div_gold + reward_gold > cap.max_gold:
            char_gold = 0 if cap.max_gold - character.div_gold < 0 else cap.max_gold - character.div_gold
        else:
            char_gold = reward_gold

        if character.div_xp + reward_xp > cap.max_xp:
            reward_xp = 0 if cap.max_xp - character.div_xp < 0 else cap.max_xp - character.div_xp
    else:
        char_gold = reward_gold

    # Guild Server Stats
    if character.xp + reward_xp >= max_xp:
        char_xp = 0 if max_xp - character.xp + reward_xp < 0 else max_xp - character.xp
        char_div_xp = 0 if cap.max_xp - character.div_xp + reward_xp < 0 or not activity.diversion else reward_xp
        server_xp = (char_div_xp - char_xp) if activity.diversion else (reward_xp - char_xp)
    else:
        char_xp = reward_xp
        char_div_xp = reward_xp

    return char_gold, char_xp, char_div_xp, server_xp


async def create_logs(ctx: ApplicationContext | Any, character: PlayerCharacter, activity: Activity, notes: str = None,
                      gold: int = 0, xp: int = 0, adventure: Adventure = None) -> DBLog:
    """
    Primary function to create any Activity log

    :param ctx: Context
    :param character: PlayerCharacter the log is for
    :param activity: Activity the log is for
    :param notes: Any notes/reason for the log
    :param gold: Manual override
    :param xp: Manual override
    :param adventure: Adventure
    :return: DBLog for the character
    """
    if not hasattr(ctx, "guild_id"):
        guild_id = ctx.bot.get_guild(character.guild_id).id
    else:
        guild_id = ctx.guild_id

    if not hasattr(ctx, "author"):
        author_id = ctx.bot.user.id
    else:
        author_id = ctx.author.id

    g: PlayerGuild = await get_or_create_guild(ctx.bot.db, guild_id)
    cap: LevelCaps = get_level_cap(character, g, ctx.bot.compendium)
    adventure_id = None if adventure is None else adventure.id

    char_gold, char_xp, char_div_xp, server_xp = get_activity_amount(character, activity, cap, g, gold, xp)

    char_log = DBLog(author=author_id, xp=char_xp, gold=char_gold, character_id=character.id, activity=activity,
                     notes=notes, adventure_id=adventure_id, server_xp=server_xp, invalid=False)
    character.gold += char_gold
    character.xp += char_xp
    g.week_xp += server_xp

    if activity.diversion:
        character.div_gold += char_gold
        character.div_xp += char_div_xp

    async with ctx.bot.db.acquire() as conn:
        results = await conn.execute(insert_new_log(char_log))
        row = await results.first()
        await conn.execute(update_character(character))
        await conn.execute(update_guild(g))

    log_entry: DBLog = LogSchema(ctx.bot.compendium).load(row)

    return log_entry


async def get_log(bot: Bot, log_id: int) -> DBLog | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_log_by_id(log_id))
        row = await results.first()

    if row is None:
        return None

    log_entry = LogSchema(bot.compendium).load(row)

    return log_entry
