from typing import List

from Resolute.models.db_tables import *
from sqlalchemy import null, and_, or_
from sqlalchemy.sql.selectable import FromClause, TableClause

from Resolute.models.db_objects import RefCategoryDashboard, RefWeeklyStipend, GlobalEvent, GlobalPlayer, \
    NewCharacterApplication


def get_dashboard_by_category_channel(category_channel_id: int) -> FromClause:
    return ref_category_dashboard_table.select().where(
        ref_category_dashboard_table.c.category_channel_id == category_channel_id
    )


def insert_new_dashboard(dashboard: RefCategoryDashboard) -> TableClause:
    return ref_category_dashboard_table.insert().values(
        category_channel_id=dashboard.category_channel_id,
        dashboard_post_channel_id=dashboard.dashboard_post_channel_id,
        dashboard_post_id=dashboard.dashboard_post_id,
        excluded_channel_ids=dashboard.excluded_channel_ids,
        dashboard_type=dashboard.dashboard_type
    )


def update_dashboard(dashboard: RefCategoryDashboard):
    return ref_category_dashboard_table.update() \
        .where(
        ref_category_dashboard_table.c.category_channel_id == dashboard.category_channel_id
    ) \
        .values(
        category_channel_id=dashboard.category_channel_id,
        dashboard_post_channel_id=dashboard.dashboard_post_channel_id,
        dashboard_post_id=dashboard.dashboard_post_id,
        excluded_channel_ids=dashboard.excluded_channel_ids,
        dashboard_type=dashboard.dashboard_type
    )


def get_dashboards() -> FromClause:
    return ref_category_dashboard_table.select()


def delete_dashboard(dashboard: RefCategoryDashboard) -> TableClause:
    return ref_category_dashboard_table.delete().where(
        ref_category_dashboard_table.c.category_channel_id == dashboard.category_channel_id
    )


def get_weekly_stipend_query(role_id: int) -> FromClause:
    return ref_weekly_stipend_table.select().where(
        ref_weekly_stipend_table.c.role_id == role_id
    )


def insert_weekly_stipend(stipend: RefWeeklyStipend) -> TableClause:
    return ref_weekly_stipend_table.insert().values(
        role_id=stipend.role_id,
        guild_id=stipend.guild_id,
        amount=stipend.amount,
        reason=stipend.reason,
        leadership=stipend.leadership
    )


def update_weekly_stipend(stipend: RefWeeklyStipend) -> TableClause:
    return ref_weekly_stipend_table.update().where(ref_weekly_stipend_table.c.role_id == stipend.role_id) \
        .values(
        role_id=stipend.role_id,
        guild_id=stipend.guild_id,
        amount=stipend.amount,
        reason=stipend.reason,
        leadership=stipend.leadership
    )


def get_guild_weekly_stipends(guild_id: int) -> FromClause:
    return ref_weekly_stipend_table.select() \
        .where(ref_weekly_stipend_table.c.guild_id == guild_id) \
        .order_by(ref_weekly_stipend_table.c.amount.desc())


def delete_weekly_stipend(stipend: RefWeeklyStipend) -> TableClause:
    return ref_weekly_stipend_table.delete().where(ref_weekly_stipend_table.c.role_id == stipend.role_id)


def insert_new_global_event(g_event: GlobalEvent) -> TableClause:
    return ref_gb_staging_table.insert().values(
        guild_id=g_event.guild_id,
        name=g_event.name,
        base_cc=g_event.base_cc
    )


def get_active_global(guild_id: int) -> FromClause:
    return ref_gb_staging_table.select().where(
        and_(ref_gb_staging_table.c.guild_id == guild_id)
    )


def update_global_event(g_event: GlobalEvent):
    return ref_gb_staging_table.update() \
        .where(ref_gb_staging_table.c.guild_id == g_event.guild_id) \
        .values(
        name=g_event.name,
        base_cc=g_event.base_cc,
        channels=g_event.channels
    )


def get_all_global_players(guild_id: int) -> FromClause:
    return ref_gb_staging_player_table.select().where(
        ref_gb_staging_player_table.c.guild_id == guild_id
    )


def get_global_player(guild_id: int, player_id: int) -> FromClause:
    return ref_gb_staging_player_table.select().where(
        and_(ref_gb_staging_table.c.guild_id == guild_id, ref_gb_staging_player_table.c.player_id == player_id)
    )


def update_global_player(g_player: GlobalPlayer):
    return ref_gb_staging_player_table.update() \
        .where(ref_gb_staging_player_table.c.id == g_player.id) \
        .values(
        cc=g_player.cc,
        update=g_player.update,
        active=g_player.active,
        num_messages=g_player.num_messages,
        channels=g_player.channels
    )


def delete_global_event(guild_id: int) -> TableClause:
    return ref_gb_staging_table.delete() \
        .where(ref_gb_staging_table.c.guild_id == guild_id)


def delete_global_players(guild_id: int) -> TableClause:
    return ref_gb_staging_player_table.delete() \
        .where(ref_gb_staging_player_table.c.guild_id == guild_id)


def add_global_player(g_player: GlobalPlayer):
    return ref_gb_staging_player_table.insert().values(
        guild_id=g_player.guild_id,
        player_id=g_player.player_id,
        cc=g_player.cc,
        update=g_player.update,
        active=g_player.active,
        num_messages=g_player.num_messages,
        channels=g_player.channels
    ).returning(ref_gb_staging_player_table)

def get_class_census() -> FromClause:
    return class_census_table.select()

def get_level_distribution() -> FromClause:
    return level_distribution_table.select()

def get_player_application(char_id: int) -> FromClause:
    return ref_applications_table.select().where(
        ref_applications_table.c.id == char_id
    )

def insert_player_application(char_id: int, application: str) -> TableClause:
    return ref_applications_table.insert().values(
        id = char_id,
        application = application
    )

def delete_player_application(char_id: int) -> TableClause:
    return ref_applications_table.delete() \
    .where(ref_applications_table.c.id == char_id)
