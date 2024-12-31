import operator
import re

import discord
from discord import ClientUser, Member

from Resolute.bot import G0T0Bot
from Resolute.constants import ZWSP3
from Resolute.helpers.characters import update_character_renown
from Resolute.helpers.general_helpers import confirm
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.players import get_player
from Resolute.models.categories import Activity
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import (PlayerCharacter,
                                                upsert_character_query)
from Resolute.models.objects.exceptions import G0T0Error, LogNotFound, TransactionError
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import (DBLog, LogSchema,
                                          character_stats_query,
                                          get_last_log_by_type, get_log_by_id,
                                          get_n_player_logs_query,
                                          player_stats_query, upsert_log)
from Resolute.models.objects.players import Player, upsert_player_query


def get_activity_amount(player: Player, guild: PlayerGuild, activity: Activity, override_amount: int = 0) -> int:
    reward_cc = override_amount if override_amount != 0 else activity.cc if activity.cc else 0

    if activity.diversion and (player.div_cc + reward_cc > guild.div_limit):
        reward_cc = 0 if guild.div_limit - player.div_cc < 0 else guild.div_limit - player.div_cc

    return reward_cc

def handicap_adjustment(player: Player, guild: PlayerGuild, amount: int, ignore: bool) -> int:
    if ignore or guild.handicap_cc <= player.handicap_amount:
        return 0
    
    return min(amount, guild.handicap_cc - player.handicap_amount)

async def author_rewards(bot: G0T0Bot, author: discord.Member, guild: PlayerGuild, log_entry: DBLog) -> None:
    if not guild.reward_threshold or log_entry.activity.value == "LOG_REWARD":
        return
    
    player = await get_player(bot, author.id, guild.id)

    player.points += log_entry.activity.points

    if player.points >= guild.reward_threshold:
        activity: Activity = bot.compendium.get_activity("LOG_REWARD")
        qty = max(1, player.points//guild.reward_threshold)        
        reward_log = await create_log(bot, bot.user, "LOG_REWARD", player,
                                      cc=activity.cc * qty,
                                      notes=f"Rewards for {guild.reward_threshold * qty} points")
        player.points = max(0, player.points - (guild.reward_threshold * qty))

        if guild.staff_channel:
            await guild.staff_channel.send(embed=LogEmbed(reward_log, bot.user, player.member, None, True))

    async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(player))



async def get_log(bot: G0T0Bot, log_id: int) -> DBLog:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_log_by_id(log_id))
        row = await results.first()

    if not row:
        return None
    
    log_enty = LogSchema(bot.compendium).load(row)

    return log_enty

async def create_log(bot: G0T0Bot, author: Member | ClientUser, activity: Activity | str, player: Player, **kwargs) -> DBLog:    
    """Create a log entry for a player

    Args:
        bot (G0T0Bot): Bot
        author (Member | ClientUser): Who is creating the log
        activity (Activity): What is the log for
        player (Player): Who is the log for

    Keyword Args:
        character (PlayerCharacter): The character the log is for
        notes (str): Log notes
        cc (int): Chain Codes
        credits (int): Credits
        adventure (Adventure): Adventure the log is for
        ignore_handicap (bool): Ignore the handicap adjustment
        renown (int): Renown amount
        faction (Faction): Faction to log the renown to
        
    Returns:
        DBLog: Log entry
    """

    # Kwargs stuff
    character: PlayerCharacter = kwargs.get('character')
    notes: str = kwargs.get('notes')
    cc: int = kwargs.get('cc', 0)
    credits: int = kwargs.get('credits', 0)
    adventure: Adventure = kwargs.get('adventure')
    faction: Faction = kwargs.get('faction')
    renown: int = kwargs.get('renown', 0)
    ignore_handicap: bool = kwargs.get('ignore_handicap', False)

    if isinstance(activity, str):
        activity = bot.compendium.get_activity(activity)

    # Get Values
    guild = await get_guild(bot, player.guild_id)
    activity_cc = get_activity_amount(player, guild, activity, cc)
    handicap_amount = handicap_adjustment(player, guild, activity_cc, ignore_handicap)

    # Shell Log
    log_entry = DBLog(author=author.id, 
                      cc=activity_cc+handicap_amount, 
                      credits=credits, 
                      player_id=player.id, 
                      character_id=character.id if character else None,
                     activity=activity, 
                     notes=notes, 
                     guild_id=guild.id,
                     adventure_id=adventure.id if adventure else None,
                     faction=faction,
                     renown=renown)
    
    # Validation
    if character and character.credits + log_entry.credits < 0:
        raise TransactionError(f"{character.name} cannot afford the {log_entry.credits} credit cost.")
    elif player.cc + log_entry.cc < 0:
        raise TransactionError(f"{player.member.mention} cannot afford the {log_entry.cc} CC cost.")


    # Updates
    if character: 
        character.credits+=log_entry.credits

    player.cc += log_entry.cc
    player.handicap_amount += handicap_amount

    if activity.diversion:
        player.div_cc += activity_cc

    if faction:
        await update_character_renown(bot, character, faction, renown)

    # Write to DB
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_log(log_entry))
        row = await results.first()

        await conn.execute(upsert_player_query(player))

        if character:
            await conn.execute(upsert_character_query(character))

    log_entry = LogSchema(bot.compendium).load(row)

    # Author Rewards
    await author_rewards(bot, author, guild, log_entry)

    return log_entry

