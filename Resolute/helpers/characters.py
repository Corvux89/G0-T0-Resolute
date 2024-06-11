
from Resolute.bot import G0T0Bot
from Resolute.models.objects.characters import CharacterSchema, CharacterStarship, CharacterStarshipSchema, PlayerCharacter, PlayerCharacterClass, PlayerCharacterClassSchema, get_active_characters, get_all_characters, get_character_class, get_character_from_id, get_character_starships, upsert_class_query, upsert_starship_query


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

    character = CharacterSchema(bot.compendium).load(row)

    return character

async def upsert_starship(bot: G0T0Bot, starship: CharacterStarship) -> CharacterStarship:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_starship_query(starship))
        row = await results.first()

    starship = CharacterStarshipSchema(bot.compendium).load(row)

    return starship