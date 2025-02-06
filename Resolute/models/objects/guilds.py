import calendar
from datetime import datetime, timedelta, timezone
from math import floor

import aiopg.sa
import sqlalchemy as sa
from discord import Guild, Role, TextChannel
from marshmallow import Schema, fields, post_load
from sqlalchemy import (BOOLEAN, TIMESTAMP, BigInteger, Column, Integer,
                        String, and_)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import FromClause

from Resolute.compendium import Compendium
from Resolute.models import metadata
from Resolute.models.objects.characters import (CharacterSchema,
                                                get_guild_characters_query)
from Resolute.models.objects.dashboards import (RefDashboard,
                                                RefDashboardSchema,
                                                get_dashboards)
from Resolute.models.objects.npc import NPC, NPCSchema, get_guild_npcs_query
from Resolute.models.objects.ref_objects import (
    RefServerCalendar, RefServerCalendarSchema, RefWeeklyStipend,
    RefWeeklyStipendSchema, get_guild_weekly_stipends_query,
    get_server_calendar)


class PlayerGuild(object):
    """
    Represents a player's guild with various attributes and methods to manage the guild.
    Attributes:
        _db (aiopg.sa.Engine): The database engine.
        id (int): The guild ID.
        max_level (int): The maximum level of the guild.
        weeks (int): The number of weeks the guild has been active.
        _reset_day (int): The day of the week the guild resets.
        _reset_hour (int): The hour of the day the guild resets.
        _last_reset (datetime): The last reset time of the guild.
        greeting (str): The greeting message of the guild.
        handicap_cc (int): The handicap CC value.
        max_characters (int): The maximum number of characters in the guild.
        div_limit (int): The division limit.
        reset_message (str): The reset message.
        weekly_announcement (list[str]): The weekly announcement messages.
        server_date (int): The server date.
        epoch_notation (str): The epoch notation.
        first_character_message (str): The first character message.
        ping_announcement (bool): Whether to ping announcements.
        reward_threshold (int): The reward threshold.
        calendar (list[RefServerCalendar]): The server calendar.
        guild (Guild): The guild object.
        npcs (list[NPC]): The list of NPCs in the guild.
        stipends (list[RefWeeklyStipend]): The list of weekly stipends.
        entry_role (Role): The entry role.
        member_role (Role): The member role.
        tier_2_role (Role): The tier 2 role.
        tier_3_role (Role): The tier 3 role.
        tier_4_role (Role): The tier 4 role.
        tier_5_role (Role): The tier 5 role.
        tier_6_role (Role): The tier 6 role.
        admin_role (Role): The admin role.
        staff_role (Role): The staff role.
        bot_role (Role): The bot role.
        quest_role (Role): The quest role.
        application_channel (TextChannel): The application channel.
        market_channel (TextChannel): The market channel.
        announcement_channel (TextChannel): The announcement channel.
        staff_channel (TextChannel): The staff channel.
        help_channel (TextChannel): The help channel.
        arena_board_channel (TextChannel): The arena board channel.
        exit_channel (TextChannel): The exit channel.
        entrance_channel (TextChannel): The entrance channel.
        activity_points_channel (TextChannel): The activity points channel.
        rp_post_channel (TextChannel): The RP post channel.
        dev_channels (list[TextChannel]): The list of development channels.
    Properties:
        get_reset_day: Returns the reset day of the week as a string.
        get_next_reset: Returns the next reset time as a timestamp.
        get_last_reset: Returns the last reset time as a timestamp.
        formatted_server_date: Returns the formatted server date.
        server_year: Returns the server year.
        server_month: Returns the server month.
        server_day: Returns the server day.
        days_in_server_year: Returns the number of days in a server year.
    Methods:
        get_internal_date(day: int, month: int, year: int) -> int:
            Returns the internal date based on the given day, month, and year.
        is_dev_channel(channel: TextChannel) -> bool:
            Checks if the given channel is a development channel.
        async upsert():
            Inserts or updates the guild in the database.
        async fetch():
            Fetches the guild from the database.
        async get_all_characters(compendium: Compendium) -> list:
            Returns a list of all characters in the guild.
        async get_dashboards(bot) -> list[RefDashboard]:
            Returns a list of dashboards for the guild.
    """

    def __init__(self, db: aiopg.sa.Engine, **kwargs):
        self._db = db

        self.id: int = kwargs.get('id')
        self.max_level: int = kwargs.get('max_level', 3)
        self.weeks: int = kwargs.get('weeks', 0)
        self._reset_day: int = kwargs.get('reset_day')
        self._reset_hour: int = kwargs.get('reset_hour')
        self._last_reset: datetime = kwargs.get('last_reset', datetime.now(timezone.utc))
        self.greeting: str = kwargs.get('greeting')
        self.handicap_cc: int = kwargs.get('handicap_cc', 0)
        self.max_characters: int = kwargs.get('max_characters', 1)
        self.div_limit: int = kwargs.get('div_limit', 10)
        self.reset_message: str = kwargs.get('reset_message')
        self.weekly_announcement: list[str] = kwargs.get('weekly_announcement', [])
        self.server_date: int = kwargs.get('server_date')
        self.epoch_notation: str = kwargs.get('epoch_notation')
        self.first_character_message: str = kwargs.get('first_character_message')
        self.ping_announcement: bool = kwargs.get('ping_announcement', False)
        self.reward_threshold: int = kwargs.get('reward_threshold')

        # Virtual attributes
        self.calendar: list[RefServerCalendar] = None
        self.guild: Guild = kwargs.get('guild')
        self.npcs: list[NPC] = []
        self.stipends: list[RefWeeklyStipend] = []

        # Roles
        self.entry_role: Role = kwargs.get('entry_role')
        self.member_role: Role = kwargs.get('member_role')
        self.tier_2_role: Role = kwargs.get('tier_2_role')
        self.tier_3_role: Role = kwargs.get('tier_3_role')
        self.tier_4_role: Role = kwargs.get('tier_4_role')
        self.tier_5_role: Role = kwargs.get('tier_5_role')
        self.tier_6_role: Role = kwargs.get('tier_6_role')
        self.admin_role: Role = kwargs.get('admin_role')
        self.staff_role: Role = kwargs.get('staff_role')
        self.bot_role: Role = kwargs.get('bot_role')
        self.quest_role: Role = kwargs.get('quest_role')
        
        # Channels
        self.application_channel: TextChannel = kwargs.get('application_channel')
        self.market_channel: TextChannel = kwargs.get('market_channel')
        self.announcement_channel: TextChannel = kwargs.get('announcement_channel')
        self.staff_channel: TextChannel = kwargs.get('staff_channel')
        self.help_channel: TextChannel = kwargs.get('help_channel')
        self.arena_board_channel: TextChannel = kwargs.get('arena_board_channel')
        self.exit_channel: TextChannel = kwargs.get('exit_channel')
        self.entrance_channel: TextChannel = kwargs.get('entrance_channel')
        self.activity_points_channel: TextChannel = kwargs.get('activity_points_channel')
        self.rp_post_channel: TextChannel = kwargs.get('rp_post_channel')
        self.dev_channels: list[TextChannel] = kwargs.get('dev_channels', [])


        if not self.id and self.guild:
            self.id = self.guild.id


    @property
    def get_reset_day(self):
        weekDays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        return weekDays[self._reset_day]

    @property
    def get_next_reset(self):
        if self._reset_hour is not None and self._reset_day is not None:
            now = datetime.now(timezone.utc)
            day_offset = (self._reset_day - now.weekday() + 7) % 7
            run_date = now + timedelta(days=day_offset)

            run_date = datetime(run_date.year, run_date.month, run_date.day, run_date.hour, 0, 0, tzinfo=timezone.utc)

            if (self._reset_hour < now.hour and run_date <= now) \
                    or (run_date < (self._last_reset + timedelta(days=6))):
                run_date += timedelta(days=7)

            dt = calendar.timegm(
                datetime(run_date.year, run_date.month, run_date.day, self._reset_hour, 0, 0).utctimetuple())

            return dt
        else:
            return None

    @property
    def get_last_reset(self):
        return calendar.timegm(self._last_reset.utctimetuple())
    
    @property
    def formatted_server_date(self):
        return f"{f'{self.epoch_notation}::' if self.epoch_notation else ''}{self.server_year:02}:{self.server_month.display_name}:{self.server_day:02}"
    
    @property
    def server_year(self):
        if not self.calendar or self.server_date is None:
            return None
        return floor(self.server_date / self.days_in_server_year)
    
    @property
    def server_month(self) -> RefServerCalendar:
        if not self.calendar or self.server_date is None:
            return None
        days_in_year = self.server_date % self.days_in_server_year
        return next((month for month in self.calendar if month.day_start <= days_in_year <= month.day_end), None)
        
    
    @property 
    def server_day(self):        
        month = self.server_month

        if not month:
            return None

        days_in_year = self.server_date % self.days_in_server_year

        return days_in_year - month.day_start + 1
    
    @property
    def days_in_server_year(self):
        if not self.calendar:
            return None
        return max(month.day_end for month in self.calendar)
    
    def get_internal_date(self, day: int, month: int, year: int) -> int:
        if not self.calendar:
            return None
        
        epoch_time = (year * self.days_in_server_year) + (self.calendar[month-1].day_start+day-1)

        return epoch_time
    
    def is_dev_channel(self, channel: TextChannel):
        if not self.dev_channels:
            return False
        return channel in self.dev_channels
    
    # Add event listener for this
    async def upsert(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(upsert_guild(self))
            row = await results.first()

        g = await GuildSchema(self._db, self.guild).load(row)

        return g

    async def fetch(self):
        async with self._db.acquire() as conn:
            results = await conn.execute(get_guild_from_id(self.id))
            guild_row = await results.first()

            if guild_row is None:
                guild = PlayerGuild(self._db, id=self.id)
                guild: PlayerGuild = await guild.upsert()
            else: 
                guild = await GuildSchema(self._db, guild=self.guild).load(guild_row)

        return guild
    
    async def get_all_characters(self, compendium: Compendium):
        async with self._db.acquire() as conn:
            results = await conn.execute(get_guild_characters_query(self.id))
            rows = await results.fetchall()

        character_list = [await CharacterSchema(self._db, compendium).load(row) for row in rows]

        return character_list
    
    async def get_dashboards(self, bot) -> list[RefDashboard]:
        dashboards = []

        async with self._db.acquire() as conn:
            async for row in conn.execute(get_dashboards()):
                dashboard: RefDashboard = RefDashboardSchema(bot).load(row)
                if dashboard.channel.guild.id == self.id:
                    dashboards.append(dashboard)

        return dashboards

guilds_table = sa.Table(
    "guilds",
    metadata,
    Column("id", BigInteger, primary_key=True, nullable=False),
    Column("max_level", Integer, nullable=False, default=3),
    Column("weeks", Integer, nullable=False, default=0),
    Column("reset_day", Integer, nullable=True),
    Column("reset_hour", Integer, nullable=True),
    Column("last_reset", TIMESTAMP(timezone=timezone.utc)),
    Column("greeting", String, nullable=True),
    Column("handicap_cc", Integer, nullable=True),
    Column("max_characters", Integer, nullable=False),
    Column("div_limit", Integer, nullable=False),
    Column("reset_message", String, nullable=True),
    Column("weekly_announcement", sa.ARRAY(String), nullable=True),
    Column("server_date", Integer, nullable=True),
    Column("epoch_notation", String, nullable=True),
    Column("first_character_message", String, nullable=True),
    Column("ping_announcement", BOOLEAN, default=False, nullable=False),
    Column("reward_threshold", Integer, nullable=True),
    Column("entry_role", BigInteger, nullable=True),
    Column("member_role", BigInteger, nullable=True),
    Column("tier_2_role", BigInteger, nullable=True),
    Column("tier_3_role", BigInteger, nullable=True),
    Column("tier_4_role", BigInteger, nullable=True),
    Column("tier_5_role", BigInteger, nullable=True),
    Column("tier_6_role", BigInteger, nullable=True),
    Column("admin_role", BigInteger, nullable=True),
    Column("staff_role", BigInteger, nullable=True),
    Column("bot_role", BigInteger, nullable=True),
    Column("quest_role", BigInteger, nullable=True),
    Column("application_channel", BigInteger, nullable=True),
    Column("market_channel", BigInteger, nullable=True),
    Column("announcement_channel", BigInteger, nullable=True),
    Column("staff_channel", BigInteger, nullable=True),
    Column("help_channel", BigInteger, nullable=True),
    Column("arena_board_channel", BigInteger, nullable=True),
    Column("exit_channel", BigInteger, nullable=True),
    Column("entrance_channel", BigInteger, nullable=True),
    Column("activity_points_channel", BigInteger, nullable=True),
    Column("rp_post_channel", BigInteger, nullable=True),
    Column("dev_channels", sa.ARRAY(BigInteger), nullable=True, default=[])
)

class GuildSchema(Schema):
    _db: aiopg.sa.Engine
    _guild: Guild

    id = fields.Integer(required=True)
    max_level = fields.Integer()
    weeks = fields.Integer()
    reset_day = fields.Integer(allow_none=True)
    reset_hour = fields.Integer(allow_none=True)
    last_reset = fields.Method(None, "load_timestamp")
    greeting = fields.String(allow_none=True)
    handicap_cc = fields.Integer(allow_none=True)
    max_characters = fields.Integer(allow_none=False)
    div_limit = fields.Integer(allow_none=False)
    reset_message = fields.String(allow_none=True)
    weekly_announcement = fields.List(fields.String, required=False)
    server_date = fields.Integer(allow_none=True)
    epoch_notation = fields.String(allow_none=True)
    first_character_message = fields.String(allow_none=True)
    ping_announcement = fields.Boolean(allow_none=False)
    reward_threshold = fields.Integer(allow_none=True)
    entry_role = fields.Method(None, "load_role", allow_none=True)
    member_role = fields.Method(None, "load_role", allow_none=True)
    tier_2_role = fields.Method(None, "load_role", allow_none=True)
    tier_3_role = fields.Method(None, "load_role", allow_none=True)
    tier_4_role = fields.Method(None, "load_role", allow_none=True)
    tier_5_role = fields.Method(None, "load_role", allow_none=True)
    tier_6_role = fields.Method(None, "load_role", allow_none=True)
    admin_role = fields.Method(None, "load_role", allow_none=True)
    staff_role = fields.Method(None, "load_role", allow_none=True)
    bot_role = fields.Method(None, "load_role", allow_none=True)
    quest_role = fields.Method(None, "load_role", allow_none=True)
    application_channel = fields.Method(None, "load_channel", allow_none=True)
    market_channel = fields.Method(None, "load_channel", allow_none=True)
    announcement_channel = fields.Method(None, "load_channel", allow_none=True)
    staff_channel = fields.Method(None, "load_channel", allow_none=True)
    help_channel = fields.Method(None, "load_channel", allow_none=True)
    arena_board_channel = fields.Method(None, "load_channel", allow_none=True)
    exit_channel = fields.Method(None, "load_channel", allow_none=True)
    entrance_channel = fields.Method(None, "load_channel", allow_none=True)
    activity_points_channel = fields.Method(None, "load_channel", allow_none=True)
    rp_post_channel = fields.Method(None, "load_channel", allow_none=True)
    dev_channels = fields.Method(None, "load_channels", allow_none=True)

    def __init__(self, db: aiopg.sa.Engine, guild: Guild, **kwargs):
        super().__init__(**kwargs)
        self._db = db
        self._guild = guild

    @post_load
    async def make_guild(self, data, **kwargs):
        guild = PlayerGuild(self._db, **data)
        guild.guild = self._guild
        await self.load_calendar(guild)
        await self.load_npcs(guild)
        await self.load_weekly_stipends(guild)
        return guild

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    
    def load_role(self, value):
        return self._guild.get_role(value)
    
    def load_channel(self, value):
        return self._guild.get_channel(value)

    def load_channels(self, value):
        channels = []
        for c in value:
            channels.append(self._guild.get_channel(c))

        return channels
    
    async def load_calendar(self, guild: PlayerGuild):
        async with self._db.acquire() as conn:
            results = await conn.execute(get_server_calendar(guild.id))
            rows = await results.fetchall()

        guild.calendar = [RefServerCalendarSchema().load(row) for row in rows]

    
    async def load_npcs(self, guild: PlayerGuild):
        async with self._db.acquire() as conn:
            results = await conn.execute(get_guild_npcs_query(guild.id))
            rows = await results.fetchall()
        guild.npcs = [NPCSchema(self._db).load(row) for row in rows]
    
    async def load_weekly_stipends(self, guild: PlayerGuild):
        async with self._db.acquire() as conn:
            results = await conn.execute(get_guild_weekly_stipends_query(guild.id))
            rows = await results.fetchall()
    
        guild.stipends = [RefWeeklyStipendSchema(self._db).load(row) for row in rows]
    

def get_guild_from_id(guild_id: int) -> FromClause:
    return guilds_table.select().where(
        guilds_table.c.id == guild_id
    )

def get_guilds_with_reset_query(day: int, hour: int) -> FromClause:
    six_days_ago = datetime.today() - timedelta(days=6)

    return guilds_table.select().where(
        and_(guilds_table.c.reset_day == day, guilds_table.c.reset_hour == hour,
             guilds_table.c.last_reset < six_days_ago)
    ).order_by(guilds_table.c.id.desc())

def upsert_guild(guild: PlayerGuild):
    insert_statment = insert(guilds_table).values(
        id=guild.id,
        max_level=guild.max_level,
        weeks=guild.weeks,
        reset_day=guild._reset_day,
        reset_hour=guild._reset_hour,
        last_reset=guild._last_reset,
        greeting=guild.greeting,
        handicap_cc=guild.handicap_cc,
        max_characters=guild.max_characters,
        div_limit=guild.div_limit,
        reset_message=guild.reset_message,
        weekly_announcement=guild.weekly_announcement,
        server_date=guild.server_date,
        epoch_notation=guild.epoch_notation,
        first_character_message=guild.first_character_message,
        ping_announcement=guild.ping_announcement,
        reward_threshold=guild.reward_threshold
    ).returning(guilds_table)

    update_dict = {
        'max_level': guild.max_level,
        'weeks': guild.weeks,
        'reset_day': guild._reset_day, 
        'reset_hour': guild._reset_hour, 
        'last_reset': guild._last_reset,
        'handicap_cc': guild.handicap_cc,
        'max_characters': guild.max_characters,
        'div_limit': guild.div_limit,
        'reset_message': guild.reset_message,
        'weekly_announcement': guild.weekly_announcement,
        'server_date': guild.server_date,
        'epoch_notation': guild.epoch_notation,
        'greeting': guild.greeting,
        'first_character_message': guild.first_character_message,
        'ping_announcement': guild.ping_announcement,
        'reward_threshold': guild.reward_threshold
    }

    upsert_statement = insert_statment.on_conflict_do_update(
        index_elements=['id'],
        set_=update_dict
    )

    return upsert_statement


