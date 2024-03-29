from marshmallow import Schema, fields, post_load

from Resolute.models.db_objects.ref_objects import *


class RefCategoryDashboardSchema(Schema):
    category_channel_id = fields.Integer(data_key="category_channel_id", required=True)
    dashboard_post_channel_id = fields.Integer(data_key="dashboard_post_channel_id", required=True)
    dashboard_post_id = fields.Integer(data_key="dashboard_post_id", required=True)
    excluded_channel_ids = fields.List(fields.Integer, data_key="excluded_channel_ids")
    dashboard_type = fields.Integer(data_key="dashboard_type", required=True)

    @post_load
    def make_dashboard(self, data, **kwargs):
        return RefCategoryDashboard(**data)


class RefWeeklyStipendSchema(Schema):
    role_id = fields.Integer(data_key="role_id", required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    amount = fields.Integer(data_key="amount", required=True)
    reason = fields.String(data_key="reason", required=False, allow_none=True)
    leadership = fields.Boolean(data_key="leadership", required=True)

    @post_load
    def make_stipend(self, data, **kwargs):
        return RefWeeklyStipend(**data)


class GlobalEventSchema(Schema):
    guild_id = fields.Integer(data_key='guild_id', required=True)
    name = fields.String(data_key='name', required=True)
    base_cc = fields.Integer(data_key='base_cc', required=True)
    channels = fields.List(fields.Integer, data_key='channels', load_default=[], required=False)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_globEvent(self, data, **kwargs):
        return GlobalEvent(**data)



class GlobalPlayerSchema(Schema):
    id = fields.Integer(data_key='id', required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    player_id = fields.Integer(data_key='player_id', required=True)
    cc = fields.Integer(data_key='cc', required=True)
    update = fields.Boolean(data_key='update', required=True)
    active = fields.Boolean(data_key='active', required=True)
    num_messages = fields.Integer(data_key="num_messages", required=True)
    channels = fields.List(fields.Integer, data_key="channels", load_default=[], required=False)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_globEvent(self, data, **kwargs):
        return GlobalPlayer(**data)

    def get_host_status(self, value):
        return self.compendium.get_object("c_host_status", value)