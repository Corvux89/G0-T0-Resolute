import logging
import re
from timeit import default_timer as timer

import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import get_selection
from Resolute.helpers.guilds import get_guild
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import (CharacterRenown,
                                                CharacterSchema,
                                                PlayerCharacter,
                                                PlayerCharacterClass,
                                                PlayerCharacterClassSchema,
                                                RenownSchema,
                                                get_active_player_characters,
                                                get_all_player_characters,
                                                get_character_class,
                                                get_character_from_id,
                                                get_character_renown,
                                                get_guild_characters_query,
                                                upsert_character_query,
                                                upsert_character_renown_query,
                                                upsert_class_query)
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

async def get_characters(bot: G0T0Bot, player_id: int, guild_id: int, inactive: bool = False) -> list[PlayerCharacter]:
    async with bot.db.acquire() as conn:
        if inactive:
            results = await conn.execute(get_all_player_characters(player_id, guild_id))
        else:
            results = await conn.execute(get_active_player_characters(player_id, guild_id))
        rows = await results.fetchall()

    character_list = [CharacterSchema(bot.compendium).load(row) for row in rows]

    for character in character_list:
        async with bot.db.acquire() as conn:
            class_results = await conn.execute(get_character_class(character.id))
            class_rows = await class_results.fetchall()

            renown_results = await conn.execute(get_character_renown(character.id))
            renown_rows = await renown_results.fetchall()

        character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]
        character.renown = [RenownSchema(bot.compendium).load(row) for row in renown_rows]

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

        renown_results = await conn.execute(get_character_renown(char_id))
        renown_rows = await renown_results.fetchall()

    character = CharacterSchema(bot.compendium).load(row)
    character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]
    character.renown = [RenownSchema(bot.compendium).load(row) for row in renown_rows]

    return character

async def upsert_renown(bot: G0T0Bot, renown: CharacterRenown) -> CharacterRenown:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_character_renown_query(renown))
        row = await results.first()

    renown = RenownSchema(bot.compendium).load(row)

    return renown

async def upsert_character(bot: G0T0Bot, character: PlayerCharacter) -> PlayerCharacter:
    async with bot.db.acquire() as conn:
        results = await conn.execute(upsert_character_query(character))
        row = await results.first()

    character = CharacterSchema(bot.compendium).load(row)

    async with bot.db.acquire() as conn:
        class_results = await conn.execute(get_character_class(character.id))
        class_rows = await class_results.fetchall()

    character.classes = [PlayerCharacterClassSchema(bot.compendium).load(row) for row in class_rows]

    return character

async def create_new_character(bot: G0T0Bot, type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs) -> PlayerCharacter:
    start = timer()

    old_character: PlayerCharacter = kwargs.get('old_character')

    new_character.player_id = player.id
    new_character.guild_id = player.guild_id        

    if type in ['freeroll', 'death']:
        new_character.reroll = True
        old_character.active = False

        if type == 'freeroll':
            new_character.freeroll_from = old_character.id
        else:
            player.handicap_amount = 0

        old_character = await upsert_character(bot, old_character)

    new_character = await upsert_character(bot, new_character)

    new_class.character_id = new_character.id
    new_class = await upsert_class(bot, new_class)

    new_character.classes.append(new_class)

    end = timer()

    log.info(f"Time to create character {new_character.id}: [ {end-start:.2f} ]s")

    return new_character

async def get_webhook_character(bot: G0T0Bot, player: Player, channel: discord.TextChannel) -> PlayerCharacter:
    if character := player.get_channel_character(channel):
        return character
    elif character := player.get_primary_character():
        character.channels.append(channel.id)
        await upsert_character(bot, character)
        return character
    
    character = player.characters[0]
    character.primary_character = True
    character.channels.append(channel.id)
    await upsert_character(bot, character)
    return character

async def get_all_guild_characters(bot: G0T0Bot, gulid_id: int) -> list[PlayerCharacter]:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_guild_characters_query(gulid_id))
        rows = await results.fetchall()

    character_list = [CharacterSchema(bot.compendium).load(row) for row in rows]

    return character_list

async def update_character_renown(bot: G0T0Bot, character: PlayerCharacter, faction: Faction, renown: int) -> CharacterRenown:
    character_renown = next((r for r in character.renown if r.faction.id == faction.id),
                            CharacterRenown(faction=faction,
                                            character_id=character.id))
    
    character_renown.renown += renown

    return await upsert_renown(bot, character_renown)

def find_character_by_name(name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
    direct_matches = [c for c in characters if c.name.lower() == name.lower()]

    # Prioritize main name first
    if not direct_matches:
        direct_matches = [c for c in characters if c.nickname and c.nickname.lower() == name.lower()]

    if not direct_matches:
        partial_matches = [c for c in characters if name.lower() in c.name.lower() or (c.nickname and name.lower() in c.nickname.lower())]
        return partial_matches
    
    return direct_matches  

async def handle_character_mention(ctx: discord.ApplicationContext | discord.Interaction, content: str, DM: bool = True) -> str:
    mentioned_characters = []

    if char_mentions := re.findall(r'{\$([^}]*)}', content):
        g = await get_guild(ctx.bot, ctx.guild.id)
        guild_characters = await get_all_guild_characters(ctx.bot, g.id)
        for mention in char_mentions:
            matches = find_character_by_name(mention, guild_characters)
            mention_char = None

            if len(matches) == 1:
                mention_char = matches[0]
            elif len(matches) > 1:
                choices = [f"{c.name} [{ctx.guild.get_member(c.player_id).display_name}]" for c in matches]
                if choice := await get_selection(ctx, choices, True, True, f"Type your choice in {ctx.channel.jump_url}", True, f"Found multiple matches for `{mention}`"):
                    mention_char = matches[choices.index(choice)]

            if mention_char:
                if mention_char not in mentioned_characters:
                    mentioned_characters.append(mention_char)
                content = content.replace("{$" + mention + "}", f"[{mention_char.nickname if mention_char.nickname else mention_char.name}](<discord:///users/{mention_char.player_id}>)")
        if DM:
            for char in mentioned_characters:
                if member := ctx.guild.get_member(char.player_id):
                    try:
                        await member.send(f"{ctx.author.mention} directly mentioned `{char.name}` in:\n{ctx.channel.jump_url}")
                    except:
                        pass

    return content
