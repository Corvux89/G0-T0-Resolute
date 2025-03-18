import logging

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import ZWSP3
from Resolute.helpers import is_admin, is_staff
from Resolute.models.embeds.logs import LogHxEmbed, LogStatsEmbed
from Resolute.models.objects.exceptions import (
    CharacterNotFound,
    G0T0Error,
    InvalidCurrencySelection,
    LogNotFound,
)
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player
from Resolute.models.views.logs import LogPromptUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Log(bot))


class Log(commands.Cog):
    """
    A Discord Cog for logging various activities and actions within the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        log_commands (SlashCommandGroup): The slash command group for logging commands.
    Methods:
        __init__(bot):
            Initializes the Log cog.
        rp_log(ctx, member, host):
            Logs a completed RP.
        snapshot_log(ctx, member):
            Logs a completed snapshot.
        bonus_log(ctx, member, reason, cc, credits):
            Gives bonus gold and/or XP to a player.
        buy_log(ctx, member, item, cost, currency):
            Logs the sale of an item to a player.
        sell_log(ctx, member, item, cost, currency):
            Logs the sale of an item from a player.
        null_log(ctx, log_id, reason):
            Nullifies a log.
        log_stats(ctx, member):
            Logs statistics for a character.
        get_log_hx(ctx, member, num_logs):
            Gets the last week's worth of logs for a player.
    Private Methods:
        prompt_log(ctx, member, activity, notes, cc, credits, ignore_handicap, conversion, show_values):
            Prompts the user to log an activity.
    """

    bot: G0T0Bot
    log_commands = discord.SlashCommandGroup(
        "log", "Logging commands for staff", guild_only=True
    )

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Log' loaded")

    @log_commands.command(name="rp", description="Logs a completed RP")
    @commands.check(is_staff)
    async def rp_log(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player who participated in the RP",
            required=True,
        ),
        host: discord.Option(
            discord.SlashCommandOptionType(5),
            description="Host of the RP or not",
            required=True,
            default=False,
        ),
    ):
        """
        Logs a role-playing (RP) event.
        Parameters:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            member (discord.Option): The player who participated in the RP.
            host (discord.Option): Indicates whether the member is the host of the RP.
        Returns:
            None
        """

        if host:
            await DBLog.create(self.bot, ctx, member, ctx.author, "RP_HOST")
        else:
            await self._prompt_log(ctx, member, "RP")

    @log_commands.command(name="snapshot", description="Logs a completed snapshot")
    @commands.check(is_staff)
    async def snapshot_log(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player who participated in the snapshot",
            required=True,
        ),
    ):
        await self._prompt_log(ctx, member, "SNAPSHOT")

    @log_commands.command(
        name="bonus", description="Give bonus gold and/or xp to a player"
    )
    @commands.check(is_staff)
    async def bonus_log(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player receiving the bonus",
            required=True,
        ),
        reason: discord.Option(
            discord.SlashCommandOptionType(3),
            description="The reason for the bonus",
            required=True,
        ),
        cc: discord.Option(
            discord.SlashCommandOptionType(4),
            description="The amount of Chain Codes",
            default=0,
            min_value=0,
            max_value=50,
        ),
        credits: discord.Option(
            discord.SlashCommandOptionType(4),
            description="The amount of Credits",
            default=0,
            min_value=0,
            max_value=20000,
        ),
    ):
        """
        Logs a bonus for a specified member with a given reason and amounts of Chain Codes and Credits.

        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            member (discord.Option): The player receiving the bonus.
            reason (discord.Option): The reason for the bonus.
            cc (discord.Option, discord.Optional): The amount of Chain Codes to be awarded (default is 0, with a minimum of 0 and a maximum of 50).
            credits (discord.Option, discord.Optional): The amount of Credits to be awarded (default is 0, with a minimum of 0 and a maximum of 20000).

        Raises:
            G0T0Error: If neither Chain Codes nor Credits are specified.
        """
        if credits > 0 or cc > 0:
            await self._prompt_log(
                ctx, member, "BONUS", reason, cc, credits, False, False, True
            )
        else:
            raise G0T0Error(f"You need to specify some sort of amount")

    @log_commands.command(
        name="buy", description="Logs the sale of an item to a player"
    )
    @commands.check(is_staff)
    async def buy_log(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player who bought the item",
            required=True,
        ),
        item: discord.Option(
            discord.SlashCommandOptionType(3),
            description="The item being bought",
            required=True,
        ),
        cost: discord.Option(
            discord.SlashCommandOptionType(4),
            description="The cost of the item",
            min_value=0,
            max_value=9999999,
            required=True,
        ),
        currency: discord.Option(
            str,
            description="Credits or Chain Codes. Default: Credits",
            choices=["Credits", "CC"],
            default="Credits",
            required=False,
        ),
    ):
        """
        Handles the logging of a purchase made by a player.
        Parameters:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            member (discord.Option): The player who bought the item.
            item (discord.Option): The item being bought.
            cost (discord.Option): The cost of the item.
            currency (discord.Option): The currency used for the purchase, either 'Credits' or 'CC'. Default is 'Credits'.
        Raises:
            InvalidCurrencySelection: If the currency selected is not 'Credits' or 'CC'.
        Returns:
            None
        """
        if currency == "Credits":
            await self._prompt_log(
                ctx, member, "BUY", item, 0, -cost, True, False, True
            )
        elif currency == "CC":

            await DBLog.create(
                self.bot,
                ctx,
                member,
                ctx.author,
                "BUY",
                cc=-cost,
                notes=item,
                ignore_handicap=True,
                show_values=True,
            )
        else:
            raise InvalidCurrencySelection()

    @log_commands.command(
        name="sell",
        description="Logs the sale of an item from a player. Not for player establishment sales",
    )
    @commands.check(is_staff)
    async def sell_log(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player who bought the item",
            required=True,
        ),
        item: discord.Option(
            discord.SlashCommandOptionType(3),
            description="The item being sold",
            required=True,
        ),
        cost: discord.Option(
            discord.SlashCommandOptionType(4),
            description="The cost of the item",
            min_value=0,
            max_value=9999999,
            required=True,
        ),
        currency: discord.Option(
            discord.SlashCommandOptionType(3),
            description="Credits or Chain Codes. Default: Credits",
            choices=["Credits", "CC"],
            default="Credits",
            required=False,
        ),
    ):
        """
        Handles the logging of a sell transaction.
        Parameters:
            ctx (discord.ApplicationContext): The context of the command invocation.
            member (discord.Option): The player who bought the item.
            item (discord.Option): The item being sold.
            cost (discord.Option): The cost of the item.
            currency (discord.Option): The currency used for the transaction, either 'Credits' or 'CC'. Default is 'Credits'.
        Raises:
            InvalidCurrencySelection: If an invalid currency is selected.
        Returns:
            None
        """
        if currency == "Credits":
            await self._prompt_log(
                ctx, member, "SELL", item, 0, cost, True, False, True
            )

        elif currency == "CC":

            await DBLog.create(
                self.bot,
                ctx,
                member,
                ctx.author,
                "SELL",
                notes=item,
                cc=cost,
                ignore_handicap=True,
                show_values=True,
            )

        else:
            raise InvalidCurrencySelection()

    # TODO: Allow the log_id to be a greedy list of ID's
    @log_commands.command(name="null", description="Nullifies a log")
    @commands.check(is_admin)
    async def null_log(
        self,
        ctx: G0T0Context,
        log_id: discord.Option(
            discord.SlashCommandOptionType(4),
            description="ID of the log to modify",
            required=True,
        ),
        reason: discord.Option(
            discord.SlashCommandOptionType(3),
            description="Reason for nulling the log",
            required=True,
        ),
    ):
        """
        Nullifies a log entry by its ID and provides a reason for the action.
        Args:
            ctx (discord.ApplicationContext): The context in which the command is being invoked.
            log_id (discord.Option[int]): The ID of the log to modify.
            reason (discord.Option[str]): The reason for nulling the log.
        Raises:
            LogNotFound: If the log entry with the specified ID is not found.
        Returns:
            None: Responds to the context with an embedded log entry.
        """

        log_entry = await DBLog.get_log(self.bot, log_id)

        if log_entry is None:
            raise LogNotFound(log_id)

        await log_entry.null(ctx, reason)

    @log_commands.command(name="stats", description="Log statistics for a character")
    async def log_stats(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player to view stats for",
            required=True,
        ),
    ):

        player = await Player.get_player(
            self.bot, member.id, ctx.guild.id, inactive=True
        )
        player_stats = await self.bot.get_player_stats(player)

        embeds = []
        embed = LogStatsEmbed(player, player_stats)
        if player.characters:
            sorted_characters = sorted(
                player.characters, key=lambda c: c.active, reverse=True
            )
            for character in sorted_characters:
                char_stats = await self.bot.get_character_stats(character)
                if char_stats:
                    embed.add_field(
                        name=f"{character.name}{' (*inactive*)' if not character.active else ''}",
                        value=f"{ZWSP3}**Starting Credits**: {char_stats['credit starting']:,}\n"
                        f"{ZWSP3}**Starting CC**: {char_stats['cc starting']:,}\n"
                        f"{ZWSP3}**CC Earned**: {char_stats['cc debt']:,}\n"
                        f"{ZWSP3}**CC Spent**: {char_stats['cc credit']:,}\n"
                        f"{ZWSP3}**Credits Earned**: {char_stats['credit debt']:,}\n"
                        f"{ZWSP3}**Credits Spent**: {char_stats['credit credit']:,}\n"
                        f"{ZWSP3}**Credits Converted**: {char_stats['credits converted']:,}",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name=f"{character.name}{' (*inactive*)' if not character.active else ''}",
                        value="Nothing",
                        inline=False,
                    )

                if len(embed.fields) > 20:
                    embeds.append(embed)
                    embed = LogStatsEmbed(self.bot, player, player_stats, False)

        if embed not in embeds:
            embeds.append(embed)

        for embed in embeds:
            await ctx.send(embed=embed)
        await ctx.delete()

    @log_commands.command(
        name="get_history", description="Get the last weeks worth of logs for a player"
    )
    async def get_log_hx(
        self,
        ctx: G0T0Context,
        member: discord.Option(
            discord.SlashCommandOptionType(6),
            description="Player to get logs for",
            required=True,
        ),
        num_logs: discord.Option(
            discord.SlashCommandOptionType(4),
            description="Number of logs to get",
            min_value=1,
            max_value=20,
            default=5,
        ),
    ):
        """
        Retrieves and responds with a specified number of logs for a given player.
        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            member (discord.Option): The player to get logs for.
            num_logs (discord.Option): The number of logs to retrieve, with a minimum of 1 and a maximum of 20. Defaults to 5.
        Returns:
            None
        """

        player = await Player.get_player(
            self.bot, member.id, ctx.guild.id, inactive=True
        )

        logs = await DBLog.get_n_player_logs(self.bot, player, num_logs)

        await ctx.respond(embed=LogHxEmbed(player, logs))

    # --------------------------- #
    # Private Methods
    # --------------------------- #

    async def _prompt_log(
        self,
        ctx: G0T0Context,
        member: discord.Member,
        activity: str,
        notes: str = None,
        cc: int = 0,
        credits: int = 0,
        ignore_handicap: bool = False,
        conversion: bool = False,
        show_values: bool = False,
    ) -> None:

        player = await Player.get_player(self.bot, member.id, ctx.guild_id)

        if not player.characters:
            raise CharacterNotFound(player.member)

        if len(player.characters) == 1:
            character = player.characters[0]
            await DBLog.create(
                self.bot,
                ctx,
                player,
                ctx.player,
                activity,
                cc=cc,
                credits=credits,
                notes=notes,
                character=character,
                ignore_handicap=ignore_handicap,
                show_values=show_values,
            )
        else:
            ui = LogPromptUI.new(
                self.bot,
                ctx.player,
                player,
                activity,
                credits=credits,
                cc=cc,
                notes=notes,
                ignore_handicap=ignore_handicap,
                show_values=show_values,
            )
            await ui.send_to(ctx)
            await ctx.delete()
