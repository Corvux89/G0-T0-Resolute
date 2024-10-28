import sqlalchemy as sa
import discord

from discord import ApplicationContext
from marshmallow import Schema, fields, post_load
from sqlalchemy import Column, Integer, BigInteger, String, BOOLEAN, and_
from sqlalchemy.sql import FromClause
from sqlalchemy.dialects.postgresql import insert, ARRAY

from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.models.categories import CharacterArchetype, CharacterClass, CharacterSpecies, StarshipRole
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models import metadata

class PlayerCharacter(object): 
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.species: CharacterSpecies = kwargs.get('species')
        self.credits = kwargs.get('credits', 0)
        self.level = kwargs.get('level', 1)
        self.player_id = kwargs.get('player_id')
        self.guild_id = kwargs.get('guild_id')
        self.reroll = kwargs.get('reroll', False)
        self.active = kwargs.get('active', True)
        self.freeroll_from = kwargs.get('freeroll_from', None)

        # Virtual Attributes
        self.classes: list[PlayerCharacterClass] = []
        self.starships: list[CharacterStarship] = []

    
    def inline_description(self, compendium: Compendium):
        class_str = "".join([f" {c.get_formatted_class()}" for c in self.classes])
        str = f"**{self.name}** - Level {self.level} {self.species.value} [{class_str}] ({self.credits:,} credits)" 

        if len(self.starships) > 0:
            str += "\n"
            str += f"\n".join([f"{ZWSP3}{s.get_formatted_starship(compendium)}" for s in self.starships])

        return str
    
    def inline_class_description(self):
        class_str = "".join([f" {c.get_formatted_class()}" for c in self.classes])
        return f"**{self.name}** - Level {self.level} {self.species.value} [{class_str}]" 


    def is_valid(self, guild: PlayerGuild):
        return (hasattr(self, "name") and self.name is not None and 
                hasattr(self, "species") and self.species is not None and
                hasattr(self, "level") and 0 < self.level <= guild.max_level)
        

    def get_member(self, ctx: ApplicationContext) -> discord.Member:
        return discord.utils.get(ctx.guild.members, id=self.player_id)

    def get_member_mention(self, ctx: ApplicationContext):
        try:
            name = discord.utils.get(ctx.guild.members, id=self.player_id).mention
            pass
        except:
            name = f"Player {self.player_id} not found on this server for character {self.name}"
            pass
        return name

    def mention(self) -> str:
        return f"<@{self.player_id}>"

characters_table = sa.Table(
    "characters",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("name", String, nullable=False),
    Column("species", Integer, nullable=False),  # ref: > c_character_race.id
    Column("credits", Integer, nullable=False, default=0),
    Column("level", Integer, nullable=False, default=1),
    Column("player_id", BigInteger, nullable=False),
    Column("guild_id", BigInteger, nullable=False),  # ref: > guilds.id
    Column("reroll", BOOLEAN, nullable=True),
    Column("active", BOOLEAN, nullable=False, default=True),
    Column("freeroll_from", Integer, nullable=True, default=None)
)

class CharacterSchema(Schema):
    compendium: Compendium
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    species = fields.Method(None, "load_species")
    credits = fields.Integer(required=True)
    level = fields.Integer(required=True)
    player_id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    reroll = fields.Boolean()
    active = fields.Boolean(required=True)
    freeroll_from = fields.Integer(allow_none=True)


    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_character(self, data, **kwargs):
        return PlayerCharacter(**data)

    def load_species(self, value):
        return self.compendium.get_object(CharacterSpecies, value)

def get_active_characters(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id,
             characters_table.c.active == True)
    )

def get_all_characters(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id))

def get_player_character_history(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())


def get_character_from_id(char_id: int) -> FromClause:
   return characters_table.select().where(characters_table.c.id == char_id)

def get_charcters_from_player_list(players: list[int], guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id.in_(players), characters_table.c.active == True,
             characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())

def get_guild_characters_query(guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.active == True, characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())


def upsert_character_query(character: PlayerCharacter):
    if hasattr(character, "id") and character.id is not None:
        update_dict = {
        'name': character.name,
        'species': character.species.id,
        'credits': character.credits,
        'level': character.level,
        'player_id': character.player_id,
        'guild_id': character.guild_id,
        'reroll': character.reroll,
        'active': character.active,
        'freeroll_from': character.freeroll_from if hasattr(character, 'freeroll_from') else None
        }
        
        update_statement = characters_table.update().where(characters_table.c.id == character.id).values(**update_dict).returning(characters_table)
        return update_statement


    insert_statement = insert(characters_table).values(
        name=character.name,
        species=character.species.id,
        credits=character.credits,
        level=character.level,
        player_id=character.player_id,
        guild_id=character.guild_id,
        reroll=character.reroll,
        active=character.active,
        freeroll_from=character.freeroll_from if hasattr(character, "freeroll_from") else None
    ).returning(characters_table)

    return insert_statement

