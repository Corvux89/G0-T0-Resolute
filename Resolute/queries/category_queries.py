from ProphetBot.models.db_tables import *
from sqlalchemy.sql.selectable import FromClause


def get_c_rarity() -> FromClause:
    return c_rarity_table.select()


def get_c_blacksmith_type() -> FromClause:
    return c_blacksmith_type_table.select()


def get_c_consumable_type() -> FromClause:
    return c_consumable_type_table.select()


def get_c_magic_school() -> FromClause:
    return c_magic_school_table.select()


def get_c_character_class() -> FromClause:
    return c_character_class_table.select()


def get_c_character_subclass() -> FromClause:
    return c_character_subclass_table.select()


def get_c_character_race() -> FromClause:
    return c_character_race_table.select()


def get_c_character_subrace() -> FromClause:
    return c_character_subrace_table.select()


def get_c_global_modifier() -> FromClause:
    return c_global_modifier_table.select()


def get_c_host_status() -> FromClause:
    return c_host_status_table.select()


def get_c_arena_tier() -> FromClause:
    return c_arena_tier_table.select()


def get_c_adventure_tier() -> FromClause:
    return c_adventure_tier_table.select()


def get_c_shop_type() -> FromClause:
    return c_shop_type_table.select()


def get_c_activity() -> FromClause:
    return c_activity_table.select()


def get_c_faction() -> FromClause:
    return c_faction_table.select()


def get_c_dashboard_type() -> FromClause:
    return c_dashboard_type_table.select()


def get_c_level_caps() -> FromClause:
    return c_level_caps_table.select()


def get_c_adventure_rewards() -> FromClause:
    return c_adventure_rewards_table.select()


def get_c_shop_tiers() -> FromClause:
    return c_shop_tier_table.select()
