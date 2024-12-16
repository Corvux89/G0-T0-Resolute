import asyncio
import logging
import signal
from threading import Thread
import aiopg.sa
from aiopg.sa import create_engine
from discord.ext import commands
from timeit import default_timer as timer
from quart import Quart, jsonify
from sqlalchemy.schema import CreateTable
from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, PORT
from Resolute.models import metadata


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
