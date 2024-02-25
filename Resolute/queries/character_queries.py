from sqlalchemy import and_
from sqlalchemy.sql import FromClause

from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, CharacterStarship
from Resolute.models.db_tables import characters_table, character_class_table, character_starship_table


def get_active_character(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id,
             characters_table.c.active == True)
    )

def get_all_characters(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())


def get_character_from_id(char_id: int) -> FromClause:
    return characters_table.select().where(
        characters_table.c.id == char_id)


def insert_new_character(character: PlayerCharacter):
    return characters_table.insert().values(
        name=character.name,
        species=character.species.id,
        credits=character.credits,
        cc=character.cc,
        div_cc=character.div_cc,
        level=character.level,
        player_id=character.player_id,
        guild_id=character.guild_id,
        reroll=character.reroll,
        active=character.active,
        freeroll_from=character.freeroll_from if hasattr(character, 'freeroll_from') else None
    ).returning(characters_table)


def update_character(character: PlayerCharacter):
    return characters_table.update() \
        .where(characters_table.c.id == character.id) \
        .values(
        name=character.name,
        species=character.species.id,
        credits=character.credits,
        cc=character.cc,
        div_cc=character.div_cc,
        level=character.level,
        player_id=character.player_id,
        guild_id=character.guild_id,
        reroll=character.reroll,
        active=character.active,
        freeroll_from=character.freeroll_from
    )


def insert_new_class(char_class: PlayerCharacterClass):
    return character_class_table.insert().values(
        character_id=char_class.character_id,
        primary_class=char_class.primary_class.id,
        archetype=None if not hasattr(char_class.archetype, "id") else char_class.archetype.id,
        active=char_class.active
    )


def update_class(char_class: PlayerCharacterClass):
    return character_class_table.update()\
        .where(character_class_table.c.id == char_class.id) \
        .values(
        primary_class=char_class.primary_class.id,
        archetype=None if not hasattr(char_class.archetype, "id") else char_class.archetype.id,
        active=char_class.active
    )


def get_character_class(char_id: int) -> FromClause:
    return character_class_table.select().where(
        and_(character_class_table.c.character_id == char_id, character_class_table.c.active == True)
    ).order_by(character_class_table.c.id.asc())


def get_multiple_characters(players: list[int], guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id.in_(players), characters_table.c.active == True,
             characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())


def get_characters(guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.active == True, characters_table.c.guild_id == guild_id)
    ).order_by(characters_table.c.id.desc())


def insert_new_starship(starship: CharacterStarship):
    return character_starship_table.insert().values(
        character_id=starship.character_id,
        name=starship.name,
        starship=starship.starship.id,
        active=starship.active,
        tier=starship.tier
    ).returning(character_starship_table)


def update_starship(starship: CharacterStarship):
    return character_starship_table.update()\
        .where(character_starship_table.c.id == starship.id)\
        .values(
        character_id=starship.character_id,
        name=starship.name,
        transponder=starship.transponder,
        active=starship.active,
        tier=starship.tier
    )

def get_character_starships(char_id: int) -> FromClause:
    return character_starship_table.select().where(
        and_(character_starship_table.c.character_id.contains([char_id]), character_starship_table.c.active == True)
    ).order_by(character_starship_table.c.id.asc())

def get_starship_by_transponder(tran_code: str) -> FromClause:
    return character_starship_table.select().where(
        and_(character_starship_table.c.transponder == tran_code, character_starship_table.c.active == True)
    )