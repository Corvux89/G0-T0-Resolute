import datetime
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import Column, Numeric, Integer, TIMESTAMP, null
from sqlalchemy.sql.selectable import TableClause

from Resolute.models import metadata


class Financial(object):
    def __init__(self, **kwargs):
        self.month_count = kwargs.get('month_count', 0)
        self.monthly_goal = kwargs.get('monthly_goal', 0)
        self.monthly_total = kwargs.get('monthly_total', 0)
        self.reserve = kwargs.get('reserve', 0)
        self.last_reset: datetime.datetime = kwargs.get('last_reset')

    @property
    def adjusted_total(self):
        # Adjusted for what Discord takes
        return self.monthly_total*.9

financial_table = sa.Table(
    "financial",
    metadata,
    Column("month_count", Integer, nullable=False),
    Column("monthly_goal", Numeric, nullable=False),
    Column("monthly_total", Numeric, nullable=False),
    Column("reserve", Numeric, nullable=False),
    Column("last_reset", TIMESTAMP(timezone=datetime.timezone.utc), nullable=True, default=null())
)

class FinancialSchema(Schema):
    month_count = fields.Integer(required=True)
    monthly_goal = fields.Number(required=True)
    monthly_total = fields.Number(required=True)
    reserve = fields.Number(required=True)
    last_reset = fields.Method(None, "load_timestamp", allow_none=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime.datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=datetime.timezone.utc)
    
    @post_load
    def make_finance(self, data, **kwargs):
        return Financial(**data)
    
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