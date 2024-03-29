from datetime import datetime, timedelta

from sqlalchemy.sql.selectable import FromClause
from sqlalchemy import and_, null
from Resolute.models.db_tables import guilds_table, adventures_table, arenas_table, discord_player_table
from Resolute.models.db_objects import PlayerGuild, Adventure, Arena, DiscordPlayer


def get_guild(guild_id: int) -> FromClause:
    return guilds_table.select().where(
        guilds_table.c.id == guild_id
    )


def get_guilds_with_reset(day: int, hour: int) -> FromClause:
    six_days_ago = datetime.today() - timedelta(days=6)
    return guilds_table.select().where(
        and_(guilds_table.c.reset_day == day, guilds_table.c.reset_hour == hour,
             guilds_table.c.last_reset < six_days_ago)
    ).order_by(guilds_table.c.id.desc())


def insert_new_guild(guild: PlayerGuild):
    return guilds_table.insert().values(
        id=guild.id,
        max_level=guild.max_level,
        weeks=guild.weeks,
        max_reroll=guild.max_reroll,
    ).returning(guilds_table)


def update_guild(guild: PlayerGuild):
    return guilds_table.update() \
        .where(guilds_table.c.id == guild.id) \
        .values(
        max_level=guild.max_level,
        weeks=guild.weeks,
        reset_day=None if not hasattr(guild, "reset_day") else guild.reset_day,
        reset_hour=None if not hasattr(guild, "reset_hour") else guild.reset_hour,
        last_reset=guild.last_reset,
        handicap_cc=guild.handicap_cc
    )


def insert_new_adventure(adventure: Adventure):
    return adventures_table.insert().values(
        guild_id=adventure.guild_id,
        name=adventure.name,
        role_id=adventure.role_id,
        dms=adventure.dms,
        category_channel_id=adventure.category_channel_id,
        cc=adventure.cc,
        end_ts=None if not hasattr(adventure, "end_ts") else adventure.end_ts,
    )


def update_adventure(adventure: Adventure):
    return adventures_table.update() \
        .where(adventures_table.c.id == adventure.id) \
        .values(
        name=adventure.name,
        role_id=adventure.role_id,
        dms=adventure.dms,
        category_channel_id=adventure.category_channel_id,
        cc=adventure.cc,
        end_ts=None if not hasattr(adventure, "end_ts") else adventure.end_ts
    )


def get_adventure_by_category_channel_id(category_channel_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.category_channel_id == category_channel_id, adventures_table.c.end_ts == null())
    )


def get_adventure_by_role_id(role_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.role_id == role_id, adventures_table.c.end_ts == null())
    )


def get_adventure_by_guild(guild_id: int) -> FromClause:
    return adventures_table.select().where(
        and_(adventures_table.c.guild_id == guild_id, adventures_table.c.end_ts == null())
    ).order_by(adventures_table.c.name)

def get_adventure_by_id(adventure_id: int) -> FromClause:
    return adventures_table.select().where(
        adventures_table.c.id == adventure_id
    )

def insert_new_arena(arena: Arena):
    return arenas_table.insert().values(
        channel_id=arena.channel_id,
        pin_message_id=arena.pin_message_id,
        role_id=arena.role_id,
        host_id=arena.host_id,
        tier=arena.tier.id,
        type=arena.type.id,
        completed_phases=arena.completed_phases
    )


def update_arena(arena: Arena):
    return arenas_table.update() \
        .where(arenas_table.c.id == arena.id) \
        .values(
        channel_id=arena.channel_id,
        pin_message_id=arena.pin_message_id,
        role_id=arena.role_id,
        host_id=arena.host_id,
        tier=arena.tier.id,
        type=arena.type.id,
        completed_phases=arena.completed_phases,
        end_ts=None if not hasattr(arena, "end_ts") else arena.end_ts
    )


def get_arena_by_channel(channel_id: int) -> FromClause:
    return arenas_table.select().where(
        and_(arenas_table.c.channel_id == channel_id, arenas_table.c.end_ts == null())
    )


def select_active_arena_by_channel(channel_id: int) -> FromClause:
    return arenas_table.select().where(
        and_(arenas_table.c.channel_id == channel_id, arenas_table.c.end_ts == null())
    )

def get_discord_player_query(player_id: int, guild_id: int) -> FromClause:
    return discord_player_table.select().where(
        and_(discord_player_table.c.id == player_id, discord_player_table.c.guild_id == guild_id)
    )

def insert_new_discord_player(player: DiscordPlayer):
    return discord_player_table.insert().values(
        id=player.id,
        guild_id=player.guild_id,
        handicap_amount=player.handicap_amount
    ).returning(discord_player_table)

def update_discord_player(player: DiscordPlayer):
    return discord_player_table.update()\
        .where(discord_player_table.c.id == player.id, discord_player_table.c.guild_id == player.guild_id)\
        .values(
        id=player.id,
        guild_id=player.guild_id,
        handicap_amount=player.handicap_amount
    )