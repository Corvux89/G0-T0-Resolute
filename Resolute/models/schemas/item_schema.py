from marshmallow import Schema, fields, post_load

from ProphetBot.models.db_objects.item_objects import ItemBlacksmith, ItemWondrous, ItemConsumable, ItemScroll


class ItemBlacksmithSchema(Schema):
    id = fields.Integer(data_key="id", requied=True)
    name = fields.String(data_key="name", required=True)
    sub_type = fields.Method(None, "load_subtype")
    rarity = fields.Method(None, "load_rarity")
    cost = fields.Integer(data_key="cost", required=True)
    item_modifier = fields.Boolean(data_key="item_modifier", required=True)
    attunement = fields.Boolean(data_key="attunement", required=True)
    seeking_only = fields.Boolean(data_key="seeking_only", required=True)
    source = fields.String(data_key="source", required=False, allow_none=True)
    notes = fields.String(data_key="notes", required=False, allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_item_blacksmith(self, data, **kwargs):
        return ItemBlacksmith(**data)

    def load_subtype(self, value):
        return self.compendium.get_object("c_blacksmith_type", value)

    def load_rarity(self, value):
        return self.compendium.get_object("c_rarity", value)


class ItemWondrousSchema(Schema):
    id = fields.Integer(data_key="id", requied=True)
    name = fields.String(data_key="name", required=True)
    rarity = fields.Method(None, "load_rarity")
    cost = fields.Integer(data_key="cost", required=True)
    attunement = fields.Boolean(data_key="attunement", required=True)
    seeking_only = fields.Boolean(data_key="seeking_only", required=True)
    source = fields.String(data_key="source", required=False, allow_none=True)
    notes = fields.String(data_key="notes", required=False, allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_item_wondrous(self, data, **kwargs):
        return ItemWondrous(**data)

    def load_rarity(self, value):
        return self.compendium.get_object("c_rarity", value)


class ItemConsumableSchema(Schema):
    id = fields.Integer(data_key="id", requied=True)
    name = fields.String(data_key="name", required=True)
    sub_type = fields.Method(None, "load_subtype")
    rarity = fields.Method(None, "load_rarity")
    cost = fields.Integer(data_key="cost", required=True)
    attunement = fields.Boolean(data_key="attunement", required=True)
    seeking_only = fields.Boolean(data_key="seeking_only", required=True)
    source = fields.String(data_key="source", required=False, allow_none=True)
    notes = fields.String(data_key="notes", required=False, allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium


    @post_load
    def make_item_consumable(self, data, **kwargs):
        return ItemConsumable(**data)

    def load_subtype(self, value):
        return self.compendium.get_object("c_consumable_type", value)

    def load_rarity(self, value):
        return self.compendium.get_object("c_rarity", value)


class ItemScrollSchema(Schema):
    id = fields.Integer(data_key="id", requied=True)
    name = fields.String(data_key="name", required=True)
    rarity = fields.Method(None, "load_rarity")
    cost = fields.Integer(data_key="cost", required=True)
    level = fields.Integer(data_key="level", required=True)
    school = fields.Method(None, "load_school", required=True)
    classes = fields.Method(None, "load_classes", allow_none=True)
    source = fields.String(data_key="source", required=False, allow_none=True)
    notes = fields.String(data_key="notes", required=False, allow_none=True)

    def __init__(self, compendium, **kwargs):
        super().__init__(**kwargs)
        self.compendium = compendium

    @post_load
    def make_item_scroll(self, data, **kwargs):
        return ItemScroll(**data)

    def load_school(self, value):
        return self.compendium.get_object("c_magic_school", value)

    def load_classes(self, value):
        ary = []
        if len(value) > 0:
            for c in value:
                ary.append(self.compendium.get_object("c_character_class", c))

        return ary

    def load_rarity(self, value):
        return self.compendium.get_object("c_rarity", value)
