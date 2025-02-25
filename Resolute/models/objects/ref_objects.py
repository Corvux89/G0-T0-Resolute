import aiopg.sa
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import FromClause, TableClause

from Resolute.models import metadata


class RefWeeklyStipend(object):
    """
    A class to represent a weekly stipend for a specific role in a guild.
    Attributes:
    -----------
    db : aiopg.sa.Engine
        The database engine for executing queries.
    guild_id : int
        The ID of the guild.
    role_id : int
        The ID of the role.
    amount : int, optional
        The amount of the stipend (default is 1).
    reason : str, optional
        The reason for the stipend (default is None).
    leadership : bool, optional
        Indicates if the stipend is for a leadership role (default is False).
    Methods:
    --------
    upsert():
        Inserts or updates the weekly stipend in the database.
    delete():
        Deletes the weekly stipend from the database.
    """

    ref_weekly_stipend_table = sa.Table(
        "ref_weekly_stipend",
        metadata,
        sa.Column("role_id", sa.BigInteger, primary_key=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger, nullable=False),  # ref: > guilds.id
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("reason", sa.String, nullable=True),
        sa.Column("leadership", sa.BOOLEAN, nullable=False, default=False),
    )

    class RefWeeklyStipendSchema(Schema):
        db: aiopg.sa.Engine

        role_id = fields.Integer(required=True)
        guild_id = fields.Integer(required=True)
        amount = fields.Integer(required=True)
        reason = fields.String(required=False, allow_none=True)
        leadership = fields.Boolean(required=True)

        def __init__(self, db: aiopg.sa.Engine, **kwargs):
            super().__init__(**kwargs)
            self.db = db

        @post_load
        def make_stipend(self, data, **kwargs):
            stipend = RefWeeklyStipend(self.db, **data)
            return stipend

    def __init__(
        self,
        db: aiopg.sa.Engine,
        guild_id: int,
        role_id: int,
        amount: int = 1,
        reason: str = None,
        leadership: bool = False,
    ):
        self._db = db
        self.guild_id = guild_id
        self.role_id = role_id
        self.amount = amount
        self.reason = reason
        self.leadership = leadership

    async def upsert(self) -> None:
        update_dict = {
            "role_id": self.role_id,
            "guild_id": self.guild_id,
            "amount": self.amount,
            "reason": self.reason,
            "leadership": self.leadership,
        }

        query = RefWeeklyStipend.ref_weekly_stipend_table.insert().values(
            role_id=self.role_id,
            guild_id=self.guild_id,
            amount=self.amount,
            reason=self.reason,
            leadership=self.leadership,
        )

        query = query.on_conflict_do_update(
            index_elements=["role_id"], set_=update_dict
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)

    async def delete(self) -> None:
        query = RefWeeklyStipend.ref_weekly_stipend_table.delete().where(
            RefWeeklyStipend.c.role_id == self.role_id
        )

        async with self._db.acquire() as conn:
            await conn.execute(query)


class RefServerCalendar(object):
    day_start: int
    day_end: int
    display_name: str
    guild_id: int

    ref_server_calendar_table = sa.Table(
        "ref_server_calendar",
        metadata,
        sa.Column("day_start", sa.Integer, primary_key=True, nullable=False),
        sa.Column("day_end", sa.Integer, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("guild_id", sa.BigInteger, nullable=False),
    )

    class RefServerCalendarSchema(Schema):
        day_start = fields.Integer(required=True)
        day_end = fields.Integer(required=True)
        display_name = fields.String(required=True)
        guild_id = fields.Integer(required=True)

        @post_load
        def make_stipend(self, data, **kwargs):
            return RefServerCalendar(**data)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
