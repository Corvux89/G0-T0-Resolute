import asyncio
import logging
import sys
from os import listdir

from discord import Color, Embed, Intents
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import BOT_TOKEN, DEFAULT_PREFIX

intents = Intents.default()
intents.members = True
intents.message_content = True

class MyHelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        e = Embed(color=Color.blurple(), description='')
        for page in self.paginator.pages:
            e.description += page
        await destination.send(embed=e)


log_formatter = logging.Formatter("%(asctime)s %(name)s: %(message)s")
handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
log = logging.getLogger("bot")

# # Because Windows is terrible
if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = G0T0Bot(command_prefix=DEFAULT_PREFIX,
              description='Resolute - Created and maintained by Corvux',
              case_insensitive=True,
              help_command=MyHelpCommand(),
              intents=intents
              )

# Load the cogs!
for filename in listdir('Resolute/cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Resolute.cogs.{filename[:-3]}')


@bot.command()
async def ping(ctx):
    print("Pong")
    await ctx.send(f'Pong! Latency is {round(bot.latency * 1000)}ms.')

bot.run(BOT_TOKEN)