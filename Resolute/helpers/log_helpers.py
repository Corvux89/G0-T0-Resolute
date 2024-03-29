from typing import Any

from discord import ApplicationContext, Bot

from Resolute.helpers.entity_helpers import get_or_create_guild, get_discord_player
from Resolute.helpers.character_helpers import get_level_cap
from Resolute.models.db_objects import PlayerCharacter, Activity, LevelCaps, PlayerGuild, DBLog, Adventure, \
    DiscordPlayer
from Resolute.models.schemas import LogSchema
from Resolute.queries import insert_new_log, update_character, update_guild, get_log_by_id, update_discord_player


def get_activity_amount(character: PlayerCharacter, activity: Activity, cap: LevelCaps, cc: int = 0,
                        credits: int = 0):
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
    if activity.cc is not None:
        # Calculate the ratio unless we have a manual override
        reward_cc = activity.cc if cc == 0 else cc
    else:
        reward_cc = cc

    reward_credits = credits

    if activity.diversion and (character.div_cc + reward_cc > cap.max_cc):  # Apply diversion limits
        reward_cc = 0 if cap.max_cc - character.div_cc < 0 else cap.max_cc - character.div_cc


    return reward_cc, reward_credits


async def create_logs(ctx: ApplicationContext | Any, character: PlayerCharacter, activity: Activity, notes: str = None,
                      cc: int = 0, credits: int = 0, adventure: Adventure = None, ignore_handicap: bool = False) -> DBLog:
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
    discord_player: DiscordPlayer = await get_discord_player(ctx.bot, character.player_id, guild_id)
    adventure_id = None if adventure is None else adventure.id

    char_cc, char_credits = get_activity_amount(character, activity, cap, cc, credits)

    char_log = DBLog(author=author_id, cc=char_cc, credits=char_credits, character_id=character.id,
                     activity=activity, notes=notes, adventure_id=adventure_id, invalid=False)

    if activity.diversion:
        character.div_cc += char_cc

    # Handicap
    if not ignore_handicap and g.handicap_cc and discord_player.handicap_amount < g.handicap_cc:
        if char_log.cc * 2 + discord_player.handicap_amount > g.handicap_cc:
            char_log.cc += g.handicap_cc - discord_player.handicap_amount
        else:
            char_log.cc = char_log.cc * 2

        discord_player.handicap_amount += char_log.cc

    character.cc += char_log.cc
    character.credits += char_credits

    async with ctx.bot.db.acquire() as conn:
        results = await conn.execute(insert_new_log(char_log))
        row = await results.first()
        await conn.execute(update_character(character))
        await conn.execute(update_discord_player(discord_player))

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
