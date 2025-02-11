import datetime

import aiopg.sa
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.sql.selectable import TableClause

from Resolute.models import metadata


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

    def __init__(self, db, **kwargs):
        self._db: aiopg.sa.Engine = db
        self.month_count = kwargs.get('month_count', 0)
        self.monthly_goal = kwargs.get('monthly_goal', 0)
        self.monthly_total = kwargs.get('monthly_total', 0)
        self.reserve = kwargs.get('reserve', 0)
        self.last_reset: datetime.datetime = kwargs.get('last_reset')

    @property
    def adjusted_total(self) -> float:
        # Adjusted for what Discord takes
        return self.monthly_total*.9
    
    async def update(self) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(update_financial_query(self))

financial_table = sa.Table(
    "financial",
    metadata,
    sa.Column("month_count", sa.Integer, nullable=False),
    sa.Column("monthly_goal", sa.Numeric, nullable=False),
    sa.Column("monthly_total", sa.Numeric, nullable=False),
    sa.Column("reserve", sa.Numeric, nullable=False),
    sa.Column("last_reset", sa.TIMESTAMP(timezone=datetime.timezone.utc), nullable=True, default=sa.null())
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

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime.datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=datetime.timezone.utc)
    
    @post_load
    def make_finance(self, data, **kwargs):
        return Financial(self.db, **data)
    
def get_financial_query() -> TableClause:
    return financial_table.select()

def update_financial_query(fin: Financial):
    update_dict = {
        "month_count": fin.month_count,
        "monthly_total": fin.monthly_total,
        "reserve": fin.reserve,
        "last_reset": fin.last_reset
    }

    return financial_table.update().values(**update_dict)