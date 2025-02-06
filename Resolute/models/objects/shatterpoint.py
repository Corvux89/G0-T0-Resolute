from enum import Enum

import aiopg.sa
import sqlalchemy as sa
from discord import ForumChannel, Message, TextChannel, Thread, User
from marshmallow import Schema, fields, post_load
from sqlalchemy import (BOOLEAN, BigInteger, Boolean, Column, Integer, String,
                        and_, cast, update)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.selectable import FromClause, TableClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.guilds import PlayerGuild


class AdjustOperator(Enum):
    """
    Enum class representing adjustment operators.
    Attributes:
        less (str): Represents the less than or equal to operator ("<=").
        greater (str): Represents the greater than or equal to operator (">=").
    """

    less = "<="
    greater = ">="


class Shatterpoint(object):
    """
    Represents a Shatterpoint object which is used to manage and interact with shatterpoints in a Discord guild.
    Attributes:
        _db (aiopg.sa.Engine): The database engine used for database operations.
        guild_id (int): The ID of the Discord guild.
        name (str): The name of the shatterpoint.
        base_cc (int): The base command currency (cc) for the shatterpoint.
        channels (list[int]): A list of channel IDs associated with the shatterpoint.
        busy (bool): A flag indicating whether the shatterpoint is busy.
        players (list[ShatterpointPlayer]): A list of players associated with the shatterpoint.
        renown (list[ShatterpointRenown]): A list of renown objects associated with the shatterpoint.
    Methods:
        __init__(db: aiopg.sa.Engine, **kwargs):
            Initializes a new instance of the Shatterpoint class.
        upsert():
            Asynchronously inserts or updates the shatterpoint in the database.
        delete():
            Asynchronously deletes the shatterpoint and its associated players and renown from the database.
        scrape_channel(bot, channel: TextChannel|Thread|ForumChannel, guild: PlayerGuild, user: User):
            Asynchronously scrapes messages from a specified channel, updates player data, and persists changes to the database.
    """

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db
        self.guild_id = kwargs.get('guild_id')
        self.name = kwargs.get('name', "New Shatterpoint")
        self.base_cc = kwargs.get('base_cc', 0)
        self.channels: list[int] = kwargs.get('channels', [])
        self.busy = kwargs.get('busy', False)

        self.players: list[ShatterpointPlayer] = kwargs.get('players', [])
        self.renown: list[ShatterpointRenown] = kwargs.get('renown', [])
    
    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_shatterpoint_query(self))

    async def delete(self):
        async with self._db.acquire() as conn:
            await conn.execute(delete_shatterpoint_query(self.guild_id))
            await conn.execute(delete_shatterpoint_players(self.guild_id))
            await conn.execute(delete_all_shatterpoint_renown_query(self.guild_id))

    async def scrape_channel(self, bot, channel: TextChannel|Thread|ForumChannel, guild: PlayerGuild, user: User):
        messages = []
        channels = self.channels

        def get_char_name_from_message(message: Message) -> str:
            try:
                char_name = message.author.name.split(' // ')[0].split('] ', 1)[1].strip()
            except:
                return None
            
            return char_name

        try:
            while True:
                last_message: Message = messages[-1] if messages else None
                batch = await channel.history(limit=600, before=last_message).flatten()

                if not batch:
                    break

                messages.extend(batch)
        except Exception as e:
            print(e)

        print(len(messages))
        characters = await guild.get_all_characters(bot.compendium)

        for message in messages:
            player: ShatterpointPlayer = None
            if not message.author.bot:
                player = next((p for p in self.players if p.player_id == message.author.id), 
                                ShatterpointPlayer(bot.db, guild_id=self.guild_id,
                                                    player_id=message.author.id,
                                                    cc=self.base_cc))
            elif (char_name := get_char_name_from_message(message)) and (character := next((c for c in characters if c.name.lower() == char_name.lower()), None)):
                player = next((p for p in self.players if p.player_id == character.player_id), 
                                ShatterpointPlayer(bot.db, guild_id=self.guild_id,
                                                    player_id=character.player_id,
                                                    cc=self.base_cc))
                if character.id not in player.characters:
                    player.characters.append(character.id)
                    
            if player:
                player.num_messages +=1 

                if message.channel.id not in player.channels:
                    player.channels.append(message.channel.id)
                
                await player.upsert()

                if player.player_id not in [p.player_id for p in self.players]:
                    self.players.append(player)
        
        if message.channel.id not in channels:
            channels.append(message.channel.id)

        shatterpoint: Shatterpoint = await bot.get_shatterpoint(self.guild_id)
        shatterpoint.busy = False
        for c in channels:
            if c not in shatterpoint.channels:
                shatterpoint.channels.append(c)

        await shatterpoint.upsert()
        await user.send(f"**{shatterpoint.name}**: Finished scraping {len(messages):,} messages in {channel.jump_url}")

        

