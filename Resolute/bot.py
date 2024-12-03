import asyncio
import logging
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

        log.info(f"Time to create db engine: {db_end - db_start}")

        async with self.db.acquire() as conn:
            await create_tables(conn)

        web_start = timer()        
        loop = asyncio.get_event_loop()
        loop.create_task(self.web_app.run_task(port=PORT))
        web_end = timer()

        log.info(f"Time to create web server: {web_end-web_start}")                

        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info("------")
