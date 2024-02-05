from typing import List

import discord.utils
from discord import ApplicationContext, TextChannel, CategoryChannel, Message, Bot

from Resolute.models.db_objects import CharacterSpecies, CharacterClass, PlayerCharacter


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
        elif self.str != '' and self.dex != '' and self.con != '' and self.int != '' and self.wis != '' and self.cha != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

    def output(self):
        return (f"**STR:** {self.str}\n" 
               f"**DEX:** {self.dex}\n" 
               f"**CON:** {self.con}\n"
               f"**INT:** {self.int}\n"
               f"**WIS:** {self.wis}\n"
               f"**CHA:** {self.cha}\n")


class AppSpecies(object):
    species: str = ""
    asi: str = ""
    feats: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_field(self):
        if not hasattr(self, "species"):
            return "Not set"
        else:
            return f"**{self.species}**\nASIs: {self.asi}\nFeatures: {self.feats}"

    def status(self):
        if self.species == '' and self.asi == '' and self.feats == '':
            return "<:x:983576786447245312> -- Incomplete"
        elif self.species != '' and self.asi != '' and self.feats != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

    def output(self):
        return (f"**Species:** {self.species}\n"
                f"**ASI:** {self.asi}\n"
                f"**Features:** {self.feats[:500]}\n")


class AppClass(object):
    char_class: str = ""
    skills: str = ""
    feats: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def status(self):
        if self.char_class == '' and self.skills == '' and self.feats == '' and self.equipment == '':
            return "<:x:983576786447245312> -- Incomplete"
        elif self.char_class != '' and self.skills != '' and self.feats != '' and self.equipment != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

    def output(self):
        return (f"**Class:** {self.char_class}\n"
                f"**Skills:** {self.skills[:250]}\n"
                f"**Features:** {self.feats[:250]}\n"
                f"**Equipment:** {self.equipment[:400]}")


class AppBackground(object):
    background: str = ""
    skills: str = ""
    tools: str = ""
    feat: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def status(self):
        if self.background == '' and self.skills == '' and self.tools == '' and self.feat == '' and self.equipment == '':
            return "<:x:983576786447245312> -- Incomplete"
        elif self.background != '' and self.skills != '' and self.tools != '' and self.feat != '' and self.equipment != '':
            return "<:white_check_mark:983576747381518396> -- Complete"
        else:
            return "<:pencil:989284061786808380> -- In-Progress"

    def output(self):
        return (f"**Background:** {self.background}\n"
                f"**Skills:** {self.skills}\n"
                f"**Tools/Languages:** {self.tools}\n"
                f"**Feat:** {self.feat}\n"
                f"**Equipment:** {self.equipment}")


class NewCharacterApplication(object):
    message: discord.Message = None
    name: str = ""
    freeroll: bool = False
    base_scores: AppBaseScores = AppBaseScores()
    species: AppSpecies = AppSpecies()
    char_class: AppClass = AppClass()
    background: AppBackground = AppBackground()
    credits: str = "0"
    homeworld: str = ""
    motivation: str = ""
    link: str = ""
    hp: str = ""
    level: str = ""
    draft: bool = True

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def can_submit(self):
        if 'Complete' in self.base_scores.status() and 'Complete' in self.species.status() and 'Complete' in self.char_class.status() and 'Complete' in self.background.status() and self.motivation != '' and self.name != '' and self.link != '' and self.homeworld != '':
            return True
        else:
            return False


    def format_app(self, owner: discord.Member, character: PlayerCharacter, archivist: discord.Role | None = None, draft: bool = False):
        hp_str = f"**HP:** {self.hp}\n\n" if self.hp != "" else ""
        level_str=f"**Level:** {self.level}\n" if self.level != "" else ""
        draft_str = f"**__DRAFT__**\n" if draft else ""
        return (
            f"{draft_str}"
            f"**{'Free Reroll' if self.freeroll else 'Reroll' if character else 'New Character'}** | {archivist.mention if archivist else 'Archivist'}\n"
            f"**Name:** {self.name}\n"
            f"**Player:** {owner.mention}\n\n"
            f"**Base Scores:**\n"
            f"STR: {self.base_scores.str}\n"
            f"DEX: {self.base_scores.dex}\n"
            f"CON: {self.base_scores.con}\n"
            f"INT: {self.base_scores.int}\n"
            f"WIS: {self.base_scores.wis}\n"
            f"CHA: {self.base_scores.cha}\n\n"
            f"{level_str}"
            f"{hp_str}"
            f"**Species:** {self.species.species}\n"
            f"ASIs: {self.species.asi}\n"
            f"Features: {self.species.feats}\n\n"
            f"**Class:** {self.char_class.char_class}\n"
            f"Skills: {self.char_class.skills}\n"
            f"Features: {self.char_class.feats}\n\n"
            f"**Background:** {self.background.background}\n"
            f"Skills: {self.background.skills}\n"
            f"Tools/Languages: {self.background.tools}\n"
            f"Feat: {self.background.feat}\n\n"
            f"**Equipment:**\n"
            f"Class: {self.char_class.equipment}\n"
            f"Background: {self.background.equipment}\n"
            f"Credits: {self.credits}\n\n"
            f"**Homeworld:** {self.homeworld}\n"
            f"**Motivation for working with the New Republic:** {self.motivation}\n\n"
            f"**Link:** {self.link}"
        )

class LevelUpApplication(object):
    message: discord.Message = None
    level: str = ""
    hp: str = ""
    feats: str = ""
    changes: str = ""
    link: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def format_app(self, owner: discord.Member, character: PlayerCharacter, archivist: discord.Role):
        return (
            f"**Level Up** | {archivist.mention}\n"
            f"**Name:** {character.name}\n"
            f"**Player:** {owner.mention}\n\n"
            f"**New Level:** {self.level}\n"
            f"**HP:** {self.hp}\n"
            f"**New Features:** {self.feats}\n"
            f"**Changes:** {self.changes}\n"
            f"**Link:** {self.link}\n\n"
        )
