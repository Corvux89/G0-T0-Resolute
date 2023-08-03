from discord import ApplicationContext
from marshmallow import Schema, fields, post_load
from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, PlayerGuild, DBLog, Adventure, Arena, \
    CharacterStarship


class PlayerCharacterClassSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    character_id = fields.Integer(data_key="character_id", required=True)
    primary_class = fields.Method(None, "load_primary_class")
    archetype = fields.Method(None, "load_archetype", allow_none=True)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_class(self, data, **kwargs):
        return PlayerCharacterClass(**data)

    def load_primary_class(self, value):
        return self.compendium.get_object("c_character_class", value)

    def load_archetype(self, value):
        return self.compendium.get_object("c_character_archetype", value)


class CharacterSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    name = fields.String(data_key="name", required=True)
    species = fields.Method(None, "load_species")
    cc = fields.Integer(data_key="cc", required=True)
    div_cc = fields.Integer(data_key="div_cc", required=True)
    credits = fields.Integer(data_key="credits", required=True)
    level = fields.Integer(data_key="level", required=True)
    token = fields.Integer(data_key="token", required=True)
    player_id = fields.Integer(data_key="player_id", required=True)
    guild_id = fields.Integer(data_key="guild_id", required=True)
    reroll = fields.Boolean(data_key="reroll", required=False, default=False)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_character(self, data, **kwargs):
        return PlayerCharacter(**data)

    def load_species(self, value):
        return self.compendium.get_object("c_character_species", value)


class GuildSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    max_level = fields.Integer(data_key="max_level", required=True)
    weeks = fields.Integer(data_key="weeks", required=True)
    max_reroll = fields.Integer(data_key="max_reroll", required=True)
    reset_day = fields.Integer(data_key="reset_day", required=False, allow_none=True)
    reset_hour = fields.Integer(data_key="reset_hour", required=False, allow_none=True)
    last_reset = fields.Method(None, "load_timestamp")
    greeting = fields.String(data_key="greeting", required=False, allow_none=True)

    @post_load
    def make_guild(self, data, **kwargs):
        return PlayerGuild(**data)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class LogSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    author = fields.Integer(data_key="author", required=True)
    cc = fields.Integer(data_key="cc", required=True)
    credits = fields.Integer(data_key="credits", required=True)
    token = fields.Integer(data_key="token", required=True)
    created_ts = fields.Method(None, "load_timestamp")
    character_id = fields.Integer(data_key="character_id", required=True)
    activity = fields.Method(None, "load_activity")
    notes = fields.String(data_key="notes", required=False, allow_none=True)
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
    category_channel_id = fields.Integer(data_key="category_channel_id", required=True)
    cc = fields.Integer(data_key="cc", required=True)
    created_ts = fields.Method(None, "load_timestamp")
    end_ts = fields.Method(None, "load_timestamp", allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_adventure(self, data, **kwargs):
        return Adventure(**data)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value


class ArenaSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    channel_id = fields.Integer(data_key="channel_id", required=True)
    pin_message_id = fields.Integer(data_key="pin_message_id", required=True)
    role_id = fields.Integer(data_key="role_id", required=True)
    host_id = fields.Integer(data_key="host_id", required=True)
    tier = fields.Method(None, "load_tier")
    type = fields.Method(None, "load_type")
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

    def load_type(self, value):
        return self.compendium.get_object("c_arena_type", value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return value

class CharacterStarshipSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    character_id = fields.List(fields.Integer, data_key="character_id", required=True)
    name = fields.String(data_key="name", required=True)
    transponder = fields.String(data_key="transponder", allow_none=True, required=False)
    starship = fields.Method(None, "load_starship")
    tier = fields.Integer(data_key="tier", required=False, default=None, allow_none=True)
    active = fields.Boolean(data_key="active", required=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_character_starship(self, data, **kwargs):
        return CharacterStarship(**data)

    def load_starship(self, value):
        return self.compendium.get_object("c_starship_role", value)
