import discord
import sqlalchemy as sa

from marshmallow import Schema, fields
from sqlalchemy import Column, BigInteger, String
from sqlalchemy.sql.selectable import TableClause, FromClause

from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models import metadata

class AppBaseScores(object):
    def __init__(self, **kwargs):
        self.str = kwargs.get('str')
        self.dex = kwargs.get('dex')
        self.con = kwargs.get('con')
        self.int = kwargs.get('int')
        self.wis = kwargs.get('wis')
        self.cha = kwargs.get('cha')

    def status(self):
        attributes = [self.str, self.dex, self.con, self.int, self.wis, self.cha]

        return status(attributes)

    def output(self):
        return (f"**STR:** {self.str}\n" 
               f"**DEX:** {self.dex}\n" 
               f"**CON:** {self.con}\n"
               f"**INT:** {self.int}\n"
               f"**WIS:** {self.wis}\n"
               f"**CHA:** {self.cha}\n")


class AppSpecies(object):
    def __init__(self, **kwargs):
        self.species = kwargs.get('species')
        self.asi = kwargs.get('asi')
        self.feats = kwargs.get('feats')

    def get_field(self):
        if not hasattr(self, "species"):
            return "Not set"
        else:
            return f"**{self.species}**\nASIs: {self.asi}\nFeatures: {self.feats}"

    def status(self):
        attributes = [self.species, self.asi, self.feats]

        return status(attributes )

    def output(self):
        return (f"**Species:** {self.species}\n"
                f"**ASI:** {self.asi}\n"
                f"**Features:** {self.feats}\n")


class AppClass(object):
    def __init__(self, **kwargs):
        self.char_class = kwargs.get('char_class')
        self.skills = kwargs.get('skills')
        self.feats = kwargs.get('feats')
        self.equipment = kwargs.get('equipment')

    def status(self):
        attributes = [self.char_class, self.skills, self.feats, self.equipment]

        return status(attributes)

    def output(self):
        return (f"**Class:** {self.char_class}\n"
                f"**Skills:** {self.skills}\n"
                f"**Features:** {self.feats}\n"
                f"**Equipment:** {self.equipment}")


class AppBackground(object):
    background: str = ""
    skills: str = ""
    tools: str = ""
    feat: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        self.background = kwargs.get('background')
        self.skills = kwargs.get('skills')
        self.tools = kwargs.get('tools')
        self.feat = kwargs.get('feat')
        self.equipment = kwargs.get('equipment')

    def status(self):
        attributes = [self.background, self.skills, self.tools, self.feat, self.equipment]
        return status(attributes)

    def output(self):
        return (f"**Background:** {self.background}\n"
                f"**Skills:** {self.skills}\n"
                f"**Tools/Languages:** {self.tools}\n"
                f"**Feat:** {self.feat}\n"
                f"**Equipment:** {self.equipment}")


class NewCharacterApplication(object):
    def __init__(self, **kwargs):
        self.message: discord.Message = kwargs.get('message')
        self.character: PlayerCharacter = kwargs.get('character')
        self.name = kwargs.get('name')
        self.type = kwargs.get('type', "New Character")
        self.base_scores: AppBaseScores = kwargs.get('base_scores', AppBaseScores())
        self.species: AppSpecies = kwargs.get('species', AppSpecies())
        self.char_class: AppClass = kwargs.get('char_class', AppClass())
        self.background: AppBackground = kwargs.get('background', AppBackground())
        self.credits = kwargs.get('credits', "0")
        self.homeworld = kwargs.get('homeworld')
        self.motivation = kwargs.get('motivation')
        self.link = kwargs.get('link')
        self.hp = kwargs.get('hp')
        self.level = kwargs.get('level', "1")

    def can_submit(self):
        if 'Complete' in self.base_scores.status() and 'Complete' in self.species.status() and 'Complete' in self.char_class.status() and 'Complete' in self.background.status() and self.motivation != '' and self.name != '' and self.link != '' and self.homeworld != '':
            return True
        else:
            return False


    def format_app(self, owner: discord.Member, archivist: discord.Role = None):
        hp_str = f"**HP:** {self.hp}\n\n" if self.hp != "" else ""
        level_str=f"**Level:** {self.level}\n" if self.level != "" else "" 
        reroll_str=f"**Reroll From:** {self.character.name} [{self.character.id}]\n" if self.type in ["Reroll", "Free Reroll"] else ""
        return (
            f"**{self.type}** | {archivist.mention if archivist else 'Archivist'}\n"
            f"{reroll_str}"
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
    
ref_applications_table = sa.Table(
    "ref_character_applications",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("application", String, nullable=False)
)

class ApplicationSchema(Schema):
    id = fields.Integer(required=True)
    application = fields.String(required=True)

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
    
def status(attributes = []) -> str:
    if all(a is None for a in attributes):
        return "<:x:983576786447245312> -- Incomplete" 
    elif all(a is not None for a in attributes):
        return "<:white_check_mark:983576747381518396> -- Complete"
    else:
        return "<:pencil:989284061786808380> -- In-Progress"

class LevelUpApplication(object):
    def __init__(self, **kwargs):
        self.message: discord.Message = kwargs.get('message')
        self.level = kwargs.get('level')
        self.hp = kwargs.get('hp')
        self.feats = kwargs.get('feats')
        self.changes = kwargs.get('changes')
        self.link = kwargs.get('link')
        self.character: PlayerCharacter = kwargs.get('character')
        self.type="Level Up"


    def format_app(self, owner: discord.Member, archivist: discord.Role = None):
        return (
            f"**Level Up** | {archivist.mention if archivist else 'Archivist'}\n"
            f"**Name:** {self.character.name} [{self.character.id}]\n"
            f"**Player:** {owner.mention}\n\n"
            f"**New Level:** {self.level}\n"
            f"**HP:** {self.hp}\n"
            f"**New Features:** {self.feats}\n"
            f"**Changes:** {self.changes}\n"
            f"**Link:** {self.link}\n\n"
        )