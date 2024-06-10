import re
import aiopg
import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.characters import get_character
from Resolute.models.objects.applications import AppBackground, AppBaseScores, AppClass, AppSpecies, ApplicationSchema, LevelUpApplication, NewCharacterApplication, delete_player_application, get_player_application, insert_player_application


async def upsert_application(db: aiopg.sa.Engine, player_id: int, application: str = None) -> None:
    async with db.acquire() as conn:
        await conn.execute(delete_player_application(player_id))
        if application:
            await conn.execute(insert_player_application(player_id, application))

def get_application_type(application: str) -> str:
    type_map = {
        "Reroll": "New",
        "Free Reroll": "New", 
        "New Character": "New",
        "Level Up": "Level"
    }

    type_match = re.search(r"^\*\*(.*?)\*\*\s\|", application, re.MULTILINE)

    if type_match:
        group = type_match.group(1).strip().replace('*', '')
        return type_map.get(group, "Unknown")
    
    return "Unknown"

async def get_cached_application(db: aiopg.sa.Engine, player_id: int) -> str:
    async with db.acquire() as conn:
        results = await conn.execute(get_player_application(player_id))
        row = await results.first()

    if row is None:
        return None
    
    application = ApplicationSchema().load(row)

    return application["application"]

async def get_new_character_application(bot: G0T0Bot, application_text: str = None, message: discord.Message = None):
    app_text = application_text or message.content

    def get_match(pattern, text, group=1, default=None):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(group) if match and match.group(group) != 'None' else default
    

    type_match = re.search(r"^\*\*(.*?)\*\*\s\|", app_text, re.MULTILINE)

    base_scores_match = re.search(r"STR: (.+?)\n"
                                 r"DEX: (.+?)\n"
                                 r"CON: (.+?)\n"
                                 r"INT: (.+?)\n"
                                 r"WIS: (.+?)\n"
                                 r"CHA: (.+?)\n", app_text)
    
    species_match = re.search(r"\*\*Species:\*\* (.+?)\n"
                              r"ASIs: (.+?)\n"
                              r"Features: (.+?)\n", app_text, re.DOTALL)
    
    char_class_match = re.search(r"\*\*Class:\*\* (.+?)\n"
                                 r"Skills: (.*?)(?=\nFeatures:)\n"
                                 r"Features: (.*?)(?=\n\n\*\*)", app_text, re.DOTALL)
    
    background_match = re.search(r"\*\*Background:\*\* (.+?)\n"
                                 r"Skills: (.+?)\n"
                                 r"Tools/Languages: (.+?)\n"
                                 r"Feat: (.+?)\n\n", app_text)
    
    equip_match = re.search(r"\*\*Equipment:\*\*\n"
                            r"Class: (.*?)(?=\nBackground:)\n"
                            r"Background: (.*?)(?=\nCredits:)", app_text, re.DOTALL)

    char_id = get_match(r"\*\*Reroll\sFrom:\*\*(.*?)\s\[(\d+)\]\n", app_text, 2)

    application = NewCharacterApplication(
        message=message,
        name=get_match(r"\*\*Name:\*\* (.+?)\n", app_text),
        type=type_match.group(1).strip().replace('*', '') if type_match else "New Character",
        base_scores=AppBaseScores(
            str=base_scores_match.group(1) if base_scores_match else "", 
            dex=base_scores_match.group(2) if base_scores_match else "",
            con=base_scores_match.group(3) if base_scores_match else "",
            int=base_scores_match.group(4) if base_scores_match else "",
            wis=base_scores_match.group(5) if base_scores_match else "",
            cha=base_scores_match.group(6) if base_scores_match else ""
        ),
        species=AppSpecies(
            species=species_match.group(1) if species_match else "",
            asi=species_match.group(2) if species_match else "",
            feats=species_match.group(3) if species_match else ""
        ),
        char_class=AppClass(
            char_class=char_class_match.group(1) if char_class_match else "",
            skills=char_class_match.group(2) if char_class_match else "",
            feats=char_class_match.group(3) if char_class_match else "",
            equipment=equip_match.group(1) if equip_match else ""
        ),
        background=AppBackground(
            background=background_match.group(1) if background_match else "",
            skills=background_match.group(2) if background_match else "",
            tools=background_match.group(3) if background_match else "",
            feat=background_match.group(4) if background_match else "",
            equipment=equip_match.group(2) if equip_match else ""
        ),
        credits=get_match(r"Credits: (.+?)\n", app_text, 1, "0"),
        homeworld=get_match(r"\*\*Homeworld:\*\* (.+?)\n", app_text),
        motivation=get_match(r"\*\*Motivation for working with the New Republic:\*\* (.*?)(?=\n\n\*\*)", app_text),
        link=get_match(r"\*\*Link:\*\* (.+)", app_text),
        level=get_match(r"\*\*Level:\*\* (.+?)\n", app_text),
        hp=get_match(r"\*\*HP:\*\* (.+?)\n", app_text)
    )

    if char_id:
        application.character = await get_character(bot, char_id)

    return application

async def get_level_up_application(bot: G0T0Bot, application_text: str = None, message: discord.Message = None) -> LevelUpApplication:
    app_text = application_text or message.content

    def get_match(pattern, text, group=1, default=None):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(group) if match and match.group(group) != 'None' else default
    
    char_id = get_match(r"\*\*Name:\*\*(.*?)\s\[(\d+)\]\n", app_text, 2)
    
    application = LevelUpApplication(
        message=message,
        level=get_match(r"\*\*New Level:\*\* (.+?)\n", app_text),
        hp=get_match(r"\*\*HP:\*\* (.+?)\n", app_text),
        feats=get_match(r"\*\*New Features:\*\* (.+?)\n", app_text),
        changes=get_match(r"\*\*Changes:\*\* (.+?)(?=\n\*\*)", app_text),
        link=get_match(r"\*\*Link:\*\* (.+)", app_text)
    )

    if char_id:
        application.character = await get_character(bot, char_id)

    return application
