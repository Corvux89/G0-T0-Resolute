import aiopg.sa
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import BOOLEAN, BigInteger, Column, Integer, String, and_
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.sql import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories import (CharacterArchetype, CharacterClass,
                                        CharacterSpecies)
from Resolute.models.categories.categories import Faction
        

class CharacterRenown(object):
    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        self._db = db
        self._compendium = compendium

        self.id = kwargs.get("id")
        self.character_id = kwargs.get("character_id")
        self.faction: Faction = kwargs.get("faction")

        self.renown = kwargs.get("renown", 0)

    def get_formatted_renown(self):
        return f"**{self.faction.value}**: {max(0, self.renown)}"
    
    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_character_renown_query(self))
            row = await results.first()

        renown = RenownSchema(self._db, self._compendium).load(row)

        return renown

renown_table = sa.Table(
    "renown",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("character_id", Integer, nullable=False),  # ref: > characters.id
    Column("faction", Integer, nullable=False),
    Column("renown", Integer)
)

class RenownSchema(Schema):
    db: aiopg.sa.Engine
    compendium: Compendium

    id = fields.Integer(required=True)
    character_id = fields.Integer(required=True)
    faction = fields.Method(None, "load_faction")
    renown = fields.Integer()

    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium
        self.db = db

    @post_load
    def make_renown(self, data, **kwargs):
        renown = CharacterRenown(self.db, self.compendium, **data)
        return renown

    def load_faction(self, value):
        return self.compendium.get_object(Faction, value)

def get_character_renown(char_id: int) -> FromClause:
    return renown_table.select().where(
        renown_table.c.character_id == char_id
    ).order_by(renown_table.c.id.asc())

def upsert_character_renown_query(renown: CharacterRenown):
    if hasattr(renown, "id") and renown.id is not None:
        update_dict = {
            "character_id": renown.character_id,
            "faction": renown.faction.id,
            "renown": renown.renown
        }

        update_statement = renown_table.update().where(renown_table.c.id == renown.id).values(**update_dict).returning(renown_table)
        return update_statement

    insert_statement = insert(renown_table).values(
        character_id=renown.character_id,
        faction=renown.faction.id,
        renown=renown.renown
    ).returning(renown_table)

    return insert_statement

class PlayerCharacterClass(object):
    def __init__(self,db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        self._db = db
        self._compendium = compendium

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
        
    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_class_query(self))
            row = await results.first()

        new_class = PlayerCharacterClassSchema(self._db, self._compendium).load(row)

        return new_class
        
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
    db: aiopg.sa.Engine
    compendium: Compendium

    id = fields.Integer(required=True)
    character_id = fields.Integer(required=True)
    primary_class = fields.Method(None, "load_primary_class")
    archetype = fields.Method(None, "load_archetype", allow_none=True)
    active = fields.Boolean(required=True)

    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.compendium = compendium

    @post_load
    def make_class(self, data, **kwargs):
        cl = PlayerCharacterClass(self.db, self.compendium, **data)
        return cl

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

class PlayerCharacter(object): 
    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        self._db = db
        self._compendium = compendium

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
        self.primary_character = kwargs.get('primary_character', False)
        self.channels: list = kwargs.get('channels', [])
        self.faction: Faction = kwargs.get('faction')
        self.avatar_url = kwargs.get('avatar_url')
        self.nickname = kwargs.get('nickname')

        # Virtual Attributes
        self.classes: list[PlayerCharacterClass] = []
        self.renown: list[CharacterRenown] = []

    @property
    def total_renown(self):
        total = 0

        if hasattr(self, "renown") and self.renown:
            total += sum(ren.renown for ren in self.renown)
        return total
    
    def inline_description(self, compendium: Compendium):
        class_str = "".join([f" {c.get_formatted_class()}" for c in self.classes])
        str = f"**{self.name}** - Level {self.level} {self.species.value} [{class_str}] ({self.credits:,} credits)" 

        return str
    
    def inline_class_description(self):
        class_str = "".join([f" {c.get_formatted_class()}" for c in self.classes])
        return f"**{self.name}** - Level {self.level} {self.species.value} [{class_str}]" 


    def is_valid(self, max_level: int):
        return (hasattr(self, "name") and self.name is not None and 
                hasattr(self, "species") and self.species is not None and
                hasattr(self, "level") and 0 < self.level <= max_level)

    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_character_query(self))
            row = await results.first()

        character: PlayerCharacter = await CharacterSchema(self._db, self._compendium).load(row)

        return character

    
    async def update_renown(self, faction: Faction, renown: int) -> CharacterRenown:
        character_renown = next((r for r in self.renown if r.faction.id == faction.id), 
                                CharacterRenown(self._db, self._compendium,
                                    faction=faction,
                                    character_id=self.id))
        character_renown.renown += renown
        await character_renown.upsert()

        return character_renown


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
    Column("freeroll_from", Integer, nullable=True, default=None),
    Column("primary_character", BOOLEAN, nullable=False, default=False),
    Column("channels", ARRAY(BigInteger), nullable=False, default=[]),
    Column("faction", Integer, nullable=True),
    Column("avatar_url", String, nullable=True),
    Column("nickname", String, nullable=True)
)

class CharacterSchema(Schema):
    db: aiopg.sa.Engine
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
    primary_character = fields.Boolean(allow_none=True)
    channels = fields.List(fields.Integer, allow_none=False)
    faction = fields.Method(None, "load_faction", allow_none=True)
    avatar_url = fields.String(required=False, allow_none=True)
    nickname = fields.String(required=False, allow_none=True)

    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.compendium = compendium

    @post_load
    async def make_character(self, data, **kwargs):
        character = PlayerCharacter(self.db, self.compendium, **data)
        await self.get_classes(character)
        await self.get_renown(character)
        return character

    def load_species(self, value):
        return self.compendium.get_object(CharacterSpecies, value)
    
    def load_faction(self, value):
        return self.compendium.get_object(Faction, value)
    
    async def get_classes(self, character: PlayerCharacter):
        async with self.db.acquire() as conn:
            class_results = await conn.execute(get_character_class(character.id))
            class_rows = await class_results.fetchall()

        character.classes = [PlayerCharacterClassSchema(self.db, self.compendium).load(row) for row in class_rows]

    async def get_renown(self, character: PlayerCharacter):
        async with self.db.acquire() as conn:
            renown_results = await conn.execute(get_character_renown(character.id))
            renown_rows = await renown_results.fetchall()

        character.renown = [RenownSchema(self.db, self.compendium).load(row) for row in renown_rows]



def get_active_player_characters(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id,
             characters_table.c.active == True)
    )

def get_all_player_characters(player_id: int, guild_id: int) -> FromClause:
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
        'freeroll_from': character.freeroll_from if hasattr(character, 'freeroll_from') else None,
        "avatar_url": character.avatar_url,
        "channels": character.channels,
        "primary_character": character.primary_character,
        "faction": character.faction.id if character.faction else None,
        "nickname": character.nickname
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
        freeroll_from=character.freeroll_from if hasattr(character, "freeroll_from") else None,
        avatar_url=character.avatar_url,
        channels=character.channels,
        primary_character=character.primary_character,
        faction=character.faction.id if character.faction else None
    ).returning(characters_table)

    return insert_statement

