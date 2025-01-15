import asyncio
import logging
import signal
from typing import TYPE_CHECKING
import aiopg.sa
from aiopg.sa import create_engine
from discord.ext import commands
from timeit import default_timer as timer
from quart import Quart
from sqlalchemy.schema import CreateTable
from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, PORT
from Resolute.models import metadata

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from Resolute.models.objects.guilds import PlayerGuild, GuildSchema, get_guild_from_id


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

    async def get_player_guild(self, guild_id: int):
        if len(self.player_guilds) > 0 and (guild:= self.player_guilds.get(str(guild_id))):
            return guild

        async with self.db.acquire() as conn:
            async with conn.begin():
                results = await conn.execute(get_guild_from_id(guild_id))
                guild_row = await results.first()

                if guild_row is None:
                    guild = PlayerGuild(id=guild_id)
                    guild: PlayerGuild = await guild.upsert(self)
                else:
                    guild = await GuildSchema(self, guild_id).load(guild_row)

        self.player_guilds[str(guild_id)] = guild
        return guild