ref_gb_staging_table = sa.Table(
    "ref_gb_staging",
    metadata,
    Column("guild_id", BigInteger, primary_key=True, nullable=False),  # ref: > guilds.id
    Column("name", String, nullable=False),
    Column("base_cc", Integer, nullable=False),
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[]),
    Column("busy", Boolean, nullable=True, default=False)
)

class ShatterPointSchema(Schema):
    bot = None

    guild_id = fields.Integer(required=True)
    name = fields.String(required=True)
    base_cc = fields.Integer(required=True)
    channels = fields.List(fields.Integer, load_default=[], required=False)
    busy = fields.Boolean(required=False, load_default=False, allow_none=True)

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    async def make_shatterpoint(self, data, **kwargs):
        shatterpoint = Shatterpoint(self.bot.db, **data)
        await self.get_players(shatterpoint)
        await self.get_renown(shatterpoint)
        return shatterpoint
    
    async def get_players(self, shatterpoint: Shatterpoint):
        async with self.bot.db.acquire() as conn:
            results = await conn.execute(get_all_shatterpoint_players_query(shatterpoint.guild_id))
            rows = await results.fetchall()

        shatterpoint.players = [await ShatterPointPlayerSchema(self.bot).load(row) for row in rows]

    async def get_renown(self, shatterpoint: Shatterpoint):
        async with self.bot.db.acquire() as conn:
            results = await conn.execute(get_shatterpoint_renown_query(shatterpoint.guild_id))
            rows = await results.fetchall()

        shatterpoint.renown = [RefRenownSchema(self.bot.db, self.bot.compendium).load(row) for row in rows]

def upsert_shatterpoint_query(shatterpoint: Shatterpoint):
    insert_statement = insert(ref_gb_staging_table).values(
        guild_id=shatterpoint.guild_id,
        name=shatterpoint.name,
        base_cc=shatterpoint.base_cc,
        channels=shatterpoint.channels,
        busy=shatterpoint.busy
    ).returning(ref_gb_staging_table)

    update_dict = {
        "name": shatterpoint.name,
        "base_cc": shatterpoint.base_cc,
        "channels": shatterpoint.channels,
        "busy": shatterpoint.busy
    }

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=['guild_id'],
        set_=update_dict
    )

    return upsert_statement

def reset_busy_flag_query():
    return update(ref_gb_staging_table).where(ref_gb_staging_table.c.busy == True).values(busy=False)

def get_shatterpoint_query(guild_id: int) -> FromClause:
    return ref_gb_staging_table.select().where(
        ref_gb_staging_table.c.guild_id == guild_id
    )

def delete_shatterpoint_query(guild_id: int) -> TableClause:
    return ref_gb_staging_table.delete().where(ref_gb_staging_table.c.guild_id == guild_id)


class ShatterpointPlayer(object):
    """
    Represents a player in the Shatterpoint game.
    Attributes:
        _db (aiopg.sa.Engine): The database engine.
        guild_id (Optional[int]): The ID of the guild the player belongs to.
        player_id (Optional[int]): The ID of the player.
        cc (Optional[int]): The player's command center level.
        update (bool): Flag indicating whether the player should be updated. Defaults to True.
        active (bool): Flag indicating whether the player is active. Defaults to True.
        num_messages (int): The number of messages the player has sent. Defaults to 0.
        channels (list[int]): List of channel IDs the player is associated with. Defaults to an empty list.
        characters (list[int]): List of character IDs the player owns. Defaults to an empty list.
        renown_override (Optional[int]): Override value for the player's renown.
        player_characters (list[PlayerCharacter]): List of PlayerCharacter objects associated with the player. Defaults to an empty list.
    Methods:
        upsert(): Inserts or updates the player record in the database.
    """

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db

        self.guild_id = kwargs.get('guild_id')
        self.player_id = kwargs.get('player_id')
        self.cc = kwargs.get('cc')
        self.update = kwargs.get('update', True)
        self.active = kwargs.get('active', True)
        self.num_messages = kwargs.get('num_messages', 0)
        self.channels: list[int] = kwargs.get('channels', [])
        self.characters: list[int] = kwargs.get('characters', [])
        self.renown_override: int = kwargs.get('renown_override')

        self.player_characters: list[PlayerCharacter] = kwargs.get('player_characters', [])

    async def upsert(self):
        async with self._db.acquire() as conn:
            await conn.execute(upsert_shatterpoint_player_query(self))


ref_gb_staging_player_table = sa.Table(
    "ref_gb_staging_player",
    metadata,
    Column("guild_id", BigInteger, nullable=False),  # ref: > ref_gb_staging.id
    Column("player_id", BigInteger, nullable=False),  # ref: > characters.player_id
    Column("cc", Integer, nullable=False),
    Column("update", BOOLEAN, nullable=False, default=True),
    Column("active", BOOLEAN, nullable=False, default=True),
    Column("num_messages", Integer, nullable=False, default=0),
    Column("channels", sa.ARRAY(BigInteger), nullable=True, default=[]),
    Column("characters", sa.ARRAY(Integer), nullable=False, default=[]),
    Column("renown_override", Integer, nullable=True)
)

