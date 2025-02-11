import calendar
from datetime import datetime, timezone

import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import FromClause

import Resolute.bot as b
import Resolute.models.objects.characters as c
import Resolute.models.objects.players as p
from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.helpers.general_helpers import confirm
from Resolute.models import metadata
from Resolute.models.categories import Activity
from Resolute.models.categories.categories import Faction
from Resolute.models.objects.exceptions import G0T0Error


class DBLog(object):
    """
    DBLog class represents a log entry in the database.
    Attributes:
        _bot (b.G0T0Bot): The bot instance.
        id (int): The log entry ID.
        author (p.Player): The author of the log entry.
        player_id (int): The ID of the player associated with the log entry.
        player (p.Player): The player associated with the log entry.
        guild_id (int): The ID of the guild associated with the log entry.
        cc (int): The CC value associated with the log entry. Defaults to 0.
        credits (int): The credits value associated with the log entry. Defaults to 0.
        character_id (int): The ID of the character associated with the log entry.
        character (c.PlayerCharacter): The character associated with the log entry.
        activity (Activity): The activity associated with the log entry.
        notes (str): Additional notes for the log entry.
        adventure_id (int): The ID of the adventure associated with the log entry.
        renown (int): The renown value associated with the log entry. Defaults to 0.
        faction (Faction): The faction associated with the log entry.
        invalid (bool): Indicates if the log entry is invalid. Defaults to False.
        created_ts (datetime): The timestamp when the log entry was created. Defaults to the current UTC time.
    Methods:
        epoch_time() -> int:
            Returns the creation timestamp in seconds since the epoch (UTC).
        async null(ctx: ApplicationContext, reason: str):
    """

    def __init__(self, bot, **kwargs):
        self._bot: b.G0T0Bot = bot
        self.id = kwargs.get('id')
        self.author: p.Player = kwargs.get('author')
        self.player_id = kwargs.get('player_id')
        self.player: p.Player = kwargs.get('player')
        self.guild_id = kwargs.get('guild_id')
        self.cc = kwargs.get('cc', 0)
        self.credits = kwargs.get('credits', 0)
        self.character_id = kwargs.get('character_id')
        self.character: c.PlayerCharacter = kwargs.get('character')
        self.activity: Activity = kwargs.get('activity')
        self.notes = kwargs.get('notes')
        self.adventure_id = kwargs.get('adventure_id')
        self.renown = kwargs.get('renown', 0)
        self.faction: Faction = kwargs.get('faction')
        self.invalid = kwargs.get('invalid', False)
        self.created_ts: datetime = kwargs.get('created_ts', datetime.now(timezone.utc))
    
    @property
    def epoch_time(self) -> int:
        """
        Convert the creation timestamp to epoch time.
        Returns:
            int: The creation timestamp in seconds since the epoch (UTC).
        """
        return calendar.timegm(self.created_ts.utctimetuple())
    
    async def null(self, ctx: discord.ApplicationContext, reason: str) -> None:
        """
        Nullifies the log entry for a given reason, if it is valid.
        Parameters:
        ctx (ApplicationContext): The context in which the command was invoked.
        reason (str): The reason for nullifying the log.
        Raises:
        G0T0Error: If the log has already been invalidated or if the user cancels the confirmation.
        TimeoutError: If the confirmation times out.
        Notes:
        - Prompts the user for confirmation before nullifying the log.
        - Updates the player's diversion CC if applicable.
        - Logs the nullification action.
        - Marks the log as invalid.
        - Updates the log entry in the database.
        """
        if self.invalid:
            raise G0T0Error(f"Log [ {self.id} ] has already been invalidated")
        
        conf = await confirm(ctx,
                         f"Are you sure you want to nullify the `{self.activity.value}` log "
                         f"for {self.player.member.display_name if self.player.member else 'Player not found'} {f'[Character: {self.character.name}]' if self.character else ''}.\n"
                         f"**Refunding**\n"
                         f"{ZWSP3}**CC**: {self.cc}\n"
                         f"{ZWSP3}**Credits**: {self.credits}\n"
                         f"{ZWSP3}**Renown**: {self.renown} {f'for {self.faction.value}' if self.faction else ''}", True, self._bot)
        
        if conf is None:
            raise TimeoutError()
        elif not conf:
            raise G0T0Error("Ok, cancelling")
        
        if self.created_ts > self.player.guild._last_reset and self.activity.diversion:
            self.player.div_cc = max(self.player.div_cc-self.cc, 0)

        note = (f"{self.activity.value} log # {self.id} nulled by "
                f"{ctx.author} for reason: {reason}")
        
        await self._bot.log(ctx, self.player, ctx.author, "MOD",
                            character=self.character,
                            notes=note,
                            cc=-self.cc,
                            credits=-self.credits,
                            renown=-self.renown,
                            faction=self.faction if self.faction else None)
        
        self.invalid = True

        async with self._bot.db.acquire() as conn:
            await conn.execute(upsert_log(self))


    
