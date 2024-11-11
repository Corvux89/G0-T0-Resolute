import calendar
from datetime import datetime, timezone

import discord
import sqlalchemy as sa
from discord import ApplicationContext
from marshmallow import Schema, fields, post_load
from sqlalchemy import (BOOLEAN, TIMESTAMP, BigInteger, Column, Integer,
                        String, and_, case, func, select)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories import Activity
from Resolute.models.categories.categories import Faction


class DBLog(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.author = kwargs.get('author')
        self.player_id = kwargs.get('player_id')
        self.guild_id = kwargs.get('guild_id')
        self.cc = kwargs.get('cc', 0)
        self.credits = kwargs.get('credits', 0)
        self.character_id = kwargs.get('character_id')
        self.activity: Activity = kwargs.get('activity')
        self.notes = kwargs.get('notes')
        self.adventure_id = kwargs.get('adventure_id')
        self.renown = kwargs.get('renown', 0)
        self.faction: Faction = kwargs.get('faction')
        self.invalid = kwargs.get('invalid', False)
        self.created_ts = kwargs.get('created_ts', datetime.now(timezone.utc))

    def get_author(self, ctx: ApplicationContext) -> discord.Member | None:
        return ctx.guild.get_member(self.author)
    
    @property
    def epoch_time(self):
        return calendar.timegm(self.created_ts.utctimetuple())
    
log_table = sa.Table(
    "log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement='auto'),
    Column("author", BigInteger, nullable=False),
    Column("cc", Integer, nullable=True),
    Column("credits", Integer, nullable=True),
    Column("created_ts", TIMESTAMP(timezone=timezone.utc), nullable=False),
    Column("character_id", Integer, nullable=True),  # ref: > characters.id
    Column("activity", Integer, nullable=False),  # ref: > c_activity.id
    Column("notes", String, nullable=True),
    Column("adventure_id", Integer, nullable=True),  # ref: > adventures.id
    Column("renown", Integer, nullable=True),
    Column("faction", Integer, nullable=True),
    Column("invalid", BOOLEAN, nullable=False, default=False),
    Column("player_id", BigInteger, nullable=False),
    Column("guild_id", BigInteger, nullable=False)
)

class LogSchema(Schema):
    compendium: Compendium
    id = fields.Integer(required=True)
    author = fields.Integer(required=True)
    cc = fields.Integer(required=True)
    credits = fields.Integer(required=True)
    created_ts = fields.Method(None, "load_timestamp")
    character_id = fields.Integer(required=False, allow_none=True)
    activity = fields.Method(None, "load_activity")
    notes = fields.String(required=False, allow_none=True)
    adventure_id = fields.Integer(required=False, allow_none=True)
    renown = fields.Integer(required=True)
    faction = fields.Method(None, "load_faction", allow_none=True)
    invalid = fields.Boolean(required=True)
    player_id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_log(self, data, **kwargs):
        return DBLog(**data)
    
    def load_faction(self, value):
        return self.compendium.get_object(Faction, value)

    def load_activity(self, value):
        return self.compendium.get_object(Activity, value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    

def get_log_by_id(log_id: int) -> FromClause:
    return log_table.select().where(log_table.c.id == log_id)

def get_last_log_by_type(player_id: int, guild_id: int, activity_id: int) -> FromClause:
    return log_table.select().where(
        and_(log_table.c.player_id == player_id,
             log_table.c.guild_id == guild_id,
             log_table.c.activity == activity_id,
             log_table.c.invalid == False)
    ).order_by(log_table.c.id.desc()).limit(1)

def get_log_count_by_player_and_activity(player_id: int, guild_id: int,  activity_id: int) -> FromClause:
    return select([func.count()]).select_from(log_table).where(
        and_(log_table.c.player_id == player_id,
             log_table.c.guild_id == guild_id, 
             log_table.c.activity == activity_id, log_table.c.invalid == False)
    )

def upsert_log(log: DBLog):
    if hasattr(log, "id") and log.id is not None:
        update_dict = {
            "activity": log.activity.id,
            "notes": log.notes if hasattr(log, "notes") else None,
            "credits": log.credits,
            "cc": log.cc,
            "renown": log.renown,
            "invalid": log.invalid
        }

        update_statement = log_table.update().where(log_table.c.id == log.id).values(**update_dict)
        return update_statement


    insert_statement = insert(log_table).values(
        author=log.author,
        player_id=log.player_id,
        cc=log.cc,
        credits=log.credits,
        created_ts=datetime.now(timezone.utc),
        character_id=log.character_id,
        guild_id=log.guild_id,
        activity=log.activity.id,
        notes=log.notes if hasattr(log, "notes") else None,
        adventure_id=None if not hasattr(log, "adventure_id") else log.adventure_id,
        renown=log.renown,
        faction=None if not hasattr(log, "faction") or not log.faction else log.faction.id,
        invalid=log.invalid
    ).returning(log_table)

    return insert_statement

def get_n_player_logs_query(player_id: int, guild_id: int, n : int) -> FromClause:
    return log_table.select().where(and_(log_table.c.player_id == player_id, log_table.c.guild_id == guild_id)).order_by(log_table.c.id.desc()).limit(n)

def player_stats_query(compendium: Compendium, player_id: int, guild_id: int):
    new_character_activity = compendium.get_activity("NEW_CHARACTER")
    activities = [x.id for x in compendium.activity[0].values() if x.value in ["RP", "ARENA", "ARENA_HOST", "GLOBAL", "SNAPSHOT"]]
    activity_columns = [func.sum(case([(log_table.c.activity == act, 1)], else_=0)).label(f"Activity {act}") for act in activities]

    query = select(log_table.c.player_id,
                   func.count(log_table.c.id).label("#"),
                   func.sum(case([(and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("debt"),
                   func.sum(case([(and_(log_table.c.cc < 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("credit"),
                   func.sum(case([(and_(log_table.c.cc > 0, log_table.c.activity == new_character_activity.id), log_table.c.cc)], else_=0)).label("starting"),
                   *activity_columns)\
                    .group_by(log_table.c.player_id)\
                        .where(and_(log_table.c.player_id == player_id,
                                    log_table.c.guild_id == guild_id,
                                     log_table.c.invalid == False))
    
    return query

def character_stats_query(compendium: Compendium, character_id: int):
    new_character_activity = compendium.get_activity("NEW_CHARACTER")
    conversion_activity = compendium.get_activity("CONVERSION")

    query = select(log_table.c.character_id,
                   func.count(log_table.c.id).label("#"),
                   func.sum(case([(and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("cc debt"),
                   func.sum(case([(and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("cc credit"),
                   func.sum(case([(and_(log_table.c.cc > 0, log_table.c.activity == new_character_activity.id), log_table.c.cc)], else_=0)).label("cc starting"),
                   func.sum(case([(and_(log_table.c.credits > 0, log_table.c.activity != new_character_activity.id), log_table.c.credits)], else_=0)).label("credit debt"),
                   func.sum(case([(and_(log_table.c.cc < 0, log_table.c.activity != new_character_activity.id), log_table.c.credits)], else_=0)).label("credit credit"),
                   func.sum(case([(and_(log_table.c.credits > 0, log_table.c.activity == new_character_activity.id), log_table.c.credits)], else_=0)).label("credit starting"),
                   func.sum(case([(log_table.c.activity == conversion_activity.id, log_table.c.credits)], else_=0)).label("credits converted"))\
                    .group_by(log_table.c.character_id)\
                    .where(and_(log_table.c.character_id == character_id, log_table.c.invalid == False))
    return query


