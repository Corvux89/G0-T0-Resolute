import logging
from asyncio import CancelledError, create_task, get_event_loop
from math import ceil
from signal import SIGINT, SIGTERM
from timeit import default_timer as timer

from aiopg.sa import Engine, SAConnection, create_engine
from discord import ApplicationContext, ClientUser, Interaction, Member
from discord.ext import commands
from quart import Quart
from sqlalchemy.schema import CreateTable

from Resolute.compendium import Compendium
from Resolute.constants import DB_URL, PORT
from Resolute.helpers.general_helpers import get_selection
from Resolute.models import metadata
from Resolute.models.categories.categories import Activity, CodeConversion, Faction
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.adventures import (
    Adventure, AdventureSchema, get_adventure_by_category_channel_query,
    get_adventure_by_role_query)
from Resolute.models.objects.arenas import (Arena, ArenaSchema,
                                            get_arena_by_channel_query)
from Resolute.models.objects.characters import (CharacterSchema,
                                                PlayerCharacter,
                                                PlayerCharacterClass,
                                                get_character_from_id, upsert_character_query)
from Resolute.models.objects.dashboards import (
    RefDashboard, RefDashboardSchema, get_dashboard_by_category_channel_query,
    get_dashboard_by_post_id)
from Resolute.models.objects.exceptions import G0T0Error, TransactionError
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog, LogSchema, upsert_log
from Resolute.models.objects.players import (Player, PlayerSchema,
                                             get_player_query,
                                             upsert_player_query)
from Resolute.models.objects.shatterpoint import (Shatterpoint,
                                                  ShatterPointSchema,
                                                  get_shatterpoint_query)
from Resolute.models.objects.store import (Store, StoreSchema,
                                           get_store_items_query)

log = logging.getLogger(__name__)   


async def create_tables(conn: SAConnection):
    for table in metadata.sorted_tables:
        await conn.execute(CreateTable(table, if_not_exists=True))


