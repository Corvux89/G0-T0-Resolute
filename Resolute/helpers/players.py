import discord

from Resolute.models.categories import Activity
from Resolute.models.objects.logs import get_log_count_by_player_and_activity
from Resolute.models.objects.players import Player, get_player_query, upsert_player_query, PlayerSchema
from Resolute.helpers import get_characters
from Resolute.bot import G0T0Bot


async def get_player(bot: G0T0Bot, player_id: int, guild_id: int, inactive: bool = False) -> Player:

    async with bot.db.acquire() as conn:
        results = await conn.execute(get_player_query(player_id, guild_id))
        rows = await results.fetchall()

        if len(rows) == 0 and guild_id:
            player = Player(id=player_id, guild_id=guild_id)
            results = await conn.execute(upsert_player_query(player))
            row = await results.first()
        elif guild_id:
            row = rows[0]
        else:
            raise Exception("Unable to create player from DM's")
        

    player: Player = PlayerSchema().load(row)

    player.characters = await get_characters(bot, player_id, player.guild_id, inactive)

    if len(player.characters) > 0 and player.highest_level_character.level < 3:
        player = await get_player_quests(bot, player )

    player.member = bot.get_guild(player.guild_id).get_member(player_id)

    return player

async def manage_player_roles(player: Player, reason: str = None) -> None:
    if (acolyte_role := discord.utils.get(player.member.guild.roles, name="Acolyte")) and (citizen_role := discord.utils.get(player.member.guild.roles, name="Citizen")) and (high_char := player.highest_level_character):
        if high_char.level < 3 and (acolyte_role not in player.member.roles) and (citizen_role not in player.member.roles):
            await player.member.add_roles(acolyte_role, reason=reason)
        elif high_char.level >= 3:
            if acolyte_role in player.member.roles:
                await player.member.remove_roles(acolyte_role, reason=reason)
            if citizen_role not in player.member.roles:
                await player.member.add_roles(citizen_role, reason=reason)

async def get_player_quests(bot: G0T0Bot, player: Player) -> Player:
    rp_activity = bot.compendium.get_object(Activity, "RP")
    arena_activity = bot.compendium.get_object(Activity, "ARENA")
    arena_host_activity = bot.compendium.get_object(Activity,  "ARENA_HOST")

    async with bot.db.acquire() as conn:
        rp_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, rp_activity.id))
        areana_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, arena_activity.id))
        arena_host_result = await conn.execute(get_log_count_by_player_and_activity(player.id, player.guild_id, arena_host_activity.id))
        player.completed_rps = await rp_result.scalar()
        player.completed_arenas = await areana_result.scalar() + await arena_host_result.scalar()

    player.needed_rps = 1 if player.highest_level_character.level == 1 else 2
    player.needed_arenas = 1 if player.highest_level_character.level == 1 else 2

    return player