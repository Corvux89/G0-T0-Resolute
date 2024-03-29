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

class ArenaTierSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    avg_level = fields.Integer(data_key="avg_level", required=True)
    max_phases = fields.Integer(data_key="max_phases", required=True)

    @post_load
    def make_c_arena_tier(self, data, **kwargs):
        return ArenaTier(**data)


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

    @post_load
    def make_level_caps(self, data, **kwargs):
        return LevelCaps(**data)

class CodeConversionSchema(Schema):
    id = fields.Integer(data_key="id", require=True)
    value = fields.Integer(data_key="value", required=True)

    @post_load
    def make_code_conversion(self, data, **kwargs):
        return CodeConversion(**data)

class StarshipRoleSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)
    size = fields.Integer(data_key="size", required=True)

    @post_load
    def make_starship_role(self, data, **kwargs):
        return StarshipRole(**data)

class StarshipSizeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_starship_size(self, data, **kwargs):
        return StarshipSize(**data)

class ArenaTypeSchema(Schema):
    id = fields.Integer(data_key="id", required=True)
    value = fields.String(data_key="value", required=True)

    @post_load
    def make_arena_type(self, data, **kwargs):
        return ArenaType(**data)