log_table = sa.Table(
    "log",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement='auto'),
    sa.Column("author", sa.BigInteger, nullable=False),
    sa.Column("cc", sa.Integer, nullable=True),
    sa.Column("credits", sa.Integer, nullable=True),
    sa.Column("created_ts", sa.TIMESTAMP(timezone=timezone.utc), nullable=False),
    sa.Column("character_id", sa.Integer, nullable=True),  # ref: > characters.id
    sa.Column("activity", sa.Integer, nullable=False),  # ref: > c_activity.id
    sa.Column("notes", sa.String, nullable=True),
    sa.Column("adventure_id", sa.Integer, nullable=True),  # ref: > adventures.id
    sa.Column("renown", sa.Integer, nullable=True),
    sa.Column("faction", sa.Integer, nullable=True),
    sa.Column("invalid", sa.BOOLEAN, nullable=False, default=False),
    sa.Column("player_id", sa.BigInteger, nullable=False),
    sa.Column("guild_id", sa.BigInteger, nullable=False)
)

class LogSchema(Schema):
    bot = None
    id = fields.Integer(required=True)
    author = fields.Integer(required=True)
    cc = fields.Integer(required=True)
    credits = fields.Integer(required=True)
    created_ts = fields.Method(None, "load_timestamp")
    character_id = fields.Integer(required=False, allow_none=True)
    activity = fields.Method(None, "load_activity")
    notes = fields.String(required=False, allow_none=True)
    adventure_id = fields.Integer(required=False, allow_none=True)
    renown = fields.Integer(required=True)
    faction = fields.Method(None, "load_faction", allow_none=True)
    invalid = fields.Boolean(required=True)
    player_id = fields.Integer(required=True)
    guild_id = fields.Integer(required=True)

    def __init__(self, bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @post_load
    async def make_log(self, data, **kwargs):
        log = DBLog(self.bot, **data)
        log.author = await self.bot.get_player(log.author, log.guild_id)
        log.player = await self.bot.get_player(log.player_id, log.guild_id)
        if log.character_id:
            log.character = await self.bot.get_character(log.character_id)
        return log
    
    def load_faction(self, value):
        return self.bot.compendium.get_object(Faction, value)

    def load_activity(self, value):
        return self.bot.compendium.get_object(Activity, value)

    def load_timestamp(self, value):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
        return datetime(value.year, value.month, value.day, value.hour, value.minute, value.second, tzinfo=timezone.utc)
    

def get_log_by_id(log_id: int) -> FromClause:

    return log_table.select().where(log_table.c.id == log_id)

def get_last_log_by_type(player_id: int, guild_id: int, activity_id: int) -> FromClause:
    return log_table.select().where(
        sa.and_(log_table.c.player_id == player_id,
             log_table.c.guild_id == guild_id,
             log_table.c.activity == activity_id,
             log_table.c.invalid == False)
    ).order_by(log_table.c.id.desc()).limit(1)

def get_log_count_by_player_and_activity(player_id: int, guild_id: int,  activity_id: int) -> FromClause:
    return sa.select([sa.func.count()]).select_from(log_table).where(
        sa.and_(log_table.c.player_id == player_id,
             log_table.c.guild_id == guild_id, 
             log_table.c.activity == activity_id, log_table.c.invalid == False)
    )

def upsert_log(log: DBLog):
    if hasattr(log, "id") and log.id is not None:
        update_dict = {
            "activity": log.activity.id,
            "notes": log.notes if hasattr(log, "notes") else None,
            "credits": log.credits,
            "cc": log.cc,
            "renown": log.renown,
            "invalid": log.invalid
        }

        update_statement = log_table.update().where(log_table.c.id == log.id).values(**update_dict)
        return update_statement


    insert_statement = insert(log_table).values(
        author=log.author.id,
        player_id=log.player_id,
        cc=log.cc,
        credits=log.credits,
        created_ts=datetime.now(timezone.utc),
        character_id=log.character_id,
        guild_id=log.guild_id,
        activity=log.activity.id,
        notes=log.notes if hasattr(log, "notes") else None,
        adventure_id=None if not hasattr(log, "adventure_id") else log.adventure_id,
        renown=log.renown,
        faction=None if not hasattr(log, "faction") or not log.faction else log.faction.id,
        invalid=log.invalid
    ).returning(log_table)

    return insert_statement

def get_n_player_logs_query(player_id: int, guild_id: int, n : int) -> FromClause:
    return log_table.select().where(sa.and_(log_table.c.player_id == player_id, log_table.c.guild_id == guild_id)).order_by(log_table.c.id.desc()).limit(n)

def player_stats_query(compendium: Compendium, player_id: int, guild_id: int):
    new_character_activity = compendium.get_activity("NEW_CHARACTER")
    activities = [x for x in compendium.activity[0].values() if x.value in ["RP", "ARENA", "ARENA_HOST", "GLOBAL", "SNAPSHOT"]]
    activity_columns = [sa.func.sum(sa.case([(log_table.c.activity == act.id, 1)], else_=0)).label(f"Activity {act.value}") for act in activities]

    query = sa.select(log_table.c.player_id,
                   sa.func.count(log_table.c.id).label("#"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("debt"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc < 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("credit"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc > 0, log_table.c.activity == new_character_activity.id), log_table.c.cc)], else_=0)).label("starting"),
                   *activity_columns)\
                    .group_by(log_table.c.player_id)\
                        .where(sa.and_(log_table.c.player_id == player_id,
                                    log_table.c.guild_id == guild_id,
                                     log_table.c.invalid == False))
    
    return query

