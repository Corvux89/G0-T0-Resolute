import asyncio
import logging
import sys
import traceback
import discord

from os import listdir
from discord import Intents, ApplicationContext
from discord.ext import commands
from Resolute.bot import G0T0Bot
from Resolute.constants import BOT_TOKEN, DEFAULT_PREFIX, DEBUG_GUILDS, ERROR_CHANNEL
from Resolute.helpers import is_admin

intents = Intents.default()
intents.members = True
intents.message_content = True

class MyHelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        e = discord.Embed(color=discord.Color.blurple(), description='')
        for page in self.paginator.pages:
            e.description += page
        await destination.send(embed=e)


log_formatter = logging.Formatter("%(asctime)s %(name)s: %(message)s")
handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
log = logging.getLogger("bot")

# Because Windows is terrible
if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = G0T0Bot(command_prefix=DEFAULT_PREFIX,
              description='Resolute - Created and maintained by Corvux',
              case_insensitive=True,
              help_command=MyHelpCommand(),
              intents=intents,
              debug_guilds=DEBUG_GUILDS
              )

for filename in listdir('Resolute/cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Resolute.cogs.{filename[:-3]}')


@bot.command()
async def ping(ctx):
    print("Pong")
    await ctx.send(f'Pong! Latency is {round(bot.latency * 1000)}ms.')

@bot.command(name="asay")
@commands.check(is_admin)
async def admin_say(ctx: ApplicationContext, channel_id, msg):
    channel = discord.utils.get(ctx.guild.channels, id=int(channel_id))
    if channel is not None:
        try:
            await channel.send(msg)
        except:
            log.warning('Unable to send message')
    return await ctx.respond("No channel found")


@bot.event
async def on_application_command_error(ctx: ApplicationContext, error):
    # Prevent any commands with local error handling from being handled here
    if hasattr(ctx.command, 'on_error'):
        return

    if isinstance(error, discord.errors.CheckFailure):
        return await ctx.respond(f'You do not have required permissions for `{ctx.command}`')
    else:
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            if ctx.selected_options is not None:
                params = "".join([f" [{p['name']}: {p['value']}]" for p in ctx.selected_options]) or ""
            else:
                params = ""
            out_str = "Error in command: cmd: chan {0.channel} [{0.channel.id}], serv: {0.guild} [{0.guild.id}] auth: {0.user} [{0.user.id}]: {0.command} ".format(ctx) + params
            out_str += f"\n```"
            for line in traceback.format_exception(type(error), error, error.__traceback__):
                out_str+=line
            out_str += "```"
            
            if ERROR_CHANNEL:
                try:
                    await ctx.bot.get_channel(int(ERROR_CHANNEL)).send(out_str)
                except:
                    log.error(out_str)
            else:
                log.error(out_str)

        try:
            if hasattr(ctx, "bot") and not hasattr(ctx.bot, "db"):
                return await ctx.respond(f"Try again in a few seconds. I'm not fully awake yet.", ephemeral=True)
            return await ctx.respond(f'Something went wrong. Let us know if it keeps up!', ephemeral=True)
        except:
            log.warning('Unable to respond')


@bot.event
async def on_application_command(ctx):
    try:
        if ctx.selected_options is not None:
            params = "".join([f" [{p['name']}: {p['value']}]" for p in ctx.selected_options])
        else:
            params = ""
        log.info(
            "cmd: chan {0.channel} [{0.channel.id}], serv: {0.guild} [{0.guild.id}],"
            " auth: {0.user} [{0.user.id}]: {0.command} ".format(ctx) + params
        )
    except AttributeError:
        log.info("Command in PM with {0.message.author} ({0.message.author.id}): {0.message.content}.".format(ctx))


bot.run(BOT_TOKEN)