class ShatterPointPlayerSchema(Schema):
    bot = None

    guild_id = fields.Integer(required=True)
    player_id = fields.Integer(required=True)
    cc = fields.Integer(required=True)
    update = fields.Boolean(required=True)
    active = fields.Boolean(required=True)
    num_messages = fields.Integer(required=True)
    channels = fields.List(fields.Integer, load_default=[], required=False)
    characters = fields.List(fields.Integer, required=True)
    renown_override = fields.Integer(required=False, allow_none=True)
    sa.PrimaryKeyConstraint("guild_id", "player_id")

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    async def make_globPlayer(self, data, **kwargs):
        player = ShatterpointPlayer(self.bot.db, **data)
        await self.get_characters(player)
        return player
    
    async def get_characters(self, player: ShatterpointPlayer):
        player.player_characters = [
            await self.bot.get_character(c) for c in player.characters
        ]

def upsert_shatterpoint_player_query(spplayer: ShatterpointPlayer):
    insert_dict = {
        "guild_id": spplayer.guild_id,
        "player_id": spplayer.player_id,
        "cc": spplayer.cc,
        "update": spplayer.update,
        "active": spplayer.active,
        "num_messages": spplayer.num_messages,
        "channels": spplayer.channels,
        "characters": spplayer.characters,
        "renown_override": spplayer.renown_override
    }

    statement = insert(ref_gb_staging_player_table).values(insert_dict)

    statement = statement.on_conflict_do_update(
        index_elements=["guild_id", "player_id"],
        set_={
            "cc": statement.excluded.cc,
            "renown_override": statement.excluded.renown_override,
            "num_messages": statement.excluded.num_messages,
            "channels": statement.excluded.channels,
            "characters": statement.excluded.characters,
            "update": statement.excluded.get('update', False),
            "active": statement.excluded.get('active', True)
        }
    )

    return statement.returning(ref_gb_staging_player_table)

def get_all_shatterpoint_players_query(guild_id: int) -> FromClause:
    return ref_gb_staging_player_table.select().where(
        ref_gb_staging_player_table.c.guild_id == guild_id
    )

def delete_shatterpoint_players(guild_id: int) -> TableClause:
    return ref_gb_staging_player_table.delete().where(ref_gb_staging_player_table.c.guild_id == guild_id)

class ShatterpointRenown(object):
    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db
        self.guild_id = kwargs.get('guild_id')
        self.faction: Faction = kwargs.get('faction')
        self.renown = kwargs.get('renown', 0)

    async def upsert(self):
        async with self._db.acquire() as conn:
            await conn.execute(upsert_shatterpoint_renown_query(self))

    async def delete(self):
        async with self._db.acquire() as conn:
            await conn.execute(delete_specific_shatterpoint_renown_query(self))

ref_gb_renown_table = sa.Table(
    "ref_gb_renown",
    metadata,
    Column("guild_id", Integer, nullable=False),
    Column("faction", Integer, nullable=False),
    Column("renown", Integer, nullable=False, default=0),
    sa.PrimaryKeyConstraint("guild_id", "faction")
)

class RefRenownSchema(Schema):
    compendium: Compendium
    db: aiopg.sa.Engine
    guild_id = fields.Integer(required=True)
    faction = fields.Method(None, "load_faction")
    renown = fields.Integer(required=True)

    def __init__(self, db: aiopg.sa.Engine, compendium: Compendium, **kwargs):
        self.compendium = compendium
        self.db = db
        super().__init__(**kwargs)

    def load_faction(self, value):
        return self.compendium.get_object(Faction, value)

    @post_load
    def make_gbrenown(self, data, **kwargs):
        return ShatterpointRenown(self.db, **data)

def upsert_shatterpoint_renown_query(renown: ShatterpointRenown):
    insert_dict = {
        "guild_id": renown.guild_id,
        "faction": renown.faction.id,
        "renown": renown.renown
    }

    statement = insert(ref_gb_renown_table).values(insert_dict)

    statement = statement.on_conflict_do_update(
        index_elements=["guild_id", "faction"],
        set_={
            "renown": statement.excluded.renown
        }
    )

    return statement.returning(ref_gb_renown_table)

def get_shatterpoint_renown_query(guild_id: int) -> FromClause:
    return ref_gb_renown_table.select().where(
        ref_gb_renown_table.c.guild_id == guild_id
    )

def delete_specific_shatterpoint_renown_query(renown: ShatterpointRenown) -> TableClause:
    return ref_gb_renown_table.delete().where(
        and_(ref_gb_renown_table.c.guild_id == renown.guild_id, ref_gb_renown_table.c.faction == renown.faction.id)
    )

def delete_all_shatterpoint_renown_query(guild_id: int) -> TableClause:
    return ref_gb_renown_table.delete().where(
        ref_gb_renown_table.c.guild_id == guild_id
    )