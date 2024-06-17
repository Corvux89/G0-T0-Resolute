import logging
import discord

from Resolute.bot import G0T0Bot
from Resolute.models.objects.characters import CharacterSchema, CharacterStarship, CharacterStarshipSchema, PlayerCharacter, PlayerCharacterClass, PlayerCharacterClassSchema, get_active_characters, get_all_characters, get_character_class, get_character_from_id, get_character_starships, upsert_character_query, upsert_class_query, upsert_starship_query
from Resolute.models.objects.players import Player
from timeit import default_timer as timer

log = logging.getLogger(__name__)


async def get_characters(bot: G0T0Bot, player_id: int, guild_id: int, inactive: bool = False) -> list[PlayerCharacter]:
    async with bot.db.acquire() as conn:
        if inactive:
            results = await conn.execute(get_all_characters(player_id, guild_id))
        else:
            results = await conn.execute(get_active_characters(player_id, guild_id))
        rows = await results.fetchall()

    character_list = [CharacterSchema(bot.compendium).load(row) for row in rows]

    for character in character_list:
        async with bot.db.acquire() as conn:
            class_results = await conn.execute(get_character_class(character.id))
            class_rows = await class_results.fetchall()

            starship_results = await conn.execute(get_character_starships(character.id))
            starship_rows = await starship_results.fetchall()

        character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]
        character.starships = [CharacterStarshipSchema(bot.compendium).load(row) for row in starship_rows]

    return character_list

async def upsert_class(bot: G0T0Bot, char_class: PlayerCharacterClass) -> PlayerCharacterClass:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_class_query(char_class))
        row = await results.first()

    new_class = PlayerCharacterClassSchema(bot.compendium).load(row)

    return new_class

async def get_character(bot: G0T0Bot, char_id: int) -> PlayerCharacter:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_character_from_id(char_id))
        row = await results.first()

        class_results = await conn.execute(get_character_class(char_id))
        class_rows = await class_results.fetchall()

        starship_results = await conn.execute(get_character_starships(char_id))
        starship_rows = await starship_results.fetchall()

    character = CharacterSchema(bot.compendium).load(row)
    character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]
    character.starships = [CharacterStarshipSchema(bot.compendium).load(row) for row in starship_rows]

    return character

async def upsert_starship(bot: G0T0Bot, starship: CharacterStarship) -> CharacterStarship:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_starship_query(starship))
        row = await results.first()

    starship = CharacterStarshipSchema(bot.compendium).load(row)

    return starship

async def upsert_character(bot: G0T0Bot, character: PlayerCharacter) -> PlayerCharacter:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_character_query(character))
        row = await results.first()

    character = CharacterSchema(bot.compendium).load(row)

    async with bot.db.acquire() as conn:
        class_results = await conn.execute(get_character_class(character.id))
        class_rows = await class_results.fetchall()

        starship_results = await conn.execute(get_character_starships(character.id))
        starship_rows = await starship_results.fetchall()

    character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]
    character.starships = [CharacterStarshipSchema(bot.compendium).load(row) for row in starship_rows]

    return character

async def create_new_character(bot: G0T0Bot, type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs) -> PlayerCharacter:
    start = timer()

    old_character: PlayerCharacter = kwargs.get('old_character')
    transfer_ship: bool = kwargs.get('transfer_ship', False)

    new_character.player_id = player.id
    new_character.guild_id = player.guild_id

    if type == 'freeroll':
        new_character.freeroll_from = old_character.id

    if type in ['freeroll', 'death']:
        new_character.reroll = True
        old_character.active = False
        player.handicap_amount = 0

        old_character = await upsert_character(bot, old_character)

    new_character = await upsert_character(bot, new_character)

    new_class.character_id = new_character.id
    new_class = await upsert_class(bot, new_class)

    new_character.classes.append(new_class)

    if old_character:
        for ship in old_character.starships:
            if transfer_ship:
                ship.character_id.remove(old_character.id)
                ship.character_id.append(new_character.id)
                new_character.starships.append(ship)
            elif len(ship.character_id) == 1:
                ship.active = False
            
            await upsert_starship(bot, ship)
    end = timer()

    log.info(f"Time to create character {new_character.id}: [ {end-start:.2f} ]s")

    return new_character




