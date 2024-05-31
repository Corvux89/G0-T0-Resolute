import sqlalchemy as sa

from Resolute.models import metadata
from sqlalchemy import Column, BigInteger, Integer, String, BOOLEAN
from marshmallow import Schema, fields, post_load
from sqlalchemy.sql import FromClause, TableClause, text
from sqlalchemy.dialects.postgresql import insert

class RefWeeklyStipend(object):
    def __init__(self, guild_id: int, role_id: int, amount: int = 1, reason: str = None, leadership: bool = False):
        self.guild_id = guild_id
        self.role_id = role_id
        self.amount = amount
        self.reason = reason
        self.leadership = leadership


ref_weekly_stipend_table = sa.Table(
    "ref_weekly_stipend",
    metadata,
    Column("role_id", BigInteger, primary_key=True, nullable=False),
    Column("guild_id", BigInteger, nullable=False),  # ref: > guilds.id
    Column("amount", Integer, nullable=False),
    Column("reason", String, nullable=True),
    Column("leadership", BOOLEAN, nullable=False, default=False)
)

class RefWeeklyStipendSchema(Schema):
    role_id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    amount = fields.Integer(required=True)
    reason = fields.String(required=False, allow_none=True)
    leadership = fields.Boolean(required=True)

    @post_load
    def make_stipend(self, data, **kwargs):
        return RefWeeklyStipend(**data)
    
def get_weekly_stipend_query(role_id: int) -> FromClause:
    return ref_weekly_stipend_table.select().where(
        ref_weekly_stipend_table.c.role_id == role_id
    )

def get_guild_weekly_stipends_query(guild_id: int) -> FromClause:
    return ref_weekly_stipend_table.select() \
        .where(ref_weekly_stipend_table.c.guild_id == guild_id) \
        .order_by(ref_weekly_stipend_table.c.amount.desc())

def delete_weekly_stipend_query(stipend: RefWeeklyStipend) -> TableClause:
    return ref_weekly_stipend_table.delete().where(ref_weekly_stipend_table.c.role_id == stipend.role_id)

def upsert_weekly_stipend(stipend: RefWeeklyStipend):
    insert_statement = insert(ref_weekly_stipend_table).values(
        role_id=stipend.role_id,
        guild_id=stipend.guild_id,
        amount=stipend.amount,
        reason=stipend.reason,
        leadership=stipend.leadership
    )

    update_dict = {
        'role_id': stipend.role_id,
        'guild_id': stipend.guild_id,
        'amount': stipend.amount,
        'reason': stipend.reason,
        'leadership': stipend.leadership
    }

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['role_id'],
        set_=update_dict
    )

    return upsert_statement

class RefServerCalendar(object):
    day_start: int
    day_end: int
    display_name: str
    guild_id: int

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

ref_server_calendar_table = sa.Table(
    "ref_server_calendar",
    metadata,
    Column("day_start", Integer, primary_key=True, nullable=False),
    Column("day_end", Integer, nullable=False),
    Column("display_name", String, nullable=False),
    Column("guild_id", BigInteger, nullable=False)    
)

class RefServerCalendarSchema(Schema):
    day_start = fields.Integer(required=True)
    day_end = fields.Integer(required=True)
    display_name = fields.String(required=True)
    guild_id = fields.Integer(required=True)
    

    @post_load
    def make_stipend(self, data, **kwargs):
        return RefServerCalendar(**data)


def get_server_calendar(guild_id: int) -> FromClause:
    return ref_server_calendar_table.select()\
           .where(ref_server_calendar_table.c.guild_id == guild_id)\
           .order_by(ref_server_calendar_table.c.day_start.asc())

ref_applications_table = sa.Table(
    "ref_character_applications",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("application", String, nullable=False)
)

class ApplicationSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    application = fields.String(data_key="application", required=True)


def get_player_application(char_id: int) -> FromClause:
    return ref_applications_table.select().where(
        ref_applications_table.c.id == char_id
    )

def upsert_player_application(char_id: int, application: str) -> TableClause:
    query = text("""
            WITH delete AS(
                 DELETE FROM ref_applications WHERE id = :char_id                    
            )
            INSERT INTO ref_applications (id, application) VALUES (:char_id, :application)     
                 """).bindparams(char_id=char_id, application=application)
    return query