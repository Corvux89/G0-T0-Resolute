import calendar
from datetime import datetime, timezone

import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load

import Resolute.bot as b
import Resolute.models.objects.characters as c
import Resolute.models.objects.players as p
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

    log_table = sa.Table(
        "log",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement="auto"),
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
        sa.Column("guild_id", sa.BigInteger, nullable=False),
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

        def load_timestamp(
            self, value
        ):  # Marshmallow doesn't like loading DateTime for some reason. This is a workaround
            return datetime(
                value.year,
                value.month,
                value.day,
                value.hour,
                value.minute,
                value.second,
                tzinfo=timezone.utc,
            )

    def __init__(self, bot, **kwargs):
        self._bot: b.G0T0Bot = bot
        self.id = kwargs.get("id")
        self.author: p.Player = kwargs.get("author")
        self.player_id = kwargs.get("player_id")
        self.player: p.Player = kwargs.get("player")
        self.guild_id = kwargs.get("guild_id")
        self.cc = kwargs.get("cc", 0)
        self.credits = kwargs.get("credits", 0)
        self.character_id = kwargs.get("character_id")
        self.character: c.PlayerCharacter = kwargs.get("character")
        self.activity: Activity = kwargs.get("activity")
        self.notes = kwargs.get("notes")
        self.adventure_id = kwargs.get("adventure_id")
        self.renown = kwargs.get("renown", 0)
        self.faction: Faction = kwargs.get("faction")
        self.invalid = kwargs.get("invalid", False)
        self.created_ts: datetime = kwargs.get("created_ts", datetime.now(timezone.utc))

    @property
    def epoch_time(self) -> int:
        """
        Convert the creation timestamp to epoch time.
        Returns:
            int: The creation timestamp in seconds since the epoch (UTC).
        """
        return calendar.timegm(self.created_ts.utctimetuple())

    async def upsert(self):
        if hasattr(self, "id") and self.id is not None:
            update_dict = {
                "activity": self.activity.id,
                "notes": getattr(self, "notes", None),
                "credits": self.credits,
                "cc": self.cc,
                "renown": self.cc,
                "invalid": self.invalid,
            }

            query = (
                DBLog.log_table.update()
                .where(DBLog.log_table.c.id == self.id)
                .values(**update_dict)
            )
        else:
            query = (
                DBLog.log_table.insert()
                .values(
                    author=self.author.id,
                    player=(
                        self.player.id
                        if hasattr(self, "player") and self.player
                        else self.player_id
                    ),
                    cc=self.cc,
                    credits=self.credits,
                    created_ts=datetime.now(timezone.utc),
                    character_id=(
                        self.character.id
                        if hasattr(self, "character") and self.character
                        else self.character_id
                    ),
                    guild_id=self.guild_id,
                    activity=self.activity.id,
                    notes=getattr(self, "notes", None),
                    adventure_id=getattr(self, "adventure_id", None),
                    faction=(
                        self.faction.id
                        if hasattr(self, "faction") and self.faction
                        else None
                    ),
                    invalid=self.invalid,
                )
                .returning(DBLog.log_table)
            )

        row = await self._bot.query(query)

        return await DBLog.LogSchema(self._bot).load(row)

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

        conf = await confirm(
            ctx,
            f"Are you sure you want to nullify the `{self.activity.value}` log "
            f"for {self.player.member.display_name if self.player.member else 'Player not found'} {f'[Character: {self.character.name}]' if self.character else ''}.\n"
            f"**Refunding**\n"
            f"{ZWSP3}**CC**: {self.cc}\n"
            f"{ZWSP3}**Credits**: {self.credits}\n"
            f"{ZWSP3}**Renown**: {self.renown} {f'for {self.faction.value}' if self.faction else ''}",
            True,
            self._bot,
        )

        if conf is None:
            raise TimeoutError()
        elif not conf:
            raise G0T0Error("Ok, cancelling")

        if self.created_ts > self.player.guild._last_reset and self.activity.diversion:
            self.player.div_cc = max(self.player.div_cc - self.cc, 0)

        note = (
            f"{self.activity.value} log # {self.id} nulled by "
            f"{ctx.author} for reason: {reason}"
        )

        await self._bot.log(
            ctx,
            self.player,
            ctx.author,
            "MOD",
            character=self.character,
            notes=note,
            cc=-self.cc,
            credits=-self.credits,
            renown=-self.renown,
            faction=self.faction if self.faction else None,
        )

        self.invalid = True

        await self.upsert()
