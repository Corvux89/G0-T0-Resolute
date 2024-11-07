import re

import discord
from discord import ClientUser, Member

from Resolute.bot import G0T0Bot
from Resolute.helpers.players import get_player
from Resolute.models.categories import Activity
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import (CharacterRenown,
                                                PlayerCharacter,
                                                upsert_character_query,
                                                upsert_character_renown)
from Resolute.models.objects.exceptions import LogNotFound
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

async def get_log(bot: G0T0Bot, log_id: int) -> DBLog:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_log_by_id(log_id))
        row = await results.first()

    if not row:
        return None
    
    log_enty = LogSchema(bot.compendium).load(row)

    return log_enty

async def create_log(bot: G0T0Bot, author: Member | ClientUser, guild: PlayerGuild, activity: Activity, player: Player, **kwargs) -> DBLog:    
    """Create a log entry for a player

    Args:
        bot (G0T0Bot): Bot
        author (Member | ClientUser): Who is creating the log
        guild (PlayerGuild): Guild settings
        activity (Activity): What is the log for
        player (Player): Who is the log for

    Keyword Args:
        character (PlayerCharacter): The character the log is for
        notes (str): Log notes
        cc (int): Chain Codes
        credits (int): Credits
        adventure (Adventure): Adventure the log is for
        ignore_handicap (bool): Ignore the handicap adjustment
        
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

    char_cc = get_activity_amount(player, guild, activity, cc)

    player.div_cc += char_cc if activity.diversion else 0
    char_log = DBLog(author=author.id, cc=char_cc, credits=credits, player_id=player.id, character_id=character.id if character else None,
                     activity=activity, notes=notes, guild_id=guild.id,
                     adventure_id=adventure.id if adventure else None,
                     faction=faction,
                     renown=renown)
    # Handle Renown
    char_renown = None
    if faction:
        char_renown = next((r for r in character.renown if r.faction.id == faction.id), CharacterRenown(faction=faction, 
                                                                                                        character_id=character.id))
        char_renown.renown += renown

    # Handicap Adjustment
    if not ignore_handicap and guild.handicap_cc and player.handicap_amount < guild.handicap_cc:
        extra_cc = min(char_log.cc, guild.handicap_cc - player.handicap_amount)
        char_log.cc += extra_cc
        player.handicap_amount += extra_cc

    # Updates
    if character: 
        character.credits+=char_log.credits

    player.cc += char_log.cc

    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_log(char_log))
        row = await results.first()

        await conn.execute(upsert_player_query(player))

        if character:
            await conn.execute(upsert_character_query(character))

        if char_renown:
            await conn.execute(upsert_character_renown(char_renown))


    log_entry = LogSchema(bot.compendium).load(row)

    # Author Rewards
    author_player = await get_player(bot, author.id, guild.id) if author.id != player.id else player
    author_player.points += activity.points if guild.reward_threshold else 0

    if activity.value != "LOG_REWARD" and guild.reward_threshold and author_player.points >= guild.reward_threshold:
        reward_activity: Activity = bot.compendium.get_activity("LOG_REWARD")
        qty = max(1, author_player.points//guild.reward_threshold)
        reward_log = await create_log(bot, bot.user, guild, reward_activity, author_player, 
                                      cc=reward_activity.cc*qty, 
                                      notes=f"Rewards for {guild.reward_threshold*qty} points")
        author_player.points = max(0, author_player.points-(guild.reward_threshold*qty))

        if guild.archivist_channel:
            await guild.archivist_channel.send(embed=LogEmbed(reward_log, bot.user, author, None, True))
    
    async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(author_player))

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
    for point in bot.compendium.activity_points[0].values():
        if player.activity_points >= point.points:
            activity_point = point
        elif player.activity_points < point.points:
            break

    if activity_point and player.activity_level != activity_point.id and (activity := bot.compendium.get_activity("ACTIVITY_REWARD")):
        revert = True if player.activity_level > activity_point.id else False
        player.activity_level = activity_point.id
        act_log = await create_log(bot, bot.user, guild, activity, player,
                                   notes=f"Activity Level {player.activity_level}{' [REVERSION]' if revert else ''}",
                                   cc=-1 if revert else 0
                                   )

        if guild.market_channel and not revert:
            await guild.market_channel.send(embed=LogEmbed(act_log, bot.user, player.member), content=f"{player.member.mention}")

        if guild.archivist_channel and revert:
            await guild.archivist_channel.send(embed=LogEmbed(act_log, bot.user, player.member))
            await player.member.send(embed=LogEmbed(act_log, bot.user, player.member))
    else:
        async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(player))