from __future__ import annotations
from math import ceil
from typing import TYPE_CHECKING, Optional, Union

from datetime import datetime, timezone


import discord
import sqlalchemy as sa
from marshmallow import Schema, fields, post_load
from Resolute.constants import APPROVAL_EMOJI, ZWSP3
from Resolute.helpers import confirm
from Resolute.models import metadata
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.enum import QueryResultType
from Resolute.models.objects.exceptions import G0T0Error, TransactionError
from Resolute.models.objects.players import Player
from Resolute.models.categories import Activity
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.categories.categories import Faction
from Resolute.models.categories.categories import CodeConversion

if TYPE_CHECKING:
    from Resolute.bot import G0T0Bot


class DBLog(object):
    """
    DBLog class represents a log entry in the database.
    Attributes:
        _bot (G0T0Bot): The bot instance.
        id (int): The log entry ID.
        author (Player): The author of the log entry.
        player_id (int): The ID of the player associated with the log entry.
        player (Player): The player associated with the log entry.
        guild_id (int): The ID of the guild associated with the log entry.
        cc (int): The CC value associated with the log entry. Defaults to 0.
        credits (int): The credits value associated with the log entry. Defaults to 0.
        character_id (int): The ID of the character associated with the log entry.
        character (PlayerCharacter): The character associated with the log entry.
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
        bot: G0T0Bot = None
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

        def __init__(self, bot: G0T0Bot, **kwargs):
            super().__init__(**kwargs)
            self.bot = bot

        @post_load
        async def make_log(self, data, **kwargs):
            log = DBLog(self.bot, **data)
            log.author = await Player.get_player(self.bot, log.author, log.guild_id)
            log.player = await Player.get_player(self.bot, log.player_id, log.guild_id)
            if log.character_id:
                log.character = await PlayerCharacter.get_character(
                    self.bot, log.character_id
                )
            return log

        def load_faction(self, value: int) -> Faction:
            return self.bot.compendium.get_object(Faction, value)

        def load_activity(self, value: int) -> Activity:
            return self.bot.compendium.get_object(Activity, value)

        def load_timestamp(
            self, value: datetime
        ) -> (
            datetime
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
        self._bot: G0T0Bot = bot
        self.id = kwargs.get("id")
        self.author: Player = kwargs.get("author")
        self.player_id = kwargs.get("player_id")
        self.player: Player = kwargs.get("player")
        self.guild_id = kwargs.get("guild_id")
        self.cc = kwargs.get("cc", 0)
        self.credits = kwargs.get("credits", 0)
        self.character_id = kwargs.get("character_id")
        self.character: PlayerCharacter = kwargs.get("character")
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
        return int(self.created_ts.timestamp())

    async def upsert(self) -> "DBLog":
        update_dict = {
            "activity": self.activity.id,
            "notes": getattr(self, "notes", None),
            "credits": self.credits,
            "cc": self.cc,
            "renown": self.renown,
            "invalid": self.invalid,
            "faction": (
                self.faction.id if hasattr(self, "faction") and self.faction else None
            ),
            "adventure_id": getattr(self, "adventure_id", None),
        }

        insert_dict = {
            **update_dict,
            "author": self.author.id,
            "player_id": (
                self.player.id
                if hasattr(self, "player") and self.player
                else self.player_id
            ),
            "created_ts": datetime.now(timezone.utc),
            "character_id": (
                self.character.id
                if hasattr(self, "character") and self.character
                else self.character_id
            ),
            "guild_id": self.guild_id,
        }

        if hasattr(self, "id") and self.id is not None:
            query = (
                DBLog.log_table.update()
                .where(DBLog.log_table.c.id == self.id)
                .values(**update_dict)
                .returning(DBLog.log_table)
            )
        else:
            query = (
                DBLog.log_table.insert()
                .values(**insert_dict)
                .returning(DBLog.log_table)
            )

        row = await self._bot.query(query)

        return await DBLog.LogSchema(self._bot).load(row)

    async def null(
        self, ctx: discord.ApplicationContext, reason: str, bulk: bool = False
    ) -> None:
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

        if not bulk:
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

        await DBLog.create(
            self._bot,
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
            ignore_handicap=True,
        )

        self.invalid = True

        await self.upsert()

    @staticmethod
    async def create(
        bot: G0T0Bot,
        ctx: Optional(discord.ApplicationContext, discord.Interaction),
        player: Union(discord.Member, discord.ClientUser, Player),
        author: Union(discord.Member, discord.ClientUser, Player),
        activity: Union(Activity, str),
        **kwargs,
    ) -> "DBLog":
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

        player: Player = (
            player
            if isinstance(player, Player)
            else await Player.get_player(bot, player.id, guild_id)
        )
        author: Player = (
            author
            if isinstance(author, Player)
            else await Player.get_player(bot, author.id, guild_id)
        )
        activity: Activity = (
            activity
            if isinstance(activity, Activity)
            else bot.compendium.get_activity(activity)
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
        reaction = kwargs.get("reaction")

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
            rate: CodeConversion = bot.compendium.get_object(
                CodeConversion, character.level
            )
            convertedCC = ceil((abs(credits) - character.credits) / rate.value)
            if player.cc < convertedCC:
                raise TransactionError(
                    f"{character.name} cannot afford the {credits:,} credit cost or to convert the {convertedCC:,} needed."
                )

            await DBLog.create(
                bot,
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
                silent=silent,
                reaction=APPROVAL_EMOJI[0],
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
            bot,
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
                act: Activity = bot.compendium.get_activity("LOG_REWARD")
                reward_log = await DBLog.create(
                    bot,
                    ctx,
                    author,
                    bot.user,
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
                msg: discord.Message = await ctx.respond(embed=embed)
            else:
                msg: discord.Message = await ctx.channel.send(embed=embed)

            if reaction:
                try:
                    await msg.add_reaction(reaction)
                except:
                    pass

        return log_entry

    @staticmethod
    async def get_log(bot: G0T0Bot, log_id: int) -> "DBLog":
        query = DBLog.log_table.select().where(DBLog.log_table.c.id == log_id)

        row = await bot.query(query)

        if not row:
            return None

        log_entry = await DBLog.LogSchema(bot).load(row)

        return log_entry

    @staticmethod
    async def get_n_player_logs(
        bot: G0T0Bot, player: Player, n: int = 5
    ) -> list["DBLog"]:
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

        rows = await bot.query(query, QueryResultType.multiple)

        if not rows:
            return None

        logs = [await DBLog.LogSchema(bot).load(row) for row in rows]

        return logs
