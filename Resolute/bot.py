import asyncio
import logging
import operator
from signal import SIGINT, SIGTERM
from timeit import default_timer as timer
import traceback

import discord
from aiopg.sa import Engine, SAConnection, create_engine, result
import sqlalchemy as sa
from discord.ext import commands
from quart import Quart
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import FromClause, TableClause


from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, ERROR_CHANNEL, PORT
from Resolute.models import metadata
from Resolute.models.categories.categories import (
    ActivityPoints,
    DashboardType,
)
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.characters import (
    PlayerCharacter,
)
from Resolute.models.objects.dashboards import RefDashboard
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.exceptions import (
    G0T0CommandError,
    G0T0Error,
)

from Resolute.models.objects.financial import Financial
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.npc import NPC
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


# TODO -> Fix a lot of these to be class methods
class G0T0Bot(commands.Bot):
    """
    G0T0Bot is a custom bot class that extends the discord.ext.commands.Bot class.
    It includes additional attributes and methods for managing a database, web application,
    and various game-related functionalities.
        db (Engine): The database engine used for database operations.
        player_guilds (dict): A dictionary to cache player guilds.
    Methods:
        __init__(self, **options):
        on_ready(self):
        close(self):
        run(self, *args, **kwargs):
            Runs the bot with the given arguments.
        before_invoke_setup(self, ctx: G0T0Context):
            Sets up the context before invoking a command.
        bot_check(self, ctx: G0T0Context):
            Checks if the bot is ready to execute commands.
        error_handling(self, ctx: discord.ApplicationContext | commands.Context, error):
        query(self, query: FromClause | TableClause, result_type: QueryResultType = QueryResultType.single):
            Executes a database query and returns the result.
        get_player_guild(self, guild_id: int) -> PlayerGuild:
        get_busy_guilds(self) -> list[PlayerGuild]:
            Retrieves a list of busy guilds.
        get_character(self, char_id: int) -> PlayerCharacter:
        get_adventure_from_role(self, role_id: int) -> Adventure:
        get_adventure_from_category(self, category_channel_id: int) -> Adventure:
        get_arena(self, channel_id: int) -> Arena:
        get_player(self, player_id: int, guild_id: int = None, **kwargs) -> Player:
        get_store_items(self) -> list[Store]:
        create_character(self, type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs):
        get_shatterpoint(self, guild_id: int) -> Shatterpoint:
        get_busy_shatterpoints(self) -> list[Shatterpoint]:
            Retrieves a list of busy shatterpoints.
        get_dashboard_from_category(self, category_id: int) -> RefDashboard:
        get_dashboard_from_message(self, message_id: int) -> RefDashboard:
        log(self, ctx: discord.ApplicationContext | discord.Interaction | None, player: discord.Member | discord.ClientUser | Player, author: discord.Member | discord.ClientUser | Player, activity: Activity | str, **kwargs) -> DBLog:
        get_log(self, log_id: int) -> DBLog:
        get_n_player_logs(self, player: Player, n: int = 5) -> list[DBLog]:
        get_player_stats(self, player: Player) -> dict:
        get_character_stats(self, character: PlayerCharacter) -> dict:
        update_player_activity_points(self, player: Player, increment: bool = True):
        manage_player_tier_roles(self, player: Player, reason: str = None):
            Manages the tier roles of a player based on their character levels.
        get_financial_data(self) -> Financial:
            Retrieves financial data from the database.
        get_all_npcs(self) -> list[NPC]:
            Retrieves all NPCs from the database.
    """

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

    async def get_player_stats(self, player: Player) -> dict:
        """
        Asynchronously retrieves player statistics from the database.
        Args:
            player (Player): The player object containing the player's ID and guild ID.
        Returns:
            dict: A dictionary containing the player's statistics.
        """
        new_character_activity = self.compendium.get_activity("NEW_CHARACTER")
        activities = [
            x
            for x in self.compendium.activity[0].values()
            if x.value in ["RP", "ARENA", "ARENA_HOST", "GLOBAL", "SNAPSHOT"]
        ]
        columns = [
            sa.func.sum(
                sa.case([(DBLog.log_table.c.activity == act.id, 1)], else_=0)
            ).label(f"Activity {act.value}")
            for act in activities
        ]

        query = (
            sa.select(
                DBLog.log_table.c.player_id,
                sa.func.count(DBLog.log_table.c.id).label("#"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("debt"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc < 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("credit"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    == new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("starting"),
                *columns,
            )
            .group_by(DBLog.log_table.c.player_id)
            .where(
                sa.and_(
                    DBLog.log_table.c.player_id == player.id,
                    DBLog.log_table.c.guild_id == player.guild_id,
                    DBLog.log_table.c.invalid == False,
                )
            )
        )

        row = await self.query(query)

        return dict(row)

    async def get_character_stats(self, character: PlayerCharacter) -> dict:
        """
        Asynchronously retrieves the statistics for a given character from the database.
        Args:
            character (PlayerCharacter): The character whose statistics are to be retrieved.
        Returns:
            dict: A dictionary containing the character's statistics if found, otherwise None.
        """
        new_character_activity = self.compendium.get_activity("NEW_CHARACTER")
        conversion_activity = self.compendium.get_activity("CONVERSION")

        query = (
            sa.select(
                DBLog.log_table.c.character_id,
                sa.func.count(DBLog.log_table.c.id).label("#"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("cc debt"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("cc credit"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc > 0,
                                    DBLog.log_table.c.activity
                                    == new_character_activity.id,
                                ),
                                DBLog.log_table.c.cc,
                            )
                        ],
                        else_=0,
                    )
                ).label("cc starting"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.credits > 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.credits,
                            )
                        ],
                        else_=0,
                    )
                ).label("credit debt"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.cc < 0,
                                    DBLog.log_table.c.activity
                                    != new_character_activity.id,
                                ),
                                DBLog.log_table.c.credits,
                            )
                        ],
                        else_=0,
                    )
                ).label("credit credit"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                sa.and_(
                                    DBLog.log_table.c.credits > 0,
                                    DBLog.log_table.c.activity
                                    == new_character_activity.id,
                                ),
                                DBLog.log_table.c.credits,
                            )
                        ],
                        else_=0,
                    )
                ).label("credit starting"),
                sa.func.sum(
                    sa.case(
                        [
                            (
                                DBLog.log_table.c.activity == conversion_activity.id,
                                DBLog.log_table.c.credits,
                            )
                        ],
                        else_=0,
                    )
                ).label("credits converted"),
            )
            .group_by(DBLog.log_table.c.character_id)
            .where(
                sa.and_(
                    DBLog.log_table.c.character_id == character.id,
                    DBLog.log_table.c.invalid == False,
                )
            )
        )

        row = await self.query(query)

        if row is None:
            return None

        return dict(row)

    async def update_player_activity_points(
        self, player: Player, increment: bool = True
    ):
        """
        Updates the activity points of a player and adjusts their activity level accordingly.
        Args:
            player (Player): The player whose activity points are to be updated.
            increment (bool, optional): If True, increment the player's activity points by 1.
                                        If False, decrement the player's activity points by 1,
                                        but not below 0. Defaults to True.
        Updates:
            player.activity_points (int): The updated activity points of the player.
            player.activity_level (int): The updated activity level of the player if it changes.
        Sends:
            A message to the player's guild activity points channel if the activity level increases.
            A message to the player's guild staff channel and a direct message to the player if the activity level decreases.
        Logs:
            An activity log entry for the activity level change.
        Database:
            Updates the player's activity points in the database.
        """
        if increment:
            player.activity_points += 1
        else:
            player.activity_points = max(player.activity_points - 1, 0)

        points = sorted(
            self.compendium.activity_points[0].values(), key=operator.attrgetter("id")
        )
        activity_point: ActivityPoints = None

        for point in points:
            point: ActivityPoints
            if player.activity_points >= point.points:
                activity_point = point
            elif player.activity_points < point.points:
                break

        if (activity_point and player.activity_level != activity_point.id) or (
            increment == False and not activity_point
        ):
            revert = (
                True
                if not activity_point
                or (activity_point and player.activity_level > activity_point.id)
                else False
            )
            player.activity_level = activity_point.id if activity_point else 0

            activity_log = await DBLog.create(
                self,
                None,
                player,
                self.user,
                "ACTIVITY_REWARD",
                notes=f"Activity Level {player.activity_level+1 if revert else player.activity_level}{' [REVERSION]' if revert else ''}",
                cc=-1 if revert else 0,
                silent=True,
            )

            if player.guild.activity_points_channel and not revert:
                await player.guild.activity_points_channel.send(
                    embed=LogEmbed(activity_log), content=f"{player.member.mention}"
                )

            if player.guild.staff_channel and revert:
                await player.guild.staff_channel.send(embed=LogEmbed(activity_log))
                await player.member.send(embed=LogEmbed(activity_log))

        else:
            await player.upsert()

    async def manage_player_tier_roles(self, player: Player, reason: str = None):
        # Primary Role handling
        if player.highest_level_character and player.highest_level_character.level >= 3:
            if (
                player.guild.member_role
                and player.guild.member_role not in player.member.roles
            ):
                await player.member.add_roles(player.guild.member_role, reason=reason)

        # Character Tier Roles
        if player.guild.entry_role:
            if player.has_character_in_tier(self.compendium, 1):
                if player.guild.entry_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.entry_role, reason=reason
                    )
            elif player.guild.entry_role in player.member.roles:
                await player.member.remove_roles(player.guild.entry_role, reason=reason)

        if player.guild.tier_2_role:
            if player.has_character_in_tier(self.compendium, 2):
                if player.guild.tier_2_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.tier_2_role, reason=reason
                    )
            elif player.guild.tier_2_role in player.member.roles:
                await player.member.remove_roles(
                    player.guild.tier_2_role, reason=reason
                )

        if player.guild.tier_3_role:
            if player.has_character_in_tier(self.compendium, 3):
                if player.guild.tier_3_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.tier_3_role, reason=reason
                    )
            elif player.guild.tier_3_role in player.member.roles:
                await player.member.remove_roles(
                    player.guild.tier_3_role, reason=reason
                )

        if player.guild.tier_4_role:
            if player.has_character_in_tier(self.compendium, 4):
                if player.guild.tier_4_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.tier_4_role, reason=reason
                    )
            elif player.guild.tier_4_role in player.member.roles:
                await player.member.remove_roles(
                    player.guild.tier_4_role, reason=reason
                )

        if player.guild.tier_5_role:
            if player.has_character_in_tier(self.compendium, 5):
                if player.guild.tier_5_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.tier_5_role, reason=reason
                    )
            elif player.guild.tier_5_role in player.member.roles:
                await player.member.remove_roles(
                    player.guild.tier_5_role, reason=reason
                )

        if player.guild.tier_6_role:
            if player.has_character_in_tier(self.compendium, 6):
                if player.guild.tier_6_role not in player.member.roles:
                    await player.member.add_roles(
                        player.guild.tier_6_role, reason=reason
                    )
            elif player.guild.tier_6_role in player.member.roles:
                await player.member.remove_roles(
                    player.guild.tier_6_role, reason=reason
                )

    async def get_financial_data(self) -> Financial:

        row = await self.query(Financial.financial_table.select())

        if row is None:
            return None

        fin = Financial.FinancialSchema(self.db).load(row)

        return fin

    async def update_financial_dashboards(self) -> None:
        dashboards = []

        d_type = self.compendium.get_object(DashboardType, "FINANCIAL")

        query = RefDashboard.ref_dashboard_table.select().where(
            RefDashboard.ref_dashboard_table.c.dashboard_type == d_type.id
        )

        rows = await self.query(query, QueryResultType.multiple)

        dashboards = [RefDashboard.RefDashboardSchema(self).load(row) for row in rows]

        for dashboard in dashboards:
            await dashboard.refresh(self)

    async def get_all_npcs(self) -> list[NPC]:
        query = NPC.npc_table.select().order_by(NPC.npc_table.c.key.asc())

        npcs = [
            NPC.NPCSchema(self.db).load(row)
            for row in await self.query(query, QueryResultType.multiple)
        ]

        return npcs
