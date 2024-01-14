from typing import List

import discord.utils
from discord import ApplicationContext, TextChannel, CategoryChannel, Message, Bot

from Resolute.models.db_objects import CharacterSpecies, CharacterClass


class RefCategoryDashboard(object):
    category_channel_id: int
    dashboard_post_channel_id: int
    dashboard_post_id: int
    excluded_channel_ids: List[int]
    dashboard_type: int

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def channels_to_check(self, bot: Bot) -> List[TextChannel]:
        category: CategoryChannel = bot.get_channel(self.category_channel_id)
        if category is not None:
            return list(filter(lambda c: c.id not in self.excluded_channel_ids, category.text_channels))
        else:
            return []

    def get_category_channel(self, bot: Bot) -> CategoryChannel | None:
        return bot.get_channel(self.category_channel_id)

    async def get_pinned_post(self, bot: Bot) -> Message | None:
        channel = bot.get_channel(self.dashboard_post_channel_id)
        if channel is not None:
            try:
                msg = await channel.fetch_message(self.dashboard_post_id)
            except discord.errors.NotFound as e:
                return None
            return msg
        return None


class RefWeeklyStipend(object):
    guild_id: int
    role_id: int
    amount: int
    reason: str
    leadership: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class GlobalPlayer(object):
    guild_id: int
    player_id: int
    cc: int
    update: bool
    active: bool
    num_messages: int
    channels: List[int]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_name(self, ctx: ApplicationContext):
        try:
            name = discord.utils.get(ctx.bot.get_all_members(), id=self.player_id).mention
            pass
        except:
            name = f"Player {self.player_id} not found on this server"
            pass

        return name


class GlobalEvent(object):
    guild_id: int
    name: str
    base_cc: int
    channels: List[int]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_channel_names(self, bot: Bot):
        names = []
        for c in self.channels:
            names.append(bot.get_channel(int(c)).name)
        return names


class AppBaseScores(object):
    str: str = ''
    dex: str = ''
    con: str = ''
    int: str = ''
    wis: str = ''
    cha: str = ''

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def status(self):
        if self.str == '' and self.dex == '' and self.con == '' and self.int == '' and self.wis == '' and self.cha == '':
            return "<:x:983576786447245312> -- Incomplete"
        elif self.str !='' and self.dex != '' and self.con !='' and self.int !='' and self.wis != '' and self.cha != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

class AppSpecies(object):
    species: CharacterSpecies|None = None
    asi: str = ""
    feats: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_field(self):
        if not hasattr(self, "species"):
            return "Not set"
        else:
            return f"**{self.species.value}**\nASIs: {self.asi}\nFeatures: {self.feats}"

    def status(self):
        if self.species == None and self.asi == '' and self.feats == '':
            return "<:x:983576786447245312> -- Incomplete"
        elif self.species != None and self.asi != '' and self.feats != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

class AppClass(object):
    char_class: CharacterClass
    skills: str = ""
    feats: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class AppBackground(object):
    background: str = ""
    equip: str = ""
    feat: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class NewCharacterApplication(object):
    name: str = ""
    freeroll: bool = False
    base_scores: AppBaseScores = AppBaseScores()
    species: AppSpecies = AppSpecies()
    char_class: AppClass = AppClass()
    background: AppBackground = AppBackground()
    credits: int = 0
    homeworld: str = ""
    motivation: str = ""
    link: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

