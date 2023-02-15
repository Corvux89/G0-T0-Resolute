import asyncio
import logging
from timeit import default_timer as timer

from Resolute.models.schemas.category_schema import *
from Resolute.queries.category_queries import *

log = logging.getLogger(__name__)


async def get_table_values(conn, query, obj, schema) -> []:
    d1 = dict()
    d2 = dict()
    ary = []
    async for row in conn.execute(query):
        val: obj = schema.load(row)
        d1[val.id] = val

        if hasattr(val, "value"):
            d2[val.value] = val
        elif hasattr(val, "avg_level"):
            d2[val.avg_level] = val
        elif hasattr(val, "name"):
            d2[val.name] = val
    ary.append(d1)
    ary.append(d2)
    return ary


class Compendium:

    # noinspection PyTypeHints
    def __init__(self):

        """
        Structure will generally be:
        self.attribute[0] = dict(object.id) = object
        self.attribute[1] = dict(object.value) = object

        This can help ensure o(1) for lookups on id/value. o(n) for any filtering
        """

        self.c_rarity = []
        self.c_character_species = []
        self.c_character_class = []
        self.c_character_archetype = []
        self.c_arena_tier = []
        self.c_adventure_tier = []
        self.c_adventure_rewards = []
        self.c_activity = []
        self.c_dashboard_type = []
        self.c_level_caps = []
        self.c_code_conversion = []
        self.c_starship = []


    async def reload_categories(self, bot):
        start = timer()

        if not hasattr(bot, "db"):
            return

        async with bot.db.acquire() as conn:
            self.c_rarity = await get_table_values(conn, get_c_rarity(), Rarity, RaritySchema())
            self.c_character_species = await get_table_values(conn, get_c_character_species(), CharacterSpecies,
                                                              CharacterSpeciesSchema())
            self.c_character_class = await get_table_values(conn, get_c_character_class(), CharacterClass,
                                                            CharacterClassSchema())
            self.c_character_archetype = await get_table_values(conn, get_c_character_archetype(), CharacterArchetype,
                                                                CharacterArchetypeSchema())
            self.c_arena_tier = await get_table_values(conn, get_c_arena_tier(), ArenaTier, ArenaTierSchema())
            self.c_adventure_tier = await get_table_values(conn, get_c_adventure_tier(), AdventureTier,
                                                           AdventureTierSchema())
            self.c_adventure_rewards = await get_table_values(conn, get_c_adventure_rewards(), AdventureRewards,
                                                              AdventureRewardsSchema())
            self.c_activity = await get_table_values(conn, get_c_activity(), Activity, ActivitySchema())
            self.c_dashboard_type = await get_table_values(conn, get_c_dashboard_type(), DashboardType,
                                                           DashboardTypeSchema())
            self.c_level_caps = await get_table_values(conn, get_c_level_caps(), LevelCaps, LevelCapsSchema())
            self.c_code_conversion = await get_table_values(conn, get_c_code_conversion(), CodeConversion,
                                                            CodeConversionSchema())
            self.c_starship = await get_table_values(conn, get_c_starship(), Starship, StarshipSchema())

        end = timer()
        log.info(f'COMPENDIUM: Categories reloaded in [ {end - start:.2f} ]s')

    def get_object(self, node: str, value: str | int = None):
        try:
            if isinstance(value, int):
                return self.__getattribute__(node)[0][value]
            else:
                return self.__getattribute__(node)[1][value]
        except KeyError:
            return None
