import logging
import math
import discord

from discord import SlashCommandGroup, Option, ApplicationContext
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ZWSP3
from Resolute.helpers.general_helpers import confirm, is_admin
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log, get_character_stats, get_log, get_n_player_logs, get_player_stats
from Resolute.helpers.players import get_player
from Resolute.models.categories import Activity, CodeConversion
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed, LogHxEmbed, LogStatsEmbed
from Resolute.models.objects.logs import upsert_log
from Resolute.models.views.logs import LogPromptUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Log(bot))

class Log(commands.Cog):
    bot: G0T0Bot
    log_commands = SlashCommandGroup("log", "Logging commands for the Archivist", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Log\' loaded')

    @log_commands.command(
        name="rp",
        description="Logs a completed RP"
    )
    async def rp_log(self, ctx: ApplicationContext,
                     member: Option(discord.SlashCommandOptionType(6),description="Player who participated in the RP", required=True)):
        if activity := self.bot.compendium.get_activity("RP"):
            await self.prompt_log(ctx, member, activity)
        else:
            return await ctx.respond(embed=ErrorEmbed(description="Activity not found"), ephemeral=True)
        
    @log_commands.command(
        name="snapshot",
        description="Logs a completed snapshot"
    )
    async def rp_log(self, ctx: ApplicationContext,
                     member: Option(discord.SlashCommandOptionType(6),description="Player who participated in the snapshot", required=True)):
        if activity := self.bot.compendium.get_activity("SNAPSHOT"):
            await self.prompt_log(ctx, member, activity)
        else:
            return await ctx.respond(embed=ErrorEmbed(description="Activity not found"), ephemeral=True)

    @log_commands.command(
        name="bonus",
        description="Give bonus gold and/or xp to a player"
    )
    async def bonus_log(self, ctx: ApplicationContext,
                        member: Option(discord.SlashCommandOptionType(6), description="Player receiving the bonus", required=True),
                        reason: Option(str, description="The reason for the bonus", required=True),
                        cc: Option(int, description="The amount of Chain Codes", default=0, min_value=0, max_value=50),
                        credits: Option(int, description="The amount of Credits", default=0, min_value=0, max_value=20000)):
        
        if (activity := self.bot.compendium.get_activity("BONUS")) and (credits > 0 or cc > 0):
            await self.prompt_log(ctx, member, activity, reason, cc, credits, False, False, True)
        else:
            return await ctx.respond(embed=ErrorEmbed(description="Activity not found"), ephemeral=True)
        
    @log_commands.command(
        name="buy",
        description="Logs the sale of an item to a player"
    )
    async def buy_log(self, ctx: ApplicationContext,
                      member: Option(discord.SlashCommandOptionType(6), description="Player who bought the item", required=True),
                      item: Option(str, description="The item being bought", required=True),
                      cost: Option(int, description="The cost of the item", min_value=0, max_value=9999999,
                                   required=True),
                      currency: Option(str, description="Credits or Chain Codes. Default: Credits",
                                       choices=['Credits', 'CC'], default="Credits", required=False)):
        
        if activity := self.bot.compendium.get_activity("BUY"):
            if currency == 'Credits':
                await self.prompt_log(ctx, member, activity, item, 0, -cost, True, False, True)
            elif currency == "CC":
                await ctx.defer()
                g = await get_guild(self.bot, ctx.guild.id)
                player = await get_player(self.bot, member.id, ctx.guild.id)

                if (player.cc - cost ) < 0:
                    return await ctx.respond(embed=ErrorEmbed(description=f"{player.member.mention} cannot afford the {cost} CC cost."))
                
                log_entry = await create_log(self.bot, ctx.author, g, activity, player,
                                             notes=item,
                                              cc=-cost,
                                              ignore_handicap=True)
                return await ctx.respond(embed=LogEmbed(log_entry, ctx.author, member, None, True))
            else:
                return await ctx.respond(embed=ErrorEmbed(description="Invalid currency selection"),
                                         ephemeral=True)
            
    @log_commands.command(
        name="sell",
        description="Logs the sale of an item from a player. Not for player establishment sales"
    )
    async def sell_log(self, ctx: ApplicationContext,
                       member: Option(discord.SlashCommandOptionType(6), description="Player who bought the item", required=True),
                       item: Option(str, description="The item being sold", required=True),
                       cost: Option(int, description="The cost of the item", min_value=0, max_value=9999999,
                                    required=True),
                       currency: Option(str, description="Credits or Chain Codes. Default: Credits",
                                        choices=['Credits', 'CC'], default="Credits", required=False)):
        
        if activity := self.bot.compendium.get_activity("SELL"):
            if currency == 'Credits':
                await self.prompt_log(ctx, member, activity, item, 0, cost, True, False, True)
            elif currency == "CC":
                await ctx.defer()
                g = await get_guild(self.bot, ctx.guild.id)
                player = await get_player(self.bot, member.id, ctx.guild.id)
                log_entry = await create_log(self.bot, ctx.author, g, activity, player,
                                             notes=item,
                                             cc=cost,
                                             ignore_handicap=True)
                return await ctx.respond(embed=LogEmbed(log_entry, ctx.author, member, None, True))
            else:
                return await ctx.respond(embed=ErrorEmbed(description="Invalid currency selection"),
                                         ephemeral=True)


    @log_commands.command(
        name="null",
        description="Nullifies a log"
    )
    @commands.check(is_admin)
    async def null_log(self, ctx: ApplicationContext,
                       log_id: Option(int, description="ID of the log to modify", required=True),
                       reason: Option(str, description="Reason for nulling the log", required=True)):
        
        await ctx.defer()
        log_entry = await get_log(self.bot, log_id)

        if log_entry is None:
            return await ctx.respond(embed=ErrorEmbed(description=f"No log found with id [ {log_id} ]"),
                                     ephemeral=True)
        elif log_entry.invalid:
            return await ctx.respond(embed=ErrorEmbed(description=f"Log [ {log_entry} ] has already been invalidated.",
                                                      ephemeral=True))
        
        player = await get_player(self.bot, log_entry.player_id, ctx.guild.id)
        g = await get_guild(self.bot, ctx.guild.id)

        if log_entry.character_id:
            character = next((c for c in player.characters if c.id == log_entry.character_id), None)
        else:
            character = None

        conf = await confirm(ctx,
                             f"Are you sure you want to nullify the `{log_entry.activity.value}` log"
                             f" for {player.member.display_name if player.member else 'Player not found'} {f'[ Character: {character.name} ]' if character else ''} "
                             f" for {log_entry.cc} chain codes, {log_entry.credits} credits\n"
                             f"(Reply with yes/no)", True)
        
        if conf is None:
            return await ctx.respond(f"Times out waiting for a response or invalid response.", delete_after=5)
        elif not conf:
            return await ctx.respond(f"Ok, cancelling.", delete_after=5)
        
        if activity := self.bot.compendium.get_activity("MOD"):
            if log_entry.created_ts > g._last_reset and log_entry.activity.diversion:
                player.div_cc -= log_entry.cc

            note = f"{log_entry.activity.value} log # {log_entry.id} nulled by "\
                   f"{ctx.author} for reason: {reason}"

            mod_log = await create_log(self.bot, ctx.author, g, activity, player,
                                       character=character,
                                       notes=note,
                                       cc=-log_entry.cc,
                                       credits=-log_entry.credits,
                                       ignore_handicap=True)
            log_entry.invalid = True

            async with self.bot.db.acquire() as conn:
                await conn.execute(upsert_log(log_entry))            
            
            return await ctx.respond(embed=LogEmbed(mod_log, ctx.author, player.member, character))

    @log_commands.command(
        name="stats",
        description="Log statistics for a character"
    )
    async def log_stats(self, ctx: ApplicationContext,
                        member: Option(discord.SlashCommandOptionType(6), description="Player to view stats for", required=True)):
        await ctx.defer()

        player = await get_player(self.bot, member.id, ctx.guild.id, True)
        player_stats = await get_player_stats(self.bot, player)

        embeds = []
        embed = LogStatsEmbed(self.bot, player, player_stats)
        if player.characters:
            sorted_characters = sorted(player.characters, key=lambda c: c.active, reverse=True)
            for character in sorted_characters:
                char_stats = await get_character_stats(self.bot, character)
                if char_stats:
                    embed.add_field(name=f"{character.name}{' (*inactive*)' if not character.active else ''}",
                                    value=f"{ZWSP3}**Starting Credits**: {char_stats['credit starting']:,}\n"
                                        f"{ZWSP3}**Starting CC**: {char_stats['cc starting']:,}\n"
                                        f"{ZWSP3}**CC Earned**: {char_stats['cc debt']:,}\n"
                                        f"{ZWSP3}**CC Spent**: {char_stats['cc credit']:,}\n"
                                        f"{ZWSP3}**Credits Earned**: {char_stats['credit debt']:,}\n"
                                        f"{ZWSP3}**Credits Spent**: {char_stats['credit credit']:,}\n"
                                        f"{ZWSP3}**Credits Converted**: {char_stats['credits converted']:,}",
                                        inline=False)
                else:
                    embed.add_field(name=f"{character.name}{' (*inactive*)' if not character.active else ''}",
                    value="Nothing",
                    inline=False)
                
                if len(embed.fields) > 20:
                    embeds.append(embed)
                    embed = LogStatsEmbed(self.bot, player, player_stats, False)

        if embed not in embeds:
            embeds.append(embed)

        for embed in embeds:
            await ctx.send(embed=embed)
        await ctx.delete()

    @log_commands.command(
        name="get_history",
        description="Get the last weeks worth of logs for a player"
    )
    async def get_log_hx(self, ctx: ApplicationContext,
                         member: Option(discord.SlashCommandOptionType(6), description="Player to get logs for", required=True),
                         num_logs: Option(int, description="Number of logs to get",
                                          min_value=1, max_value=20, default=5)):
        await ctx.defer()

        player = await get_player(self.bot, member.id, ctx.guild.id, True)

        logs = await get_n_player_logs(self.bot, player, num_logs)

        await ctx.respond(embed=LogHxEmbed(self.bot, player, logs))
         
    # --------------------------- #
    # Private Methods
    # --------------------------- #

    async def prompt_log(self, ctx: ApplicationContext, member: discord.Member, activity: Activity, notes: str = None, 
                         cc: int = 0, credits: int = 0, ignore_handicap: bool = False, conversion: bool = False, show_values: bool = False) -> None:
        await ctx.defer()

        player = await get_player(self.bot, member.id, ctx.guild_id)
        g = await get_guild(self.bot, ctx.guild.id)

        if not player.characters:
            return await ctx.respond(embed=ErrorEmbed(description=f"No character information found for {member.mention}"),
                                        ephemeral=True)
        
        if (player.cc + cc) < 0:
            return await ctx.respond(embed=ErrorEmbed(description=f"{member.mention} cannot afford the {cc} CC cost."))

        if len(player.characters) == 1:
            character = player.characters[0]
            rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, character.level)
            if conversion:
                credits = abs(cc) * rate.value
                ignore_handicap = True

            if (character.credits + credits) < 0:
                convertedCC = math.ceil((abs(credits) - character.credits) / rate.value)
                if player.cc < convertedCC:
                    return await ctx.respond(embed=ErrorEmbed(description=f"{character.name} cannot afford the {credits} credit cost or to convert the {convertedCC} needed."))

                convert_activity = self.bot.compendium.get_activity("CONVERSION")
                converted_entry = await create_log(self.bot, ctx.author, g, convert_activity, player, 
                                                   character=character, 
                                                   notes=notes, 
                                                   cc=-convertedCC, 
                                                   credits=convertedCC*rate.value, 
                                                   ignore_handicap=True)  
                await ctx.send(embed=LogEmbed(converted_entry, ctx.author, member, player.characters[0], show_values))
            
            log_entry = await create_log(self.bot, ctx.author, g, activity, player, 
                                         character=character, 
                                         notes=notes, 
                                         cc=cc, 
                                         credits=credits, 
                                         ignore_handicap=ignore_handicap)
            
            return await ctx.respond(embed=LogEmbed(log_entry, ctx.author, member, player.characters[0],show_values))
        else:
            ui = LogPromptUI.new(self.bot, ctx.author, member, player, g, activity, credits=credits, cc=cc, notes=notes,
                                 ignore_handicap=ignore_handicap, show_values=show_values)    
            await ui.send_to(ctx)
            await ctx.delete()