async def get_n_player_logs(bot: G0T0Bot, player: Player, n: int = 5) -> list[DBLog]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_n_player_logs_query(player.id, player.guild_id, n))
        rows = await results.fetchall()

    if not rows:
        return None

    logs = [LogSchema(bot.compendium).load(row) for row in rows]

    return logs


async def get_player_stats(bot: G0T0Bot, player: Player) -> dict:
    async with bot.db.acquire() as conn:
        results = await conn.execute(player_stats_query(bot.compendium, player.id, player.guild_id))
        row = await results.first()
    
    return dict(row)

async def get_character_stats(bot: G0T0Bot, character: PlayerCharacter) -> dict:
    async with bot.db.acquire() as conn:
        results = await conn.execute(character_stats_query(bot.compendium, character.id))
        row = await results.first()

    if row is None:
        return None

    return dict(row)

async def get_log_from_entry(bot: G0T0Bot, message: discord.Message) -> DBLog:
    try:
        embed = message.embeds[0]
        log_id = get_match(f"ID:\s*(\d+)", embed.footer.text)

        log_entry = await get_log(bot, log_id)

    except:
        raise LogNotFound()

    return log_entry

async def get_last_activity_log(bot: G0T0Bot, player: Player, guild: PlayerGuild, activity: Activity) -> DBLog:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_last_log_by_type(player.id, guild.id, activity.id))
        row = await results.first()

    if row is None:
        return None
    return LogSchema(bot.compendium).load(row)


def get_match(pattern, text, group=1, default=None):
    match = re.search(pattern, text, re.DOTALL)
    return match.group(group) if match and match.group(group) != 'None' else default


async def update_activity_points(bot: G0T0Bot, player: Player, guild: PlayerGuild, increment: bool = True):
    if increment:
        player.activity_points += 1
    else:
        player.activity_points -= 1

    activity_point = None
    for point in sorted(bot.compendium.activity_points[0].values(), key=operator.attrgetter('id')):
        if player.activity_points >= point.points:
            activity_point = point
        elif player.activity_points < point.points:
            break

    if activity_point and player.activity_level != activity_point.id:
        revert = True if player.activity_level > activity_point.id else False
        player.activity_level = activity_point.id
        act_log = await create_log(bot, bot.user, "ACTIVITY_REWARD", player,
                                   notes=f"Activity Level {player.activity_level}{' [REVERSION]' if revert else ''}",
                                   cc=-1 if revert else 0
                                   )

        if guild.activity_points_channel and not revert:
            await guild.activity_points_channel.send(embed=LogEmbed(act_log, bot.user, player.member), content=f"{player.member.mention}")

        if guild.staff_channel and revert:
            await guild.staff_channel.send(embed=LogEmbed(act_log, bot.user, player.member))
            await player.member.send(embed=LogEmbed(act_log, bot.user, player.member))
    else:
        async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(player))

async def null_log(bot: G0T0Bot, ctx: discord.ApplicationContext, log: DBLog, reason: str) -> DBLog:
    if log.invalid:
        raise G0T0Bot(f"Log [ {log.id} ] has already been invalidated.")
    
    player = await get_player(bot, log.player_id, log.guild_id, True)
    
    if log.character_id:
        character = next((c for c in player.characters if c.id == log.character_id), None)
    else:
        character = None

    conf = await confirm(ctx,
                         f"Are you sure you want to nullify the `{log.activity.value}` log "
                         f"for {player.member.display_name if player.member else 'Player not found'} {f'[Character: {character.name}]' if character else ''}.\n"
                         f"**Refunding**\n"
                         f"{ZWSP3}**CC**: {log.cc}\n"
                         f"{ZWSP3}**Credits**: {log.credits}\n"
                         f"{ZWSP3}**Renown**: {log.renown} {f'for {log.faction.value}' if log.faction else ''}", True, bot)
    
    if conf is None:
        raise TimeoutError()
    elif not conf:
        raise G0T0Error("Ok, cancelling")
    
    guild = await get_guild(bot, log.guild_id)
    
    if log.created_ts > guild._last_reset and log.activity.diversion:
        player.div_cc = max(player.div_cc-log.cc, 0)
    
    note = (f"{log.activity.value} log # {log.id} nulled by "
            f"{ctx.author} for reason: {reason}")
    
    log_entry = await create_log(bot, ctx.author, "MOD", player,
                                 character=character,
                                 notes=note,
                                 cc=-log.cc,
                                 credits=-log.credits,
                                 renown=-log.renown,
                                 faction=log.faction if log.faction else None)
    log.invalid = True

    async with bot.db.acquire() as conn:
        await conn.execute(upsert_log(log))

    return log_entry

    
    
