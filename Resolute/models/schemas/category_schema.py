from marshmallow import Schema, fields, post_load

from Resolute.models.db_objects.category_objects import *

class RaritySchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_rarity(self, data, **kwargs):
        return Rarity(**data)


class CharacterClassSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_class(self, data, **kwargs):
        return CharacterClass(**data)


class CharacterArchetypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    parent = fields.Integer(data_key="parent", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_subclass(self, data, **kwargs):
        return CharacterArchetype(**data)


class CharacterSpeciesSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_character_race(self, data, **kwargs):
        return CharacterSpecies(**data)

class GlobalModifierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    adjustment = fields.Float(data_key="adjustment", required=True)
    max = fields.Integer(data_key="max", required=True)

    @post_load
    def make_c_global_modifier(self, data, **kwargs):
        return GlobalModifier(**data)


class HostStatusSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_host_status(self, data, **kwargs):
        return HostStatus(**data)


class ArenaTierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    avg_level = fields.Integer(data_key="avg_level", required=True)
    max_phases = fields.Integer(data_key="max_phases", required=True)

    @post_load
    def make_c_arena_tier(self, data, **kwargs):
        return ArenaTier(**data)


class AdventureTierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    avg_level = fields.Integer(data_key="avg_level", required=True)

    @post_load
    def make_c_adventure_tier(self, data, **kwargs):
        return AdventureTier(**data)


class ActivitySchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    cc = fields.Integer(data_key="cc", required=False, allow_none=True)
    diversion = fields.Boolean(data_key="diversion", required=True)

    @post_load
    def make_c_activity(self, data, **kwargs):
        return Activity(**data)


class DashboardTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_c_dashboard_type(self, data, **kwargs):
        return DashboardType(**data)


class LevelCapsSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    max_cc = fields.Integer(data_key="max_cc", required=True)
    max_items = fields.String(data_key="max_items", required=True)
    max_consumable = fields.String(data_key="max_consumable", required=True)

    @post_load
    def make_level_caps(self, data, **kwargs):
        return LevelCaps(**data)


class AdventureRewardsSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    ep = fields.Integer(data_key="ep", required=True)
    tier = fields.Integer(data_key="tier", required=True)
    rarity = fields.Integer(data_key="rarity", required=False, allow_none=True)

    @post_load
    def make_adventure_reward(self, data, **kwargs):
        return AdventureRewards(**data)

class CodeConversionSchema(Schema):
    id = fields.Integer(data_key="id", require=True)
    value = fields.Integer(data_key="value", required=True)

    @post_load
    def make_code_conversion(self, data, **kwargs):
        return CodeConversion(**data)
