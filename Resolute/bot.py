import asyncio
import logging
from signal import SIGINT, SIGTERM
from timeit import default_timer as timer
import traceback

import discord
from aiopg.sa import Engine, SAConnection, create_engine, result
from discord.ext import commands
from quart import Quart
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import FromClause, TableClause


from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, ERROR_CHANNEL, PORT
from Resolute.models import metadata
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.exceptions import (
    G0T0CommandError,
    G0T0Error,
)

from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.npc import NonPlayableCharacter
from Resolute.models.objects.players import Player


log = logging.getLogger(__name__)


async def create_tables(conn: SAConnection):
    for table in metadata.sorted_tables:
        await conn.execute(CreateTable(table, if_not_exists=True))


class G0T0Context(discord.ApplicationContext):
    bot: "G0T0Bot"

    def __init__(self, **kwargs):
        super(G0T0Context).__init__(**kwargs)
        self.player: Player = None
        self.playerGuild: PlayerGuild = None

    def __repr__(self):
        return f"<{self.__class__.__name__} author={self.author.id:!r} channel={self.channel.name!r}"


class G0T0Bot(commands.Bot):
    db: Engine
    compendium: Compendium
    web_app: Quart
    player_guilds: dict = {}

    # Extending/overriding discord.ext.commands.Bot
    def __init__(self, **options):
        """
        Initializes the G0T0Bot instance with the given options.
        Args:
            **options: Arbitrary keyword arguments that are passed to the parent class initializer.
        Attributes:
            compendium (Compendium): An instance of the Compendium class.
            web_app (Quart): An instance of the Quart web application.
        """

        super(G0T0Bot, self).__init__(**options)
        self.compendium = Compendium()
        self.web_app = Quart(__name__)

        self.check(self.bot_check)
        self.before_invoke(self.before_invoke_setup)
        self.add_listener(self.error_handling, "on_error")
        self.add_listener(self.error_handling, "on_command_error")
        self.add_listener(self.error_handling, "on_application_command_error")

    async def on_ready(self):
        """
        Event handler for when the bot is ready.
        This method is called when the bot has successfully connected to Discord and is ready to start interacting.
        It performs the following tasks:
        1. Connects to the database and creates the necessary tables.
        2. Starts the web server for the bot.
        The method logs the time taken to create the database engine and the web server, and logs the bot's user information.
        Raises:
            Exception: If there is an error in creating the database engine or starting the web server.
        """

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
        """
        Asynchronously closes the bot and web server.
        This method performs the following steps:
        1. Logs the shutdown process.
        2. Cancels the web server task if it exists and waits for it to finish.
        3. Closes the database connection if it exists and waits for it to close.
        4. Calls the superclass's close method to perform any additional cleanup.
        Raises:
            CancelledError: If the web server task is cancelled during the shutdown process.
        """

        log.info("Shutting down bot and web server...")
        if hasattr(self, "web_task"):
            self.web_task.cancel()
            try:
                await self.web_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "db"):
            self.db.close()
            await self.db.wait_closed()

        await super().close()

    def run(self, *args, **kwargs):
        for sig in (SIGINT, SIGTERM):
            try:
                self.loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.close())
                )
            except (NotImplementedError, RuntimeError):
                pass
        super().run(*args, **kwargs)

    async def before_invoke_setup(self, ctx: commands.Context):
        ctx: G0T0Context = ctx
        if hasattr(ctx, "defer"):
            await ctx.defer()
        ctx.player = await Player.get_player(
            self, ctx.author.id, ctx.guild.id if ctx.guild else None, ctx=ctx
        )

        ctx.playerGuild = (
            await PlayerGuild.get_player_guild(self, ctx.guild.id)
            if ctx.guild
            else None
        )

        await ctx.player.update_command_count(str(ctx.command))
        params = "".join(
            [
                f" [{p['name']}: {p['value']}]"
                for p in (
                    ctx.selected_options
                    if hasattr(ctx, "selected_options") and ctx.selected_options
                    else []
                )
            ]
        )

        try:
            log.info(
                f"cmd: chan {ctx.channel} [{ctx.channel.id}], serv: {f'{ctx.guild.name} [{ctx.guild.id}]' if ctx.guild.id else 'DM'}, "
                f"auth: {ctx.author} [{ctx.author.id}]: {ctx.command}  {params}"
            )
        except AttributeError as e:
            log.info(
                f"Command in DM with {ctx.author} [{ctx.author.id}]: {ctx.command} {params}"
            )

    async def bot_check(self, ctx: discord.ApplicationContext | commands.Context):
        if (
            hasattr(self, "db")
            and self.db
            and hasattr(self, "compendium")
            and self.compendium
        ):
            return True

        if isinstance(ctx, commands.Context):
            raise G0T0CommandError(
                "Try again in a few seconds. I'm not fully awake yet"
            )
        raise G0T0Error("Try again in a few seconds. I'm not fully awake yet")

    async def error_handling(
        self, ctx: discord.ApplicationContext | commands.Context, error
    ):
        """
        Handles errors that occur during the execution of application commands.
        Parameters:
        ctx (discord.ApplicationContext): The context in which the command was invoked.
        error (Exception): The error that was raised during command execution.
        Returns:
        None
        This function performs the following actions:
        - If the command has a custom error handler (`on_error`), it returns immediately.
        - If the error is a `CheckFailure`, it responds with a message indicating insufficient permissions.
        - If the error is a `G0T0Error`, it responds with an embedded error message.
        - Logs detailed error information to a specified error channel or to the log if the error channel is not available.
        - Responds with appropriate messages for specific conditions such as bot not being fully initialized or command not supported in direct messages.
        """
        # Cleanup
        try:
            await ctx.defer()
            await ctx.delete()
        except:
            pass

        if isinstance(error, commands.CommandNotFound) and isinstance(
            ctx, commands.Context
        ):
            return await ctx.send(
                embed=ErrorEmbed(f"No npc with the key `{ctx.invoked_with}` found.")
            )

        elif (
            hasattr(ctx.command, "on_error")
            or isinstance(error, (commands.CommandNotFound))
            or "Unknown interaction" in str(error)
        ):
            return

        elif isinstance(
            error,
            (G0T0Error, discord.CheckFailure, G0T0CommandError, commands.CheckFailure),
        ):
            return await ctx.send(embed=ErrorEmbed(error))

        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db"):
            params = (
                "".join(
                    [
                        f" [{p['name']}: {p['value']}]"
                        for p in (ctx.selected_options or [])
                    ]
                )
                if hasattr(ctx, "selected_options") and ctx.selected_options
                else ""
            )

            out_str = (
                f"Error in command: cmd: chan {ctx.channel} [{ctx.channel.id}], {f'serv: {ctx.guild} [{ctx.guild.id}]' if ctx.guild else ''} auth: {ctx.author} [{ctx.author.id}]: {ctx.command} {params}\n```"
                f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"
                f"```"
            )

            if ERROR_CHANNEL:
                try:
                    await ctx.bot.get_channel(int(ERROR_CHANNEL)).send(out_str)
                except:
                    log.error(out_str)
            else:
                log.error(out_str)

        try:
            return await ctx.send(
                embed=ErrorEmbed(f"Something went wrong. Let us know if it keeps up!")
            )
        except:
            log.warning("Unable to respond")

    async def query(
        self,
        query: FromClause | TableClause,
        result_type: QueryResultType = QueryResultType.single,
    ) -> result.RowProxy | list[result.RowProxy] | None:
        """
        Executes a database query and returns the result based on the specified result type.
        Args:
            query (FromClause | TableClause): The SQL query to be executed.
            result_type (QueryResultType, optional): The type of result expected from the query.
                Defaults to QueryResultType.single.
        Returns:
            result.RowProxy | list[result.RowProxy]: The result of the query. The type of the result
                depends on the specified result_type:
                - QueryResultType.single: Returns a single row.
                - QueryResultType.multiple: Returns a list of rows.
                - QueryResultType.scalar: Returns a single scalar value.
                - None: If the result_type is has no return.
        """
        async with self.db.acquire() as conn:
            results = await conn.execute(query)

            if result_type == QueryResultType.single:
                return await results.first()
            elif result_type == QueryResultType.multiple:
                return await results.fetchall()
            elif result_type == QueryResultType.scalar:
                return await results.scalar()
            else:
                return None