class PlayerCharacterClass(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.character_id = kwargs.get('character_id')
        self.primary_class: CharacterClass = kwargs.get('primary_class')
        self.archetype: CharacterArchetype = kwargs.get('archetype')
        self.active = kwargs.get('active', True)

    def is_valid(self):
        self.active = True if not hasattr(self, "active") else self.active
        return (hasattr(self, "primary_class") and self.primary_class is not None)

    def get_formatted_class(self):
        if hasattr(self, "archetype") and self.archetype is not None:
            return f"{self.archetype.value} {self.primary_class.value}"
        elif hasattr(self, "primary_class") and self.primary_class is not None:
            return f"{self.primary_class.value}"
        else:
            return ""
        
character_class_table = sa.Table(
    "character_class",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("character_id", Integer, nullable=False),  # ref: > characters.id
    Column("primary_class", Integer, nullable=False),  # ref: > c_character_class.id
    Column("archetype", Integer, nullable=True),  # ref: > c_character_subclass.id
    Column("active", BOOLEAN, nullable=False, default=True)
)
        
class PlayerCharacterClassSchema(Schema):
    compendium: Compendium
    id = fields.Integer(required=True)
    character_id = fields.Integer(required=True)
    primary_class = fields.Method(None, "load_primary_class")
    archetype = fields.Method(None, "load_archetype", allow_none=True)
    active = fields.Boolean(required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_class(self, data, **kwargs):
        return PlayerCharacterClass(**data)

    def load_primary_class(self, value):
        return self.compendium.get_object(CharacterClass, value)

    def load_archetype(self, value):
        return self.compendium.get_object(CharacterArchetype, value)

    
def get_character_class(char_id: int) -> FromClause:
    return character_class_table.select().where(
        and_(character_class_table.c.character_id == char_id, character_class_table.c.active == True)
    ).order_by(character_class_table.c.id.asc())

def upsert_class_query(char_class: PlayerCharacterClass):
    if hasattr(char_class, "id") and char_class.id is not None:
        update_dict = {
            'character_id': char_class.character_id,
            'primary_class': char_class.primary_class.id,
            'archetype': None if not hasattr(char_class.archetype, 'id') else char_class.archetype.id,
            'active': char_class.active
        }
        
        update_statement = character_class_table.update().where(character_class_table.c.id == char_class.id).values(**update_dict).returning(character_class_table)
        return update_statement
    
    insert_statement = insert(character_class_table).values(
        character_id=char_class.character_id,
        primary_class=char_class.primary_class.id,
        archetype=None if not hasattr(char_class.archetype, "id") else char_class.archetype.id
    ).returning(character_class_table)

    return insert_statement

class CharacterStarship(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.character_id: list[int] = kwargs.get('character_id', [])
        self.name = kwargs.get('name')
        self.transponder = kwargs.get('transponder')
        self.starship: StarshipRole = kwargs.get('starship')
        self.tier = kwargs.get('tier', 0)
        self.active = kwargs.get('active', True)

        # Virtual
        self.owners: list[PlayerCharacter] = []

    def get_formatted_starship(self, compendium):
        return f"**{self.name}** *(Tier {self.tier} {self.starship.get_size(compendium).value} {self.starship.value})*"
    
character_starship_table = sa.Table(
    "character_starship",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("character_id", ARRAY(BigInteger), nullable=False),
    Column("name", String, nullable=False),
    Column("transponder", String, nullable=True),
    Column("starship", Integer, nullable=False),
    Column("tier", Integer, nullable=True),
    Column("active", BOOLEAN, nullable=False, default=True)
)

class CharacterStarshipSchema(Schema):
    compendium: Compendium
    id = fields.Integer(required=True)
    character_id = fields.List(fields.Integer, required=True)
    name = fields.String(required=True)
    transponder = fields.String(allow_none=True, required=False)
    starship = fields.Method(None, "load_starship")
    tier = fields.Integer(required=False, default=None, allow_none=True)
    active = fields.Boolean(required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_character_starship(self, data, **kwargs):
        return CharacterStarship(**data)

    def load_starship(self, value):
        return self.compendium.get_object(StarshipRole, value)

def get_character_starships(char_id: int) -> FromClause:
    return character_starship_table.select().where(
        and_(character_starship_table.c.character_id.contains([char_id]), character_starship_table.c.active == True)
    ).order_by(character_starship_table.c.id.asc())

def upsert_starship_query(starship: CharacterStarship):
    if hasattr(starship, "id") and starship.id is not None:
        update_dict = {
            "character_id": starship.character_id,
            "name": starship.name,
            "transponder": starship.transponder,
            "active": starship.active,
            "tier": starship.tier
        }

        update_statement = character_starship_table.update().where(character_starship_table.c.id == starship.id).values(**update_dict).returning(character_starship_table)
        return update_statement
    
    insert_statement = insert(character_starship_table).values(
        character_id=starship.character_id,
        name=starship.name,
        starship=starship.starship.id,
        active=starship.active,
        tier=starship.tier
    ).returning(character_starship_table)

    return insert_statement
