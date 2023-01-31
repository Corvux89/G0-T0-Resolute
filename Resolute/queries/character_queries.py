from sqlalchemy import and_
from sqlalchemy.sql import FromClause

from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass
from Resolute.models.db_tables import characters_table, character_class_table


def get_active_character(player_id: int, guild_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.player_id == player_id, characters_table.c.guild_id == guild_id,
             characters_table.c.active == True)
    )


def get_character_from_id(char_id: int) -> FromClause:
    return characters_table.select().where(
        and_(characters_table.c.id == char_id, characters_table.c.active == True)
    )


def insert_new_character(character: PlayerCharacter):
    return characters_table.insert().values(
        name=character.name,
        species=character.species.id,
        credits=character.credits,
        cc=character.cc,
        div_cc=character.div_cc,
        level=character.level,
        enhanced_items=character.enhanced_items,
        player_id=character.player_id,
        guild_id=character.guild_id,
        reroll=character.reroll,
        active=character.active
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
        enhanced_items=character.enhanced_items,
        player_id=character.player_id,
        guild_id=character.guild_id,
        reroll=character.reroll,
        active=character.active
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
