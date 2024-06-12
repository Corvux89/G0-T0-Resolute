

from discord import Member, ClientUser
from Resolute.bot import G0T0Bot
from Resolute.models.categories import Activity
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter, upsert_character
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog, LogSchema, character_stats_query, get_log_by_id, get_n_player_logs_query, player_stats_query, upsert_log
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

async def create_log(bot: G0T0Bot, author: Member | ClientUser, guild: PlayerGuild, activity: Activity, player: Player, character: PlayerCharacter = None, 
                      notes: str = None, cc: int = 0, credits: int = 0, adventure: Adventure = None, ignore_handicap: bool = False) -> DBLog:

    char_cc = get_activity_amount(player, guild, activity, cc)

    player.div_cc += char_cc if activity.diversion else 0

    char_log = DBLog(author=author.id, cc=char_cc, credits=credits, player_id=player.id, character_id=character.id if character else None,
                     activity=activity, notes=notes, adventure_id=adventure.id if adventure else None)

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
            await conn.execute(upsert_character(character))

    log_entry = LogSchema(bot.compendium).load(row)


    return log_entry

async def get_n_player_logs(bot: G0T0Bot, player: Player, n: int = 5) -> list[DBLog]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_n_player_logs_query(player.id, n))
        rows = await results.fetchall()

    if not rows:
        return None

    logs = [LogSchema(bot.compendium).load(row) for row in rows]

    return logs


async def get_player_stats(bot: G0T0Bot, player: Player) -> dict:
    async with bot.db.acquire() as conn:
        results = await conn.execute(player_stats_query(bot.compendium, player.id))
        row = await results.first()
    
    return dict(row)

async def get_character_stats(bot: G0T0Bot, character: PlayerCharacter) -> dict:
    async with bot.db.acquire() as conn:
        results = await conn.execute(character_stats_query(bot.compendium, character.id))
        row = await results.first()

    if row is None:
        return None

    return dict(row)