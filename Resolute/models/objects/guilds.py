import calendar
import discord
import sqlalchemy as sa

from math import floor
from marshmallow import Schema, fields, post_load
from sqlalchemy import Column, Integer, BigInteger, String, TIMESTAMP, and_, BOOLEAN
from sqlalchemy.sql import FromClause
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone, timedelta

from Resolute.models import metadata
from Resolute.models.objects.npc import NPC
from Resolute.models.objects.ref_objects import RefServerCalendar

class PlayerGuild(object):
    calendar: list[RefServerCalendar]

    def __init__(self, id: int, **kwargs):
        self.id = id

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
        self.calendar = None
        self.guild: discord.Guild = None
        self.npcs: list[NPC] = []

        # Roles
        self.archivist_role: discord.Role = None
        self.citizen_role: discord.Role = None
        self.acolyte_role: discord.Role = None
        self.senate_role: discord.Role = None
        
        # Channels
        self.help_channel: discord.TextChannel = None
        self.character_application_channel: discord.TextChannel = None
        self.market_channel: discord.TextChannel = None
        self.announcement_channel: discord.TextChannel = None
        self.archivist_channel: discord.TextChannel = None
        self.automation_channel: discord.TextChannel = None
        self.arena_board: discord.TextChannel = None

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
    Column("reward_threshold", Integer, nullable=True)
)

class GuildSchema(Schema):
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

    @post_load
    def make_guild(self, data, **kwargs):
        return PlayerGuild(**data)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    

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