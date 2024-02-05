import re

import aiopg.sa
import discord
from discord import TextChannel, Role

from Resolute.bot import G0T0Bot
from Resolute.models.db_objects import RefCategoryDashboard, RefWeeklyStipend, GlobalPlayer, GlobalEvent, \
    NewCharacterApplication, AppBaseScores, AppSpecies, AppClass, AppBackground, LevelUpApplication
from Resolute.models.schemas import RefCategoryDashboardSchema, RefWeeklyStipendSchema, GlobalPlayerSchema, \
    GlobalEventSchema
from Resolute.queries import get_dashboard_by_category_channel, get_weekly_stipend_query, get_all_global_players, \
    get_active_global, get_global_player, delete_global_event, delete_global_players


async def get_dashboard_from_category_channel_id(category_channel_id: int,
                                                 db: aiopg.sa.Engine) -> RefCategoryDashboard | None:
    if category_channel_id is None:
        return None

    async with db.acquire() as conn:
        results = await conn.execute(get_dashboard_by_category_channel(category_channel_id))
        row = await results.first()

    if row is None:
        return None
    else:
        dashboard: RefCategoryDashboard = RefCategoryDashboardSchema().load(row)
        return dashboard


async def get_last_message(channel: TextChannel) -> discord.Message | None:
    last_message = channel.last_message
    hx=[]

    if last_message is None:
        try:
            hx = [msg async for msg in channel.history(limit=1)]
        except discord.errors.HTTPException:
            pass

        if len(hx) > 0:
            last_message = hx[0]
    if last_message is None:
        try:
            lm_id = channel.last_message_id
            last_message = await channel.fetch_message(lm_id) if lm_id is not None else None
        except discord.errors.HTTPException as e:
            print(f"Skipping channel {channel.name}: [ {e} ]")
            return None
    return last_message


async def get_weekly_stipend(db: aiopg.sa.Engine, role: Role) -> RefWeeklyStipend | None:
    async with db.acquire() as conn:
        results = await conn.execute(get_weekly_stipend_query(role.id))
        row = await results.first()

    if row is None:
        return None
    else:
        stipend: RefWeeklyStipend = RefWeeklyStipendSchema().load(row)
        return stipend


async def get_all_players(bot: G0T0Bot, guild_id: int) -> dict:
    players = dict()

    async with bot.db.acquire() as conn:
        async for row in conn.execute(get_all_global_players(guild_id)):
            if row is not None:
                player: GlobalPlayer = GlobalPlayerSchema(bot.compendium).load(row)
                players[player.player_id] = player

    return players


async def get_player(bot: G0T0Bot, gulid_id: int, player_id: int) -> GlobalPlayer | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_global_player(gulid_id, player_id))
        row = await results.first()

    if row is None:
        return None

    player: GlobalPlayer = GlobalPlayerSchema(bot.compendium).load(row)

    return player


async def get_global(bot: G0T0Bot, guild_id: int) -> GlobalEvent | None:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_active_global(guild_id))
        row = await results.first()

    if row is None:
        return None
    else:
        glob: GlobalEvent = GlobalEventSchema(bot.compendium).load(row)
        return glob


async def close_global(db: aiopg.sa.Engine, guild_id: int):
    async with db.acquire() as conn:
        await conn.execute(delete_global_event(guild_id))
        await conn.execute(delete_global_players(guild_id))


