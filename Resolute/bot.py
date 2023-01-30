import logging
import aiopg.sa
from aiopg.sa import create_engine
from discord.ext import commands
from timeit import default_timer as timer
from sqlalchemy.schema import CreateTable
from Resolute.compendium import Compendium
from Resolute.constants import DB_URL
from Resolute.models.db_tables import *

log = logging.getLogger(__name__)


async def create_tables(conn: aiopg.sa.SAConnection):
    for table in metadata.sorted_tables:
        await conn.execute(CreateTable(table, if_not_exists=True))


class G0T0Bot(commands.Bot):
    db: aiopg.sa.Engine
    compendium: Compendium

    # Extending/overriding discord.ext.commands.Bot
    def __init__(self, **options):
        super(G0T0Bot, self).__init__(**options)
        self.compendium = Compendium()

    async def on_ready(self):
        start = timer()
        self.db = await create_engine(DB_URL)
        end = timer()

        log.info(f"Time to create db engine: {end - start}")

        async with self.db.acquire() as conn:
            await create_tables(conn)

        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info("------")