class G0T0Bot(commands.Bot):
    """
    G0T0Bot is a custom Discord bot that extends the functionality of discord.ext.commands.Bot.
    It integrates with a database, a web application, and provides various methods to interact with game-related data.
    Attributes:
        db (Engine): The database engine.
        compendium (Compendium): The compendium of game data.
        web_app (Quart): The web application instance.
        player_guilds (dict): A dictionary to store player guilds.
    Methods:
        __init__(**options): Initializes the bot with the given options.
        on_ready(): Called when the bot is ready. Initializes the database and web server.
        close(): Shuts down the bot and web server.
        run(*args, **kwargs): Runs the bot and sets up signal handlers for graceful shutdown.
        get_player_guild(guild_id: int) -> PlayerGuild: Retrieves the player guild for the given guild ID.
        get_guilds_with_reset(day: int, hour: int) -> list[PlayerGuild]: Retrieves guilds with a reset scheduled at the given day and hour.
        get_character(char_id: int) -> PlayerCharacter: Retrieves the character for the given character ID.
        get_adventure_from_role(role_id: int) -> Adventure: Retrieves the adventure associated with the given role ID.
        get_adventure_from_category(category_channel_id: int) -> Adventure: Retrieves the adventure associated with the given category channel ID.
        get_arena(channel_id: int) -> Arena: Retrieves the arena associated with the given channel ID.
        get_player(player_id: int, guild_id: int, **kwargs) -> Player: Retrieves the player for the given player ID and guild ID.
        get_store_items() -> list[Store]: Retrieves the list of store items.
        create_character(type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs): Creates a new character for the player.
        get_shatterpoint(guild_id: int) -> Shatterpoint: Retrieves the shatterpoint for the given guild ID.
        get_dashboard_from_category(category_id: int) -> RefDashboard: Retrieves the dashboard associated with the given category ID.
        get_dashboard_from_message(message_id: int) -> RefDashboard: Retrieves the dashboard associated with the given message ID.
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
        loop = get_event_loop()
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
        if hasattr(self, 'web_task'):
            self.web_task.cancel()  
            try:
                await self.web_task
            except CancelledError:
                pass

        if hasattr(self, 'db'):
            self.db.close()  
            await self.db.wait_closed()

        await super().close()  

    def run(self, *args, **kwargs):
        for sig in (SIGINT, SIGTERM):
            try:
                self.loop.add_signal_handler(sig, lambda: create_task(self.close()))
            except (NotImplementedError, RuntimeError):
                pass
        super().run(*args, **kwargs)

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

        if len(self.player_guilds) > 0 and (guild:= self.player_guilds.get(str(guild_id))):
            return guild

        guild = await PlayerGuild(self.db, guild=self.get_guild(guild_id)).fetch()

        self.player_guilds[str(guild_id)] = guild

        return guild
    
    async def get_character(self, char_id: int) -> PlayerCharacter:
        """
        Asynchronously retrieves a character from the database using the provided character ID.
        Args:
            char_id (int): The ID of the character to retrieve.
        Returns:
            PlayerCharacter: The character object corresponding to the provided ID.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_character_from_id(char_id))
            row = await results.first()

        character: PlayerCharacter = await CharacterSchema(self.db, self.compendium).load(row)

        return character
    
    async def get_adventure_from_role(self, role_id: int) -> Adventure:
        """
        Retrieve an adventure based on the given role ID.
        Args:
            role_id (int): The ID of the role to retrieve the adventure for.
        Returns:
            Adventure: The adventure associated with the given role ID, or None if no such adventure exists.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_adventure_by_role_query(role_id))
            row = await results.first()

        if row is None:
            return None
        
        adventure = await AdventureSchema(self).load(row)

        return adventure
        
    async def get_adventure_from_category(self, category_channel_id: int) -> Adventure:
        """
        Retrieve an adventure based on the given category channel ID.
        Args:
            category_channel_id (int): The ID of the category channel to retrieve the adventure from.
        Returns:
            Adventure: The adventure associated with the given category channel ID, or None if no adventure is found.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_adventure_by_category_channel_query(category_channel_id))
            row = await results.first()

        if row is None:
            return None

        adventure = await AdventureSchema(self).load(row)

        return adventure
    
    async def get_arena(self, channel_id: int) -> Arena:
        """
        Retrieve the Arena object associated with the given channel ID.
        Args:
            channel_id (int): The ID of the channel for which to retrieve the Arena.
        Returns:
            Arena: The Arena object associated with the given channel ID, or None if no such Arena exists.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_arena_by_channel_query(channel_id))
            row = await results.first()

        if row is None:
            return None
        
        arena: Arena = await ArenaSchema(self).load(row)

        return arena
    
    async def get_player(self, player_id: int, guild_id: int, **kwargs) -> Player:
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
        """
        Asynchronously retrieves store items from the database.
        This method acquires a database connection, executes a query to fetch store items,
        and loads the results into a list of Store objects using the StoreSchema.
        Returns:
            list[Store]: A list of Store objects representing the store items.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_store_items_query())
            rows = await results.fetchall()

        store_items = [StoreSchema().load(row) for row in rows]

        return store_items
    
    async def create_character(self, type: str, player: Player, new_character: PlayerCharacter, new_class: PlayerCharacterClass, **kwargs):
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
        """
        Retrieve the Shatterpoint object for a given guild ID.
        Args:
            guild_id (int): The ID of the guild for which to retrieve the Shatterpoint.
        Returns:
            Shatterpoint: The Shatterpoint object associated with the given guild ID, or None if not found.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_shatterpoint_query(guild_id))
            row = await results.first()
        
        if row is None:
            return None
        
        shatterpoint: Shatterpoint = await ShatterPointSchema(self).load(row)

        return shatterpoint

    async def get_dashboard_from_category(self, category_id: int) -> RefDashboard:
        """
        Retrieve a dashboard from a specific category.
        Args:
            category_id (int): The ID of the category to retrieve the dashboard from.
        Returns:
            RefDashboard: The dashboard associated with the given category ID, or None if no dashboard is found.
        """

        async with self.db.acquire() as conn:
            results = await conn.execute(get_dashboard_by_category_channel_query(category_id))
            row = await results.first()

        if row is None:
            return None
        
        d = RefDashboardSchema(self).load(row)

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

        async with self.db.acquire() as conn:
            results = await conn.execute(get_dashboard_by_post_id(message_id))
            row = await results.first() 

        if row is None:
            return None
        
        d = RefDashboardSchema(self).load(row)

        return d
    
    async def log(self, ctx: ApplicationContext|Interaction|None, player: Member|ClientUser|Player, author: Member|ClientUser|Player, activity: Activity|str, **kwargs) -> DBLog:
        guild_id = ctx.guild.id if ctx else player.guild.id if player.guild else author.guild.id if author.guild else None

        if not guild_id:
            raise G0T0Error("I have no idea what guild this log is for")
        
        player = player if isinstance(player, Player) else await self.get_player(player.id, guild_id)
        author = author if isinstance(author, Player) else await self.get_player(author.id, guild_id)
        activity = activity if isinstance(activity, Activity) else self.compendium.get_activity(activity)

        cc = kwargs.get('cc')
        convertedCC = None
        credits = kwargs.get('credits', 0)
        renown = kwargs.get('renown', 0)

        notes = kwargs.get('notes')
        character: PlayerCharacter = kwargs.get('character')
        ignore_handicap = kwargs.get('ignore_handicap', False)

        faction: Faction = kwargs.get('faction')
        adventure: Adventure = kwargs.get('adventure')

        silent = kwargs.get('silent', False)
        respond = kwargs.get('respond', True)
        show_values = kwargs.get('show_values', False)

        # Calculations
        reward_cc = cc if cc else activity.cc if activity.cc else 0
        if activity.diversion and (player.div_cc + reward_cc > player.guild.div_limit):
            reward_cc = max(0, player.guild.div_limit - player.div_cc)

        handicap_adjustment = 0 if ignore_handicap or player.guild.handicap_cc <= player.handicap_amount else min(reward_cc, player.guild.handicap_cc - player.handicap_amount)
        total_cc = reward_cc+handicap_adjustment

        # Verification
        if player.cc + total_cc < 0:
            raise TransactionError(f"{player.member.mention} cannot afford the {total_cc:,} CC cost.")
        elif (credits != 0 or renown != 0) and not character:
            raise G0T0Error("Need to specify a character to do this type of transaction")
        elif renown > 0 and not faction:
            raise G0T0Error("No faction specified")
        elif character and credits < 0 and character.credits + credits < 0:
            rate: CodeConversion = self.compendium.get_object(CodeConversion, character.level)
            convertedCC = ceil((abs(credits) - character.credits) / rate.value)
            if player.cc < convertedCC:
                raise TransactionError(f"{character.name} cannot afford the {credits:,} credit cost or to convert the {convertedCC:,} needed.")
            
            await self.log(ctx, player, author, "CONVERSION",
                            cc=-convertedCC,
                            character=character,
                            credits=convertedCC*rate.value,
                            notes=notes,
                            ignore_handicap=True,
                            respond=False,
                            show_values=show_values)

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
            guild_id=player.guild.id,
            author=author.id,
            player_id=player.id,
            activity=activity,
            notes=notes,
            character_id=character.id if character else None,
            cc=total_cc,
            credits=credits,
            renown=renown,
            adventure_id=adventure.id if adventure else None,
            faction=faction
        )

        async with self.db.acquire() as conn:
            results = await conn.execute(upsert_log(log_entry))
            row = await results.first()

            await conn.execute(upsert_player_query(player))

            if character:
                await conn.execute(upsert_character_query(character))

        log_entry = LogSchema(self.compendium).load(row)

        # Author Rewards
        if author.guild.reward_threshold and activity.value != "LOG_REWARD":
            author.points += activity.points

            if author.points >= author.guild.reward_threshold:
                qty = max(1, author.points // author.guild.reward_threshold)
                act: Activity = self.compendium.get_activity("LOG_REWARD")
                reward_log = await self.log(ctx, author, self.user, act,
                                            cc=act.cc*qty,
                                            notes=f"Rewards for {author.guild.reward_threshold*qty} points",
                                            silent=True)
                
                author.points = max(0, author.points - (author.guild.reward_threshold * qty))

                if author.guild.staff_channel:
                    await author.guild.staff_channel.send(embed=LogEmbed(reward_log, self.user, author.member, None, True))

                async with self.db.acquire() as conn:
                    await conn.execute(upsert_player_query(author))

        # Send output
        if silent is False and ctx:
            embed = LogEmbed(log_entry, author.member, player.member, character, show_values)
            if respond:
                await ctx.respond(embed=embed)
            else:
                await ctx.channel.send(embed=embed)

        return log_entry
                    
            
        

            

        
           




