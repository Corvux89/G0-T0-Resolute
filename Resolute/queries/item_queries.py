from sqlalchemy.sql.selectable import FromClause

from ProphetBot.models.db_tables import item_blacksmith_table, item_wondrous_table, item_consumable_table, \
    item_scrolls_table


def get_blacksmith_items() -> FromClause:
    return item_blacksmith_table.select()


def get_wondrous_items() -> FromClause:
    return item_wondrous_table.select()


def get_consumable_items() -> FromClause:
    return item_consumable_table.select()


def get_scroll_items() -> FromClause:
    return item_scrolls_table.select()
