import logging
from timeit import default_timer as timer

from Resolute.models.categories import *

log = logging.getLogger(__name__)


async def get_table_values(conn, comp: CompendiumObject) -> list:
    d1, d2 = {}, {}

    async for row in conn.execute(get_category_table(comp.table)):
        val = comp.schema().load(row)

        d1[val.id] = val
        attr_list = ["value", "avg_level", "name", "cc", "points"]
        key = next((getattr(val, attr) for attr in attr_list if hasattr(val, attr)), None)

        if key is not None:
            d2[key] = val

    return [d1, d2]

class Compendium:
    def __init__(self) -> None:
        self.categories = [
            rarity, char_class, char_archetype,
            char_species, arena_tier, activity, 
            dashboard_type, cc_conversion, arena_type, transaction_type, transaction_subtype,
            level_cost, faction, activity_points, npc_type
            ]

        for category in self.categories:
            setattr(self, category.key, [])
    
    async def reload_categories(self, bot):
        if not hasattr(bot, "db"):
            return
        
        start = timer()
        async with bot.db.acquire() as conn:
            for category in self.categories:
                setattr(self, category.key, await get_table_values(conn, category))

        end = timer()
        log.info(f'COMPENDIUM: Categories reloaded in [ {end - start:.2f} ]s')
        bot.dispatch("compendium_loaded")
        
    def get_object(self, cls, value: str | int = None):
        try:
            for category in self.categories:
                if category.obj == cls:
                    for cat_value in getattr(self, category.key)[0 if isinstance(value, int) else 1]:
                        if isinstance(cat_value, str) and isinstance(value, str):
                            if cat_value.lower() == value.lower():
                                return getattr(self, category.key)[0 if isinstance(value, int) else 1][cat_value]
                        elif cat_value == value:
                            return getattr(self, category.key)[0 if isinstance(value, int) else 1][cat_value]
                    
                    # Approximate match for strings
                    for cat_value in getattr(self, category.key)[0 if isinstance(value, int) else 1]:
                        if isinstance(cat_value, str) and isinstance(value, str):
                            if cat_value.lower().startswith(value.lower()):
                                return getattr(self, category.key)[0 if isinstance(value, int) else 1][cat_value]
        except:
            pass
        return None
    
    def get_activity(self, activity: str | int = None):
        return self.get_object(Activity, activity)