def get_new_character_application(message: discord.Message) -> NewCharacterApplication | None:
    app_text = message.content
    name_match = re.search(r"\*\*Name:\*\* (.+)", app_text)
    base_scores_match = re.search(r"STR: (.+?)\n"
                                  r"DEX: (.+?)\n"
                                  r"CON: (.+?)\n"
                                  r"INT: (.+?)\n"
                                  r"WIS: (.+?)\n"
                                  r"CHA: (.+?)", app_text)
    species_match = re.search(r"\*\*Species:\*\* (.+?)\n"
                              r"ASIs: (.+?)\n"
                              r"Features: (.*?)(?=\n\n\*\*)", app_text, re.DOTALL)
    class_match = re.search(r"\*\*Class:\*\* (.+?)\n"
                            r"Skills: (.*?)(?=\nFeatures:)\n"
                            r"Features: (.*?)(?=\n\n\*\*)", app_text, re.DOTALL)
    background_match = re.search(r"\*\*Background:\*\* (.+?)\n"
                                 r"Skills: (.+?)\n"
                                 r"Tools/Languages: (.+?)\n"
                                 r"Feat: (.+?)\n\n", app_text)
    equip_match = re.search(r"\*\*Equipment:\*\*\n"
                            r"Class: (.*?)(?=\nBackground:)\n"
                            r"Background: (.*?)(?=\nCredits:)", app_text, re.DOTALL)
    hp_match = re.search(r"\*\*HP:\*\* (.+?)\n", app_text)
    credits_match = re.search(r"\*\*Link:\*\* (.+)", app_text)
    level_match = re.search(r"\*\*Level:\*\* (.+?)\n", app_text)
    homeworld_match = re.search(r"\*\*Homeworld:\*\* (.+?)\n", app_text)
    motivation_match = re.search(r"\*\*Motivation for working with the New Republic:\*\* (.*?)(?=\n\n\*\*)", app_text, re.DOTALL)
    draft_match = re.search(r"\*\*__DRAFT__\*\*", app_text)
    link_match = re.search(r"\*\*Link:\*\* (.+)", app_text)

    application: NewCharacterApplication = NewCharacterApplication(
        message=message,
        name=name_match.group(1) if name_match else "",
        freeroll=True if re.search(r"^(.*?) \|", app_text, re.MULTILINE).group(1).replace('*','') == "Free Reroll" else False,
        base_scores=AppBaseScores(
            str=base_scores_match.group(1),
            dex=base_scores_match.group(2),
            con=base_scores_match.group(3),
            int=base_scores_match.group(4),
            wis=base_scores_match.group(5),
            cha=base_scores_match.group(6)
        ) if base_scores_match else AppBaseScores(),
        species=AppSpecies(
            species=species_match.group(1),
            asi=species_match.group(2),
            feats=species_match.group(3)
        ) if species_match else AppSpecies(),
        char_class=AppClass(
            char_class=class_match.group(1),
            skills=class_match.group(2),
            feats=class_match.group(3),
            equipment=equip_match.group(1)
        ) if class_match and equip_match else AppClass(),
        background=AppBackground(
            background=background_match.group(1),
            skills=background_match.group(2),
            tools=background_match.group(3),
            feat=background_match.group(4),
            equipment=equip_match.group(2)
        ) if background_match and equip_match else AppBackground(),
        credits=credits_match.group(1) if credits_match else 0,
        homeworld=homeworld_match.group(1) if homeworld_match else "",
        motivation=motivation_match.group(1) if motivation_match else "",
        link=link_match.group(1) if link_match else "",
        level=level_match.group(1) if level_match else '',
        hp=hp_match.group(1) if hp_match else '',
        draft=True if draft_match else False
    )
    return application


def get_level_up_application(message: discord.Message) -> LevelUpApplication | None:
    app_text = message.content
    application: LevelUpApplication = LevelUpApplication(
        message=message,
        level=re.search(r"\*\*New Level:\*\* (.+?)\n", app_text).group(1),
        hp=re.search(r"\*\*HP:\*\* (.+?)\n", app_text).group(1),
        feats=re.search(r"\*\*New Features:\*\* (.+?)(?=\n\*\*)", app_text,re.DOTALL).group(1),
        changes=re.search(r"\*\*Changes:\*\* (.+?)(?=\n\*\*)", app_text, re.DOTALL).group(1),
        link=re.search(r"\*\*Link:\*\* (.+)", app_text).group(1)
    )
    return application
