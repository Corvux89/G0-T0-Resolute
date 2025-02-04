import operator

from discord import ApplicationContext

from Resolute.bot import G0T0Bot
from Resolute.constants import ZWSP3
from Resolute.helpers.general_helpers import confirm
from Resolute.models.categories import Activity
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.characters import (PlayerCharacter)
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import (DBLog, LogSchema,
                                          character_stats_query,
                                          get_last_log_by_type, get_log_by_id,
                                          get_n_player_logs_query,
                                          player_stats_query, upsert_log)
from Resolute.models.objects.players import Player, upsert_player_query

async def get_log(bot: G0T0Bot, log_id: int) -> DBLog:
    """
    Retrieve a log entry from the database by its ID.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection and compendium.
        log_id (int): The ID of the log entry to retrieve.
    Returns:
        DBLog: The log entry corresponding to the given ID, or None if no entry is found.
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_log_by_id(log_id))
        row = await results.first()

    if not row:
        return None
    
    log_enty = LogSchema(bot.compendium).load(row)

    return log_enty

async def get_n_player_logs(bot: G0T0Bot, player: Player, n: int = 5) -> list[DBLog]:
    """
    Fetches the most recent logs for a given player.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection and compendium.
        player (Player): The player whose logs are to be fetched.
        n (int, optional): The number of logs to fetch. Defaults to 5.
    Returns:
        list[DBLog]: A list of the most recent logs for the player, or None if no logs are found.
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_n_player_logs_query(player.id, player.guild_id, n))
        rows = await results.fetchall()

    if not rows:
        return None

    logs = [LogSchema(bot.compendium).load(row) for row in rows]

    return logs


async def get_player_stats(bot: G0T0Bot, player: Player) -> dict:
    """
    Retrieve player statistics from the database.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection and compendium.
        player (Player): The player object containing the player's ID and guild ID.
    Returns:
        dict: A dictionary containing the player's statistics.
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(player_stats_query(bot.compendium, player.id, player.guild_id))
        row = await results.first()

    return dict(row)

async def get_character_stats(bot: G0T0Bot, character: PlayerCharacter) -> dict:
    """
    Fetches the statistics of a given character from the database.
    Args:
        bot (G0T0Bot): The bot instance containing the database connection and compendium.
        character (PlayerCharacter): The character whose stats are to be fetched.
    Returns:
        dict: A dictionary containing the character's stats if found, otherwise None.
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(character_stats_query(bot.compendium, character.id))
        row = await results.first()

    if row is None:
        return None

    return dict(row)

async def get_last_activity_log(bot: G0T0Bot, player: Player, guild: PlayerGuild, activity: Activity) -> DBLog:
    """
    Fetches the last activity log for a given player in a specific guild and activity.
    Args:
        bot (G0T0Bot): The bot instance to use for database access.
        player (Player): The player whose activity log is being fetched.
        guild (PlayerGuild): The guild in which the activity took place.
        activity (Activity): The specific activity to fetch the log for.
    Returns:
        DBLog: The last activity log entry for the specified player, guild, and activity.
               Returns None if no log entry is found.
    """
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_last_log_by_type(player.id, guild.id, activity.id))
        row = await results.first()

    if row is None:
        return None
    return LogSchema(bot.compendium).load(row)


async def update_activity_points(bot: G0T0Bot, player: Player, increment: bool = True):
    """
    Updates the activity points of a player and adjusts their activity level accordingly.
    Args:
        bot (G0T0Bot): The bot instance.
        player (Player): The player whose activity points are to be updated.
        increment (bool, optional): If True, increment the activity points by 1. If False, decrement the activity points by 1. Defaults to True.
    Returns:
        None
    """ 
    if increment:
        player.activity_points += 1
    else:
        player.activity_points = max(player.activity_points - 1, 0)

    activity_point = None
    for point in sorted(bot.compendium.activity_points[0].values(), key=operator.attrgetter('id')):
        if player.activity_points >= point.points:
            activity_point = point
        elif player.activity_points < point.points:
            break

    if activity_point and player.activity_level != activity_point.id:
        revert = True if player.activity_level > activity_point.id else False
        player.activity_level = activity_point.id
        act_log = await bot.log(None, player, bot.user, "ACTIVITY_REWARD",
                                notes=f"Activity Level {player.activity_level}{' [REVERSION]' if revert else ''}",
                                cc=-1 if revert else 0,
                                silent=True)
        
        if player.guild.activity_points_channel and not revert:
            await player.guild.activity_points_channel.send(embed=LogEmbed(act_log, bot.user, player.member), content=f"{player.member.mention}")

        if player.guild.staff_channel and revert:
            await player.guild.staff_channel.send(embed=LogEmbed(act_log, bot.user, player.member))
            await player.member.send(embed=LogEmbed(act_log, bot.user, player.member))
    else:
        async with bot.db.acquire() as conn:
            await conn.execute(upsert_player_query(player))

async def null_log(bot: G0T0Bot, ctx: ApplicationContext, log: DBLog, reason: str) -> DBLog:
    """
    Asynchronously nullifies a log entry for a player and creates a new log entry indicating the nullification.
    Args:
        bot (G0T0Bot): The bot instance.
        ctx (ApplicationContext): The context of the application command.
        log (DBLog): The log entry to be nullified.
        reason (str): The reason for nullifying the log.
    Returns:
        DBLog: The new log entry created to indicate the nullification.
    Raises:
        G0T0Bot: If the log has already been invalidated.
        TimeoutError: If the confirmation times out.
        G0T0Error: If the nullification is cancelled by the user.
    """
    if log.invalid:
        raise G0T0Bot(f"Log [ {log.id} ] has already been invalidated.")
    
    player = await bot.get_player(log.player_id, log.guild_id,
                                  inactive=True)
    
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
    
    if log.created_ts > player.guild._last_reset and log.activity.diversion:
        player.div_cc = max(player.div_cc-log.cc, 0)
    
    note = (f"{log.activity.value} log # {log.id} nulled by "
            f"{ctx.author} for reason: {reason}")
    
    log_entry = await bot.log(ctx, player, ctx.author, "MOD",
                  character=character,
                  notes=note,
                  cc=-log.cc,
                  credits=-log.credits,
                  renown=-log.renown,
                  raction=log.faction if log.faction else None)
    
    log.invalid = True

    async with bot.db.acquire() as conn:
        await conn.execute(upsert_log(log))

    return log_entry

    
    