def character_stats_query(compendium: Compendium, character_id: int):
    new_character_activity = compendium.get_activity("NEW_CHARACTER")
    conversion_activity = compendium.get_activity("CONVERSION")

    query = sa.select(log_table.c.character_id,
                   sa.func.count(log_table.c.id).label("#"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("cc debt"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc > 0, log_table.c.activity != new_character_activity.id), log_table.c.cc)], else_=0)).label("cc credit"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc > 0, log_table.c.activity == new_character_activity.id), log_table.c.cc)], else_=0)).label("cc starting"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.credits > 0, log_table.c.activity != new_character_activity.id), log_table.c.credits)], else_=0)).label("credit debt"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.cc < 0, log_table.c.activity != new_character_activity.id), log_table.c.credits)], else_=0)).label("credit credit"),
                   sa.func.sum(sa.case([(sa.and_(log_table.c.credits > 0, log_table.c.activity == new_character_activity.id), log_table.c.credits)], else_=0)).label("credit starting"),
                   sa.func.sum(sa.case([(log_table.c.activity == conversion_activity.id, log_table.c.credits)], else_=0)).label("credits converted"))\
                    .group_by(log_table.c.character_id)\
                    .where(sa.and_(log_table.c.character_id == character_id, log_table.c.invalid == False))
    return query


