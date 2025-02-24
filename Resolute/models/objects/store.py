import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.sql.selectable import TableClause

from Resolute.models import metadata


class Store(object):
    """
    A class used to represent a Store.
    Attributes
    ----------
    sku : str
        The stock keeping unit identifier for the store item.
    user_cost : int
        The cost to the user for the store item. Defaults to 0.
    Methods
    -------
    __init__(**kwargs)
        Initializes the Store object with the given keyword arguments.
    """

    def __init__(self, **kwargs):
        self.sku = kwargs.get("sku")
        self.user_cost: int = kwargs.get("user_cost", 0)


store_table = sa.Table(
    "store",
    metadata,
    sa.Column("sku", sa.BigInteger, primary_key=True, nullable=False),
    sa.Column("user_cost", sa.Numeric, nullable=False),
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
