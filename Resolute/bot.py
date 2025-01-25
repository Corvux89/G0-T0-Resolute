import asyncio
import logging
import signal
import aiopg.sa
from aiopg.sa import create_engine
from discord.ext import commands
from timeit import default_timer as timer
from quart import Quart
from sqlalchemy.schema import CreateTable
from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, PORT
from Resolute.helpers.general_helpers import get_selection
from Resolute.models import metadata
from Resolute.models.objects.adventures import Adventure, AdventureSchema, get_adventure_by_category_channel_query, get_adventure_by_role_query
from Resolute.models.objects.arenas import Arena, ArenaSchema, get_arena_by_channel_query
from Resolute.models.objects.characters import CharacterSchema, PlayerCharacter, PlayerCharacterClass, get_character_from_id
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player, PlayerSchema, get_player_query, upsert_player_query
from Resolute.models.objects.shatterpoint import ShatterPointSchema, Shatterpoint, get_shatterpoint_query
from Resolute.models.objects.store import Store, StoreSchema, get_store_items_query

log = logging.getLogger(__name__)   


async def create_tables(conn: aiopg.sa.SAConnection):
    for table in metadata.sorted_tables:
        await conn.execute(CreateTable(table, if_not_exists=True))


class G0T0Bot(commands.Bot):
    db: aiopg.sa.Engine
    compendium: Compendium
    web_app: Quart
    player_guilds: dict = {}

    # Extending/overriding discord.ext.commands.Bot
    def __init__(self, **options):
        super(G0T0Bot, self).__init__(**options)
        self.compendium = Compendium()
        self.web_app = Quart(__name__)

    async def on_ready(self):
        db_start = timer()
        self.db = await create_engine(DB_URL)
        self.dispatch("db_connected")
        db_end = timer()

        log.info(f"Time to create db engine: {db_end - db_start:.2f}")

        async with self.db.acquire() as conn:
            await create_tables(conn)

        web_start = timer()        
        loop = asyncio.get_event_loop()
        loop.create_task(self.web_app.run_task(host="0.0.0.0", port=PORT))
        web_end = timer()

        log.info(f"Time to create web server: {web_end-web_start:.2f}")                

        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info("------")

    async def close(self):
        log.info("Shutting down bot and web server...")
        if hasattr(self, 'web_task'):
            self.web_task.cancel()  
            try:
                await self.web_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, 'db'):
            self.db.close()  
            await self.db.wait_closed()

        await super().close()  

    def run(self, *args, **kwargs):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self.loop.add_signal_handler(sig, lambda: asyncio.create_task(self.close()))
            except (NotImplementedError, RuntimeError):
                pass
        super().run(*args, **kwargs)

    async def get_player_guild(self, guild_id: int) -> PlayerGuild:
        if len(self.player_guilds) > 0 and (guild:= self.player_guilds.get(str(guild_id))):
            return guild

        guild = await PlayerGuild(self.db, guild=self.get_guild(guild_id)).fetch()

        self.player_guilds[str(guild_id)] = guild

        return guild
    
    async def get_character(self, char_id: int) -> PlayerCharacter:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_character_from_id(char_id))
            row = await results.first()

        character: PlayerCharacter = await CharacterSchema(self.db, self.compendium).load(row)

        return character
    
    async def get_adventure_from_role(self, role_id: int) -> Adventure:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_adventure_by_role_query(role_id))
            row = await results.first()

        if row is None:
            return None
        
        adventure = await AdventureSchema(self).load(row)

        return adventure
        
    async def get_adventure_from_category(self, category_channel_id: int) -> Adventure:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_adventure_by_category_channel_query(category_channel_id))
            row = await results.first()

        if row is None:
            return None

        adventure = await AdventureSchema(self).load(row)

        return adventure
    
    async def get_arena(self, channel_id: int) -> Arena:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_arena_by_channel_query(channel_id))
            row = await results.first()

        if row is None:
            return None
        
        arena: Arena = await ArenaSchema(self).load(row)

        return arena
    
    async def get_player(self, player_id: int, guild_id: int, **kwargs) -> Player:
        inactive = kwargs.get('inactive', False)
        lookup_only = kwargs.get('lookup_only', False)
        ctx = kwargs.get('ctx')

        async with self.db.acquire() as conn:
            results = await conn.execute(get_player_query(player_id, guild_id))
            rows = await results.fetchall()

            if len(rows) == 0 and guild_id and not lookup_only:
                player = Player(id=player_id, guild_id=guild_id)
                results = await conn.execute(upsert_player_query(player))
                row = await results.first()
            elif len(rows) == 0 and lookup_only:
                return None
            elif len(rows) == 0 and not guild_id:
                if ctx:
                    guilds = [g for g in self.guilds if g.get_member(player_id)]

                    if len(guilds) == 1:
                        row = None
                        player = Player(id=player_id, guild_id=guilds[0].id)
                        results = await conn.execute(upsert_player_query(player))
                        row = await results.first()
                    elif len(guilds) > 1:
                        guild = await get_selection(ctx, guilds, True, True, None, False, "Which guild is the command for?\n")

                        if guild:
                            player = Player(id=player_id, guild_id=guild.id)
                            results = await conn.execute(upsert_player_query(player))
                            row = await results.first()
                        else:
                            raise G0T0Error("No guild selected.")
                else:
                    raise G0T0Error("Unable to find player")
            else:
                if ctx:
                    guilds = [self.get_guild(r["guild_id"]).name for r in rows]
                    guild = await get_selection(ctx, guilds, True, True, None, False, "Which guild is the command for?\n")
                    row = rows[guilds.index(guild)]
                else:
                    row = rows[0]

        player: Player = await PlayerSchema(self, inactive).load(row)

        return player

    async def get_store_items(self) -> list[Store]:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_store_items_query())
            rows = await results.fetchall()

        store_items = [StoreSchema().load(row) for row in rows]

        return store_items
    
    async def create_character(self, type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs):
        start = timer()

        old_character: PlayerCharacter = kwargs.get('old_character')

        new_character.player_id = player.id
        new_character.guild_id = player.guild_id        

        if type in ['freeroll', 'death']:
            new_character.reroll = True
            old_character.active = False

            if type == 'freeroll':
                new_character.freeroll_from = old_character.id
            else:
                player.handicap_amount = 0

            await old_character.upsert()

        new_character = await new_character.upsert()

        new_class.character_id = new_character.id
        new_class = await new_class.upsert()

        new_character.classes.append(new_class)

        end = timer()

        log.info(f"Time to create character {new_character.id}: [ {end-start:.2f} ]s")

        return new_character
    
    async def get_shatterpoint(self, guild_id: int) -> Shatterpoint:
        async with self.db.acquire() as conn:
            results = await conn.execute(get_shatterpoint_query(guild_id))
            row = await results.first()
        
        if row is None:
            return None
        
        shatterpoint: Shatterpoint = await ShatterPointSchema(self).load(row)

        return shatterpoint
