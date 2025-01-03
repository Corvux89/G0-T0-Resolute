import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy import BigInteger, Column, Numeric
from sqlalchemy.sql.selectable import TableClause

from Resolute.models import metadata


class Store(object):
    def __init__(self, **kwargs):
        self.sku = kwargs.get('sku')
        self.user_cost: int = kwargs.get('user_cost', 0)

store_table = sa.Table(
    "store",
    metadata,
    Column("sku", BigInteger, primary_key=True, nullable=False),
    Column("user_cost", Numeric, nullable=False)
)

class StoreSchema(Schema):
    sku = fields.Integer(required=True)
    user_cost = fields.Number(required=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    @post_load
    def make_store(self, data, **kwargs):
        return Store(**data)
    
def get_store_items_query() -> TableClause:
    return store_table.select()