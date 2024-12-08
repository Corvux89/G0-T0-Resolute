import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import BigInteger, Column, Numeric, Integer
from sqlalchemy.sql.selectable import TableClause

from Resolute.models import metadata


class Financial(object):
    def __init__(self, **kwargs):
        self.month_count = kwargs.get('month_count', 0)
        self.monthly_goal = kwargs.get('monthly_goal', 0)
        self.monthly_total = kwargs.get('monthly_total', 0)
        self.reserve = kwargs.get('reserve', 0)

financial_table = sa.Table(
    "financial",
    metadata,
    Column("month_count", Integer, nullable=False),
    Column("monthly_goal", Numeric, nullable=False),
    Column("monthly_total", Numeric, nullable=False),
    Column("reserve", Numeric, nullable=False)
)

class FinancialSchema(Schema):
    month_count = fields.Integer(required=True)
    monthly_goal = fields.Number(required=True)
    monthly_total = fields.Number(required=True)
    reserve = fields.Number(required=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    @post_load
    def make_finance(self, data, **kwargs):
        return Financial(**data)
    
def get_financial_query() -> TableClause:
    return financial_table.select()

def update_financial_query(fin: Financial):
    update_dict = {
        "month_count": fin.month_count,
        "monthly_total": fin.monthly_total,
        "reserve": fin.reserve
    }

    return financial_table.update().values(**update_dict)