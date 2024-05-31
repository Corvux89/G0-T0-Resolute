import sqlalchemy as sa
import discord

from discord import ApplicationContext
from marshmallow import Schema, fields, post_load
from datetime import timezone, datetime
from sqlalchemy import Column, Integer, BigInteger, String, BOOLEAN, null, func, TIMESTAMP, and_, select
from Resolute.models.categories import Activity
from Resolute.compendium import Compendium
from Resolute.models import metadata
from discord import ApplicationContext
from sqlalchemy.sql import FromClause
from sqlalchemy.dialects.postgresql import insert

from Resolute.models.objects.characters import PlayerCharacter


class DBLog(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.author = kwargs.get('author')
        self.player_id = kwargs.get('player_id')
        self.cc = kwargs.get('cc', 0)
        self.credits = kwargs.get('credits', 0)
        self.character_id = kwargs.get('character_id')
        self.activity: Activity = kwargs.get('activity')
        self.notes = kwargs.get('notes')
        self.adventure_id = kwargs.get('adventure_id')
        self.invalid = kwargs.get('invalid', False)
        self.created_ts = kwargs.get('created_ts', datetime.now(timezone.utc))

    def get_author(self, ctx: ApplicationContext) -> discord.Member | None:
        return discord.utils.get(ctx.guild.members, id=self.author)
    
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
    Column("invalid", BOOLEAN, nullable=False, default=False),
    Column("player_id", BigInteger, nullable=False)
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
    invalid = fields.Boolean(required=True)
    player_id = fields.Integer(required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_log(self, data, **kwargs):
        return DBLog(**data)

    def load_activity(self, value):
        return self.compendium.get_object(Activity, value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    

def get_log_by_id(log_id: int) -> FromClause:
    return log_table.select().where(log_table.c.id == log_id)

def get_log_count_by_player_and_activity(player_id: int, activity_id: int) -> FromClause:
    return select([func.count()]).select_from(log_table).where(
        and_(log_table.c.player_id == player_id, log_table.c.activity == activity_id, log_table.c.invalid == False)
    )

def upsert_log(log: DBLog):
    if hasattr(log, "id") and log.id is not None:
        update_dict = {
            "activity": log.activity.id,
            "notes": log.notes if hasattr(log, "notes") else None,
            "credits": log.credits,
            "cc": log.cc,
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
        activity=log.activity.id,
        notes=log.notes if hasattr(log, "notes") else None,
        adventure_id=None if not hasattr(log, "adventure_id") else log.adventure_id,
        invalid=log.invalid
    ).returning(log_table)

    return insert_statement