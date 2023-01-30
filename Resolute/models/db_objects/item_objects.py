import math
from typing import List
import discord
from ProphetBot.models.db_objects.category_objects import *


class ItemBlacksmith(object):
    name: str
    sub_type: BlacksmithType
    rarity: Rarity
    cost: int
    item_modifier: bool
    attunement: bool
    seeking_only: bool
    source: str
    notes: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def display_cost(self) -> str:
        if self.item_modifier:
            return str(self.cost) + "+"
        else:
            return str(self.cost)


class ItemWondrous(object):
    name: str
    rarity: Rarity
    cost: int
    attunement: bool
    seeking_only: bool
    source: str
    notes: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class ItemConsumable(object):
    name: str
    sub_type: ConsumableType
    rarity: Rarity
    cost: int
    attunement: bool
    seeking_only: bool
    source: str
    notes: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class ItemScroll(object):
    name: str
    rarity: Rarity
    cost: int
    level: int
    school: MagicSchool
    classes: []
    source: str
    notes: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def ordinal_suffix(self) -> str:
        tens = self.level % 10
        hunds = self.level % 100
        if tens == 1 and hunds != 11:
            return str(self.level) + "st"
        elif tens == 2 and hunds != 12:
            return str(self.level) + "nd"
        elif tens ==3 and hunds != 13:
            return str(self.level) + "rd"
        else:
            return str(self.level) + "th"

    def display_name(self):
        return self.name + " (" + self.ordinal_suffix() + ")"

