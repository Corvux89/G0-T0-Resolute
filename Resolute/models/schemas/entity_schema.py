from discord import ApplicationContext
from marshmallow import Schema, fields, post_load
from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, PlayerGuild, DBLog, Adventure, Arena, \
    Shop


class PlayerCharacterClassSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    character_id = fields.Integer(data_key="character_id", required=True)
    primary_class = fields.Method(None, "load_primary_class")
    subclass = fields.Method(None, "load_subclass", allow_none=True)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_class(self, data, **kwargs):
        return PlayerCharacterClass(**data)

    def load_primary_class(self, value):
        return self.compendium.get_object("c_character_class", value)

    def load_subclass(self, value):
        return self.compendium.get_object("c_character_subclass", value)


class CharacterSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    name = fields.String(data_key="name", required=True)
    race = fields.Method(None, "load_race")
    subrace = fields.Method(None, "load_subrace", allow_none=True)
    xp = fields.Integer(data_key="xp", required=True)
    div_xp = fields.Integer(data_key="div_xp", required=True)
    gold = fields.Integer(data_key="gold", required=True)
    div_gold = fields.Integer(data_key="div_gold", required=True)
    player_id = fields.Integer(data_key="player_id", required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    faction = fields.Method(None, "load_factions", allow_none=True)
    reroll = fields.Boolean(data_key="reroll", required=False, default=False)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_character(self, data, **kwargs):
        return PlayerCharacter(**data)

    def load_race(self, value):
        return self.compendium.get_object("c_character_race", value)

    def load_subrace(self, value):
        return self.compendium.get_object("c_character_subrace", value)

    def load_factions(self, value):
        return self.compendium.get_object("c_faction", value)


class GuildSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    max_level = fields.Integer(data_key="max_level", required=True)
    server_xp = fields.Integer(data_key="server_xp", required=True)
    weeks = fields.Integer(data_key="weeks", required=True)
    week_xp = fields.Integer(data_key="week_xp", required=True)
    max_reroll = fields.Integer(data_key="max_reroll", required=True)
    xp_adjust = fields.Integer(data_key="xp_adjust", required=True)
    reset_day = fields.Integer(data_key="reset_day", required=False, allow_none=True)
    reset_hour = fields.Integer(data_key="reset_hour", required=False, allow_none=True)
    last_reset = fields.Method(None, "load_timestamp")

    @post_load
    def make_guild(self, data, **kwargs):
        return PlayerGuild(**data)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class LogSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    author = fields.Integer(data_key="author", required=True)
    xp = fields.Integer(data_key="xp", required=True)
    server_xp = fields.Integer(data_key="server_xp", required=True)
    gold = fields.Integer(data_key="gold", required=True)
    created_ts = fields.Method(None, "load_timestamp")
    character_id = fields.Integer(data_key="character_id", required=True)
    activity = fields.Method(None, "load_activity")
    notes = fields.String(data_key="notes", required=False, allow_none=True)
    shop_id = fields.Integer(data_key="shop_id", required=False, allow_none=True)
    adventure_id = fields.Integer(data_key="adventure_id", required=False, allow_none=True)
    invalid = fields.Boolean(data_key="invalid", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_log(self, data, **kwargs):
        return DBLog(**data)

    def load_activity(self, value):
        return self.compendium.get_object("c_activity", value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class AdventureSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    name = fields.String(data_key="name", required=True)
    role_id = fields.Integer(data_key="role_id", required=True)
    dms = fields.List(fields.Integer, data_key="dms", required=True)
    tier = fields.Method(None, "load_tier")
    category_channel_id = fields.Integer(data_key="category_channel_id", required=True)
    ep = fields.Integer(data_key="ep", required=True)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_adventure(self, data, **kwargs):
        return Adventure(**data)

    def load_tier(self, value):
        return self.compendium.get_object("c_adventure_tier", value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class ArenaSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    pin_message_id = fields.Integer(data_key="pin_message_id", required=True)
    role_id = fields.Integer(data_key="role_id", required=True)
    host_id = fields.Integer(data_key="host_id", required=True)
    tier = fields.Method(None, "load_tier")
    completed_phases = fields.Integer(data_key="completed_phases", required=True, default=0)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_arena(self, data, **kwargs):
        return Arena(**data)

    def load_tier(self, value):
        return self.compendium.get_object("c_arena_tier", value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class ShopSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    name = fields.String(data_key="name", required=True)
    type = fields.Method(None, "load_type")
    owner_id = fields.Integer(data_key="owner_id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    shelf = fields.Integer(data_key="shelf", required=True)
    network = fields.Integer(data_key="network", required=True)
    mastery = fields.Integer(data_key="mastery", required=True)
    seeks_remaining = fields.Integer(data_key="seeks_remaining", required=True)
    max_cost = fields.Integer(data_key="max_cost", required=False, default=None, allow_none=True)
    seek_roll = fields.String(data_key="seek_roll", reqquired=False, default=None, allow_none=True)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_shop(self, data, **kwargs):
        return Shop(**data)

    def load_type(self, value):
        return self.compendium.get_object("c_shop_type", value)
