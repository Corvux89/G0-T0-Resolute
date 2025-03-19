from __future__ import annotations
from typing import TYPE_CHECKING

import datetime

import aiopg.sa
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load

from Resolute.models import metadata

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class Financial(object):
    """
    A class to represent financial information and operations.
    Attributes:
    -----------
    _db : aiopg.sa.Engine
        The database engine used for database operations.
    month_count : int
        The number of months counted.
    monthly_goal : float
        The financial goal for the month.
    monthly_total : float
        The total amount for the month.
    reserve : float
        The reserve amount.
    last_reset : datetime.datetime
        The last reset date and time.
    Methods:
    --------
    adjusted_total:
        Returns the monthly total adjusted for Discord's fee.
    update:
        Asynchronously updates the financial information in the database.
    """

    financial_table = sa.Table(
        "financial",
        metadata,
        sa.Column("month_count", sa.Integer, nullable=False),
        sa.Column("monthly_goal", sa.Numeric, nullable=False),
        sa.Column("monthly_total", sa.Numeric, nullable=False),
        sa.Column("reserve", sa.Numeric, nullable=False),
        sa.Column(
            "last_reset",
            sa.TIMESTAMP(timezone=datetime.timezone.utc),
            nullable=True,
            default=sa.null(),
        ),
    )

    class FinancialSchema(Schema):
        db: aiopg.sa.Engine = None
        month_count = fields.Integer(required=True)
        monthly_goal = fields.Number(required=True)
        monthly_total = fields.Number(required=True)
        reserve = fields.Number(required=True)
        last_reset = fields.Method(None, "load_timestamp", allow_none=True)

        def __init__(self, db: aiopg.sa.Engine, **kwargs):
            self.db = db
            super().__init__(**kwargs)

        def load_timestamp(
            self, value: datetime.datetime
        ):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
            return datetime.datetime(
                value.year,
                value.month,
                value.day,
                value.hour,
                value.minute,
                value.second,
                tzinfo=datetime.timezone.utc,
            )

        @post_load
        def make_finance(self, data, **kwargs) -> "Financial":
            return Financial(self.db, **data)

    def __init__(self, db, **kwargs):
        self._db: aiopg.sa.Engine = db
        self.month_count = kwargs.get("month_count", 0)
        self.monthly_goal = kwargs.get("monthly_goal", 0)
        self.monthly_total = kwargs.get("monthly_total", 0)
        self.reserve = kwargs.get("reserve", 0)
        self.last_reset: datetime.datetime = kwargs.get("last_reset")

    @property
    def adjusted_total(self) -> float:
        # Adjusted for what Discord takes
        return self.monthly_total * 0.9

    async def update(self) -> None:
        update_dict = {
            "month_count": self.month_count,
            "monthly_total": self.monthly_total,
            "reserve": self.reserve,
            "last_reset": self.last_reset,
        }

        query = Financial.financial_table.update().values(**update_dict)

        async with self._db.acquire() as conn:
            await conn.execute(query)

    @staticmethod
    async def get_financial_data(bot: G0T0Bot) -> "Financial":
        row = await bot.query(Financial.financial_table.select())

        if row is None:
            return None

        fin = Financial.FinancialSchema(bot.db).load(row)

        return fin
