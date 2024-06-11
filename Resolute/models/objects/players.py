import sqlalchemy as sa

from marshmallow import Schema, fields, post_load
from sqlalchemy import Column, Integer, BigInteger, and_, update
from sqlalchemy.sql import FromClause
from sqlalchemy.dialects.postgresql import insert

from Resolute.models import metadata
from Resolute.models.objects.characters import PlayerCharacter

class Player(object):
    characters: list[PlayerCharacter]

    def __init__(self, id: int, guild_id: int, **kwargs):
        self.id = id
        self.guild_id = guild_id
        self.handicap_amount: int = kwargs.get('handicap_amount', 0)
        self.cc: int = kwargs.get('cc', 0)
        self.div_cc: int = kwargs.get('div_cc', 0)

        # Virtual Attributes
        self.characters: list[PlayerCharacter] = []

    @property
    def highest_level_character(self) -> PlayerCharacter:
        if hasattr(self, "characters") and self.characters:
            return max(self.characters, key=lambda char: char.level)
        return None
            


player_table = sa.Table(
    "players",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("guild_id", BigInteger, primary_key=True),
    Column("handicap_amount", Integer),
    Column("cc", Integer),
    Column("div_cc", Integer)
)

class PlayerSchema(Schema):
    id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)
    handicap_amount = fields.Integer()
    cc = fields.Integer()
    div_cc = fields.Integer()

    @post_load
    def make_discord_player(self, data, **kwargs):
        return Player(**data)
    

def get_player_query(player_id: int, guild_id: int) -> FromClause:
    return player_table.select().where(
        and_(player_table.c.id == player_id, player_table.c.guild_id == guild_id)
    )

def reset_div_cc(guild_id: int):
    return update(player_table).where(player_table.c.guild_id == guild_id).values(div_cc =0)

def upsert_player_query(player: Player):
    insert_statement = insert(player_table).values(
        id=player.id,
        guild_id=player.guild_id,
        handicap_amount=player.handicap_amount,
        cc=player.cc,
        div_cc=player.div_cc
    ).returning(player_table)

    update_dict = {
        'id': player.id,
        'guild_id': player.guild_id,
        'handicap_amount': player.handicap_amount,
        'cc': player.cc,
        'div_cc': player.div_cc
    }

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['id', 'guild_id'],
        set_=update_dict
    )

    return upsert_statement