import discord.utils
from discord import ApplicationContext, Role

class Rarity(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class CharacterClass(object):
    def __init__(self, id, value):
        """
        :param id: int
        :param value: str
        """

        self.id = id
        self.value = value


class CharacterArchetype(object):
    def __init__(self, id, parent, value):
        """
        :param id: int
        :param parent: int
        :param value: str
        """

        self.id = id
        self.parent = parent
        self.value = value


class CharacterSpecies(object):
    def __init__(self, id, value):
        """
        :param id: int
        :param value: str
        """

        self.id = id
        self.value = value

class GlobalModifier(object):
    def __init__(self, id, value, adjustment, max):
        """
        :param id: int
        :param value: str
        :param adjustment: float
        :param max: int
        """

        self.id = id
        self.value = value
        self.adjustment = adjustment
        self.max = max


class HostStatus(object):
    def __init__(self, id, value):
        """
        :param id: int
        :param value: str
        """

        self.id = id
        self.value = value


class ArenaTier(object):
    def __init__(self, id, avg_level, max_phases):
        """
        :param id: int
        :param avg_level: int
        :param max_phases: int
        """

        self.id = id
        self.avg_level = avg_level
        self.max_phases = max_phases


class AdventureTier(object):
    def __init__(self, id, avg_level):
        """
        :param id: int
        :param avg_level: int
        """

        self.id = id
        self.avg_level = avg_level


class Activity(object):
    def __init__(self, id, value, cc, diversion):
        """
        :param id: int
        :param value: str
        :param ratio: float
        :param diversion: bool
        """

        self.id = id
        self.value = value
        self.cc = cc
        self.diversion = diversion

class DashboardType(object):
    def __init__(self, id, value):
        """
        :param id: int
        :param value: str
        """

        self.id = id
        self.value = value


class LevelCaps(object):
    def __init__(self, id, max_cc):
        """
        :param id: int
        :param max_gold: int
        :param max_xp: int
        """

        self.id = id
        self.max_cc = max_cc


class AdventureRewards(object):
    def __init__(self, id, ep, tier, rarity = None):
        """
        :param id: int
        :param ep: int
        :param tier: int
        :param rarity: int
        """

        self.id = id
        self.ep = ep
        self.tier = tier
        self.rarity = rarity

class CodeConversion(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value

class StarshipRole(object):
    def __init__(self, id, value, size):
        self.id = id
        self.value = value
        self.size = size

    def get_size(self, compendium):
        return compendium.get_object("c_starship_size", self.size)

class StarshipSize(object):
    def __init__(self, id, value):
        self.id = id
        self.value = value
