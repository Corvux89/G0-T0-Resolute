import sqlalchemy as sa

from sqlalchemy import Column, BigInteger, Integer, String, BOOLEAN, and_, null
from marshmallow import Schema, fields, post_load
from sqlalchemy.sql import FromClause, TableClause
from sqlalchemy.dialects.postgresql import ARRAY, insert

from Resolute.compendium import Compendium
from Resolute.models import metadata

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


class NPC(object):
    def __init__(self, guild_id: int, key: str, name: str, **kwargs):
        self.guild_id: int = guild_id
        self.key: str = key
        self.name: str = name
        self.avatar_url: str = kwargs.get('avatar_url')
        self.roles: list[int] = kwargs.get('roles', [])
        self.adventure_id: int = kwargs.get('adventure_id')


npc_table = sa.Table(
    "ref_npc",
    metadata,
    Column("guild_id", Integer, nullable=False),
    Column("key", String, nullable=False),
    Column("name", String, nullable=False),
    Column("avatar_url", String, nullable=True),
    Column("roles", ARRAY(BigInteger), nullable=False),
    Column("adventure_id", Integer, nullable=True),
    sa.PrimaryKeyConstraint("guild_id", "key")
)


class NPCSchema(Schema):
    compendium: Compendium
    guild_id=fields.Integer(required=True)
    key=fields.String(required=True)
    name=fields.String(required=True)
    avatar_url=fields.String(required=False, allow_none=True)
    roles=fields.List(fields.Integer, required=True)
    adventure_id=fields.Integer(required=False, allow_none=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @post_load
    def make_npc(self, data, **kwargs):
        return NPC(**data)


def upsert_npc_query(npc: NPC):
    insert_dict = {
        "key": npc.key,
        "guild_id": npc.guild_id,
        "name": npc.name,
        "avatar_url": npc.avatar_url,
        "adventure_id": npc.adventure_id,
        "roles": npc.roles
    }

    statement = insert(npc_table).values(insert_dict)

    statement = statement.on_conflict_do_update(
        index_elements=['guild_id', 'key'],
        set_={
            'name': statement.excluded.name,
            'avatar_url': statement.excluded.avatar_url,
            'adventure_id': statement.excluded.adventure_id,
            'roles': statement.excluded.roles
        }
    )

    return statement.returning(npc_table)


def get_npc_query(guild_id: int, key: str) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.key == key)
    )


def get_guild_npcs_query(guild_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.guild_id == guild_id, npc_table.c.adventure_id == null())
    ).order_by(npc_table.c.key.asc())


def get_adventure_npcs_query(adventure_id: int) -> FromClause:
    return npc_table.select().where(
        and_(npc_table.c.adventure_id == adventure_id)
    ).order_by(npc_table.c.key.asc())


def delete_npc_query(npc: NPC) -> TableClause:
    return npc_table.delete().where(
        and_(npc_table.c.guild_id == npc.guild_id, npc_table.c.key == npc.key)
    )