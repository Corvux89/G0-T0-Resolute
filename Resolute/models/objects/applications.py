import discord

from Resolute.models.objects.characters import PlayerCharacter

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

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def can_submit(self):
        if 'Complete' in self.base_scores.status() and 'Complete' in self.species.status() and 'Complete' in self.char_class.status() and 'Complete' in self.background.status() and self.motivation != '' and self.name != '' and self.link != '' and self.homeworld != '':
            return True
        else:
            return False


    def format_app(self, owner: discord.Member, character: PlayerCharacter, archivist: discord.Role | None = None):
        hp_str = f"**HP:** {self.hp}\n\n" if self.hp != "" else ""
        level_str=f"**Level:** {self.level}\n" if self.level != "" else ""
        return (
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