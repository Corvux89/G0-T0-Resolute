import asyncio
import logging
import operator
from math import ceil
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
from Resolute.helpers import get_selection
from Resolute.models import metadata
from Resolute.models.categories.categories import (
    Activity,
    ActivityPoints,
    CodeConversion,
    DashboardType,
    Faction,
)
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.arenas import Arena
from Resolute.models.objects.characters import (
    PlayerCharacter,
    PlayerCharacterClass,
)
from Resolute.models.objects.dashboards import RefDashboard
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.exceptions import (
    G0T0CommandError,
    G0T0Error,
    TransactionError,
)

from Resolute.models.objects.financial import Financial
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.npc import NPC
from Resolute.models.objects.players import Player
from Resolute.models.objects.shatterpoint import Shatterpoint
from Resolute.models.objects.store import Store


log = logging.getLogger(__name__)


async def create_tables(conn: SAConnection):
    for table in metadata.sorted_tables:
        await conn.execute(CreateTable(table, if_not_exists=True))


class G0T0Context(discord.ApplicationContext):
    def __init__(self, **kwargs):
        super(G0T0Context).__init__(**kwargs)

        self.player: Player = None
        self.playerGuild: PlayerGuild = None


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

    async def before_invoke_setup(self, ctx: G0T0Context):
        ctx.player = await self.get_player(
            ctx.author.id, ctx.guild.id if ctx.guild else None
        )
        ctx.playerGuild = (
            await self.get_player_guild(ctx.guild.id) if ctx.guild else None
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

    async def get_player_guild(self, guild_id: int) -> PlayerGuild:
        """
        Asynchronously retrieves a PlayerGuild object for the given guild ID.
        If the guild is already cached in `self.player_guilds`, it returns the cached guild.
        Otherwise, it fetches the guild from the database, caches it, and then returns it.
        Args:
            guild_id (int): The ID of the guild to retrieve.
        Returns:
            PlayerGuild: The PlayerGuild object associated with the given guild ID.
        """

        if len(self.player_guilds) > 0 and (
            guild := self.player_guilds.get(str(guild_id))
        ):
            return guild

        guild = await PlayerGuild(self.db, guild=self.get_guild(guild_id)).fetch()

        self.player_guilds[str(guild_id)] = guild

        return guild

    async def get_busy_guilds(self) -> list[PlayerGuild]:
        """
        Asynchronously retrieves a list of busy guilds.
        A busy guild is defined as a guild that has an archive user.
        Returns:
            list[PlayerGuild]: A list of PlayerGuild objects representing the busy guilds.
        """
        query = PlayerGuild.guilds_table.select().where(
            PlayerGuild.guilds_table.c.archive_user.isnot(None)
        )

        rows = await self.query(query, QueryResultType.multiple)

        guilds = [
            await PlayerGuild.GuildSchema(
                self.db, guild=self.get_guild(row["id"])
            ).load(row)
            for row in rows
        ]

        return guilds

    async def get_character(self, char_id: int) -> PlayerCharacter:
        """
        Asynchronously retrieves a character from the database using the provided character ID.
        Args:
            char_id (int): The ID of the character to retrieve.
        Returns:
            PlayerCharacter: The character object corresponding to the provided ID.
        """
        query = PlayerCharacter.characters_table.select().where(
            PlayerCharacter.characters_table.c.id == char_id
        )

        row = await self.query(query)

        if row is None:
            return None

        character: PlayerCharacter = await PlayerCharacter.CharacterSchema(
            self.db, self.compendium
        ).load(row)

        return character

    async def get_adventure_from_role(self, role_id: int) -> Adventure:
        """
        Retrieve an adventure based on the given role ID.
        Args:
            role_id (int): The ID of the role to retrieve the adventure for.
        Returns:
            Adventure: The adventure associated with the given role ID, or None if no such adventure exists.
        """
        query = Adventure.adventures_table.select().where(
            sa.and_(
                Adventure.adventures_table.c.role_id == role_id,
                Adventure.adventures_table.c.end_ts == sa.null(),
            )
        )

        row = await self.query(query)

        if row is None:
            return None

        adventure = await Adventure.AdventureSchema(self).load(row)

        return adventure

    async def get_adventure_from_category(self, category_channel_id: int) -> Adventure:
        """
        Retrieve an adventure based on the given category channel ID.
        Args:
            category_channel_id (int): The ID of the category channel to retrieve the adventure from.
        Returns:
            Adventure: The adventure associated with the given category channel ID, or None if no adventure is found.
        """
        query = Adventure.adventures_table.select().where(
            sa.and_(
                Adventure.adventures_table.c.category_channel_id == category_channel_id,
                Adventure.adventures_table.c.end_ts == sa.null(),
            )
        )

        row = await self.query(query)

        if row is None:
            return None

        adventure = await Adventure.AdventureSchema(self).load(row)

        return adventure

    async def get_arena(self, channel_id: int) -> Arena:
        """
        Retrieve the Arena object associated with the given channel ID.
        Args:
            channel_id (int): The ID of the channel for which to retrieve the Arena.
        Returns:
            Arena: The Arena object associated with the given channel ID, or None if no such Arena exists.
        """
        query = Arena.arenas_table.select().where(
            sa.and_(
                Arena.arenas_table.c.channel_id == channel_id,
                Arena.arenas_table.c.end_ts == sa.null(),
            )
        )

        row = await self.query(query)

        if row is None:
            return None

        arena: Arena = await Arena.ArenaSchema(self).load(row)

        return arena

    async def get_player(
        self, player_id: int, guild_id: int = None, **kwargs
    ) -> Player:
        """
        Retrieve a player from the database based on player_id and guild_id.
        Args:
            player_id (int): The ID of the player to retrieve.
            guild_id (int): The ID of the guild the player belongs to.
            **kwargs: Additional keyword arguments.
                - inactive (bool): If True, load the player as inactive. Default is False.
                - lookup_only (bool): If True, only perform a lookup without creating a new player. Default is False.
                - ctx: The context for the command, used for interactive guild selection.
        Returns:
            Player: The retrieved or newly created Player object.
        Raises:
            G0T0Error: If no guild is selected or if unable to find the player.
        """

        inactive = kwargs.get("inactive", False)
        lookup_only = kwargs.get("lookup_only", False)
        ctx = kwargs.get("ctx")

        player = None

        if guild_id:
            query = Player.player_table.select().where(
                sa.and_(
                    Player.player_table.c.id == player_id,
                    Player.player_table.c.guild_id == guild_id,
                )
            )
        else:
            query = Player.player_table.select().where(
                Player.player_table.c.id == player_id
            )

        rows = await self.query(query, QueryResultType.multiple)

        if len(rows) == 0 and guild_id and not lookup_only:
            player = await Player(self, player_id, guild_id).upsert(inactive=inactive)

        elif len(rows) == 0 and lookup_only:
            return None

        elif len(rows) == 0 and not guild_id:
            if ctx:
                guilds = [g for g in self.guilds if g.get_member(player_id)]

                if len(guilds) == 1:
                    player = await Player(self, player_id, guilds[0].id).upsert(
                        inactive=inactive
                    )
                    return player
                elif len(guilds) > 1:
                    guild = await get_selection(
                        ctx,
                        guilds,
                        True,
                        True,
                        None,
                        False,
                        "Which guild is this command for?\n",
                    )

                    if guild:
                        player = await Player(self, player_id, guild.id).upsert(
                            inactive=inactive
                        )
                    else:
                        raise G0T0Error("No guild selected/found.")
                else:
                    raise G0T0Error("Unable to find player")
        else:
            if ctx:
                guilds = [g for g in self.guilds if g.get_member(player_id)]

                if len(guilds) == 1:
                    player = await Player(self, player_id, guilds[0].id).fetch()

                else:
                    choices = [g.name for g in guilds]
                    choice = await get_selection(
                        ctx,
                        choices,
                        True,
                        True,
                        None,
                        False,
                        "Which guild is this command for?\n",
                    )

                    if choice and (
                        guild := next((g for g in guilds if g.name == choice), None)
                    ):
                        player = await Player(self, player_id, guild.id).fetch(
                            inactive=inactive
                        )
            else:
                player = await Player(self, player_id, rows[0]["guild_id"]).fetch(
                    inactive=inactive
                )

        return player

    async def get_store_items(self) -> list[Store]:
        """
        Asynchronously retrieves store items from the database.
        This method acquires a database connection, executes a query to fetch store items,
        and loads the results into a list of Store objects using the StoreSchema.
        Returns:
            list[Store]: A list of Store objects representing the store items.
        """
        rows = await self.query(Store.store_table.select(), QueryResultType.multiple)

        store_items = [Store.StoreSchema().load(row) for row in rows]

        return store_items

    async def create_character(
        self,
        type: str,
        player: Player,
        new_character: PlayerCharacter,
        new_class: PlayerCharacterClass,
        **kwargs,
    ):
        """
        Asynchronously creates a new character for a player.
        Args:
            type (str): The type of character creation, either 'freeroll' or 'death'.
            player (Player): The player for whom the character is being created.
            new_character (PlayerCharacter): The new character to be created.
            new_class (PlayerCharacterClass): The class of the new character.
            **kwargs: Additional keyword arguments, including 'old_character' which is the player's previous character.
        Returns:
            PlayerCharacter: The newly created character.
        Raises:
            Exception: If there is an error during the character creation process.
        Notes:
            - If the type is 'freeroll', the new character is marked as a reroll and linked to the old character.
            - If the type is 'death', the player's handicap amount is reset.
            - The old character is marked as inactive and updated in the database.
            - The new character and its class are inserted into the database.
            - The time taken to create the character is logged.
        """

        start = timer()

        old_character: PlayerCharacter = kwargs.get("old_character")

        new_character.player_id = player.id
        new_character.guild_id = player.guild_id

        if type in ["freeroll", "death"]:
            new_character.reroll = True
            old_character.active = False

            if type == "freeroll":
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
        """
        Retrieve the Shatterpoint object for a given guild ID.
        Args:
            guild_id (int): The ID of the guild for which to retrieve the Shatterpoint.
        Returns:
            Shatterpoint: The Shatterpoint object associated with the given guild ID, or None if not found.
        """
        query = Shatterpoint.ref_gb_staging_table.select().where(
            Shatterpoint.ref_gb_staging_table.c.guild_id == guild_id
        )

        row = await self.query(query)

        if row is None:
            return None

        shatterpoint: Shatterpoint = await Shatterpoint.ShatterPointSchema(self).load(
            row
        )

        return shatterpoint

    async def get_busy_shatterpoints(self) -> list[Shatterpoint]:
        query = Shatterpoint.ref_gb_staging_table.select().where(
            Shatterpoint.ref_gb_staging_table.c.busy_member.isnot(None)
        )

        shatterpoints = [
            await Shatterpoint.ShatterPointSchema(self).load(row)
            for row in await self.query(query, QueryResultType.multiple)
        ]

        return shatterpoints

    async def get_dashboard_from_category(self, category_id: int) -> RefDashboard:
        """
        Retrieve a dashboard from a specific category.
        Args:
            category_id (int): The ID of the category to retrieve the dashboard from.
        Returns:
            RefDashboard: The dashboard associated with the given category ID, or None if no dashboard is found.
        """

        query = RefDashboard.ref_dashboard_table.select().where(
            RefDashboard.ref_dashboard_table.c.category_channel_id == category_id
        )

        row = await self.query(query)

        if row is None:
            return None

        d = RefDashboard.RefDashboardSchema(self).load(row)

        return d

    async def get_dashboard_from_message(self, message_id: int) -> RefDashboard:
        """
        Retrieve a dashboard reference from a message ID.
        Args:
            message_id (int): The ID of the message to retrieve the dashboard from.
        Returns:
            RefDashboard: The dashboard reference associated with the given message ID.
            None: If no dashboard is found for the given message ID.
        """
        query = RefDashboard.ref_dashboard_table.select().where(
            RefDashboard.ref_dashboard_table.c.post_id == message_id
        )

        row = await self.query(query)

        if row is None:
            return None

        d = RefDashboard.RefDashboardSchema(self).load(row)

        return d

    async def log(
        self,
        ctx: discord.ApplicationContext | discord.Interaction | None,
        player: discord.Member | discord.ClientUser | Player,
        author: discord.Member | discord.ClientUser | Player,
        activity: Activity | str,
        **kwargs,
    ) -> DBLog:
        """
        Logs an activity for a player and updates the database accordingly.
        Args:
            ctx (ApplicationContext | Interaction | None): The context of the command or interaction.
            player (Member | ClientUser | Player): The player involved in the activity.
            author (Member | ClientUser | Player): The author of the log entry.
            activity (Activity | str): The activity being logged.
            **kwargs: Additional keyword arguments for the log entry.
        Keyword Args:
            cc (int): The amount of CC (currency) involved in the activity.
            credits (int): The amount of credits involved in the activity.
            renown (int): The amount of renown involved in the activity.
            notes (str): Additional notes for the log entry.
            character (PlayerCharacter): The character involved in the activity.
            ignore_handicap (bool): Whether to ignore handicap adjustments.
            faction (Faction): The faction involved in the activity.
            adventure (Adventure): The adventure involved in the activity.
            silent (bool): Whether to suppress output messages.
            respond (bool): Whether to respond to the context.
            show_values (bool): Whether to show values in the output.
        Returns:
            DBLog: The log entry created.
        Raises:
            G0T0Error: If the guild ID cannot be determined or required parameters are missing.
            TransactionError: If the player cannot afford the transaction.
        """
        guild_id = (
            ctx.guild.id
            if ctx
            else (
                player.guild.id
                if player.guild
                else author.guild.id if author.guild else None
            )
        )

        if not guild_id:
            raise G0T0Error("I have no idea what guild this log is for")

        player = (
            player
            if isinstance(player, Player)
            else await self.get_player(player.id, guild_id)
        )
        author = (
            author
            if isinstance(author, Player)
            else await self.get_player(author.id, guild_id)
        )
        activity = (
            activity
            if isinstance(activity, Activity)
            else self.compendium.get_activity(activity)
        )

        cc = kwargs.get("cc")
        convertedCC = None
        credits = kwargs.get("credits", 0)
        renown = kwargs.get("renown", 0)

        notes = kwargs.get("notes")
        character: PlayerCharacter = kwargs.get("character")
        ignore_handicap = kwargs.get("ignore_handicap", False)

        faction: Faction = kwargs.get("faction")
        adventure: Adventure = kwargs.get("adventure")

        silent = kwargs.get("silent", False)
        respond = kwargs.get("respond", True)
        show_values = kwargs.get("show_values", False)

        # Calculations
        reward_cc = cc if cc else activity.cc if activity.cc else 0
        if activity.diversion and (player.div_cc + reward_cc > player.guild.div_limit):
            reward_cc = max(0, player.guild.div_limit - player.div_cc)

        handicap_adjustment = (
            0
            if ignore_handicap or player.guild.handicap_cc <= player.handicap_amount
            else min(reward_cc, player.guild.handicap_cc - player.handicap_amount)
        )
        total_cc = reward_cc + handicap_adjustment

        # Verification
        if player.cc + total_cc < 0:
            raise TransactionError(
                f"{player.member.mention} cannot afford the {total_cc:,} CC cost."
            )
        elif (credits != 0 or renown != 0) and not character:
            raise G0T0Error(
                "Need to specify a character to do this type of transaction"
            )
        elif renown > 0 and not faction:
            raise G0T0Error("No faction specified")
        elif character and credits < 0 and character.credits + credits < 0:
            rate: CodeConversion = self.compendium.get_object(
                CodeConversion, character.level
            )
            convertedCC = ceil((abs(credits) - character.credits) / rate.value)
            if player.cc < convertedCC:
                raise TransactionError(
                    f"{character.name} cannot afford the {credits:,} credit cost or to convert the {convertedCC:,} needed."
                )

            await self.log(
                ctx,
                player,
                author,
                "CONVERSION",
                cc=-convertedCC,
                character=character,
                credits=convertedCC * rate.value,
                notes=notes,
                ignore_handicap=True,
                respond=False,
                show_values=show_values,
            )

        # Updates
        if character:
            character.credits += credits

        player.cc += total_cc
        player.handicap_amount += handicap_adjustment
        player.div_cc += reward_cc if activity.diversion else 0

        if faction:
            await character.update_renown(faction, renown)

        # Log Entry
        log_entry = DBLog(
            self,
            guild_id=player.guild.id,
            author=author,
            player_id=player.id,
            activity=activity,
            notes=notes,
            character_id=character.id if character else None,
            cc=total_cc,
            credits=credits,
            renown=renown,
            adventure_id=adventure.id if adventure else None,
            faction=faction,
        )

        await player.upsert()

        if character:
            await character.upsert()

        log_entry = await log_entry.upsert()

        # Author Rewards
        if author.guild.reward_threshold and activity.value != "LOG_REWARD":
            author.points += activity.points

            if author.points >= author.guild.reward_threshold:
                qty = max(1, author.points // author.guild.reward_threshold)
                act: Activity = self.compendium.get_activity("LOG_REWARD")
                reward_log = await self.log(
                    ctx,
                    author,
                    self.user,
                    act,
                    cc=act.cc * qty,
                    notes=f"Rewards for {author.guild.reward_threshold*qty} points",
                    silent=True,
                )

                author.points = max(
                    0, author.points - (author.guild.reward_threshold * qty)
                )

                if author.guild.staff_channel:
                    await author.guild.staff_channel.send(
                        embed=LogEmbed(reward_log, True)
                    )

                await author.upsert()

        # Send output
        if silent is False and ctx:
            embed = LogEmbed(log_entry, show_values)
            if respond:
                await ctx.respond(embed=embed)
            else:
                await ctx.channel.send(embed=embed)

        return log_entry

    async def get_log(self, log_id: int) -> DBLog:
        """
        Retrieve a log entry from the database by its ID.
        Args:
            log_id (int): The ID of the log entry to retrieve.
        Returns:
            DBLog: The log entry corresponding to the given ID, or None if no entry is found.
        """
        query = DBLog.log_table.select().where(DBLog.log_table.c.id == log_id)

        row = await self.query(query)

        if not row:
            return None

        log_entry = await DBLog.LogSchema(self).load(row)

        return log_entry

    async def get_n_player_logs(self, player: Player, n: int = 5) -> list[DBLog]:
        """
        Retrieve the most recent logs for a given player.
        Args:
            player (Player): The player whose logs are to be retrieved.
            n (int, optional): The number of logs to retrieve. Defaults to 5.
        Returns:
            list[DBLog]: A list of the most recent logs for the given player.
        """
        query = (
            DBLog.log_table.select()
            .where(
                sa.and_(
                    DBLog.log_table.c.player_id == player.id,
                    DBLog.log_table.c.guild_id == player.guild.id,
                )
            )
            .order_by(DBLog.log_table.c.id.desc())
            .limit(n)
        )

        rows = await self.query(query, QueryResultType.multiple)

        if not rows:
            return None

        logs = [await DBLog.LogSchema(self).load(row) for row in rows]

        return logs

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
                    DBLog.log_table.c.player_id == player.player_id,
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

            activity_log = await self.log(
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
