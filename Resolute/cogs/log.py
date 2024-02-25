import logging

from discord import SlashCommandGroup, Option, ApplicationContext, Member, Role, Embed, Color
from discord.ext import commands

from Resolute.helpers import *
from Resolute.bot import G0T0Bot
from Resolute.models.db_objects import PlayerCharacter, Activity, DBLog, Adventure, LevelCaps, PlayerGuild
from Resolute.models.embeds import ErrorEmbed, HxLogEmbed, DBLogEmbed, AdventureRewardEmbed
from Resolute.models.schemas import LogSchema, CharacterSchema
from Resolute.queries import get_n_player_logs, get_multiple_characters, update_adventure, update_log, update_guild, \
    update_character, insert_new_log

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Log(bot))


class Log(commands.Cog):
    bot: G0T0Bot
    log_commands = SlashCommandGroup("log", "Logging commands for the Archivist")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Log\' loaded')

    @log_commands.command(
        name="get_history",
        description="Get the last weeks worth of logs for a player"
    )
    async def get_log_hx(self, ctx: ApplicationContext,
                         player: Option(Member, description="Player to get logs for", required=True),
                         num_logs: Option(int, description="Number of logs to get",
                                          min_value=1, max_value=20, default=5)):
        """
        Gets the log history for a given user

        :param ctx: Context
        :param player: Member to lookup
        :param num_logs: Number of logs to lookup
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        log_ary = []

        async with self.bot.db.acquire() as conn:
            async for row in conn.execute(get_n_player_logs(character.id, num_logs)):
                if row is not None:
                    log: DBLog = LogSchema(ctx.bot.compendium).load(row)
                    log_ary.append(log)

        await ctx.respond(embed=HxLogEmbed(log_ary, character, ctx), ephemeral=True)

    @log_commands.command(
        name="rp",
        description="Logs a completed RP"
    )
    async def rp_log(self, ctx: ApplicationContext,
                     player: Option(Member, description="Player who participated in the RP", required=True)):
        """
        Logs a completed RP for a player

        :param ctx: Context
        :param player: Member getting rewarded
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        act: Activity = ctx.bot.compendium.get_object("c_activity", "RP")

        log_entry = await create_logs(ctx, character, act)

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character, False))

    @log_commands.command(
        name="bonus",
        description="Give bonus gold and/or xp to a player"
    )
    async def bonus_log(self, ctx: ApplicationContext,
                        player: Option(Member, description="Player receiving the bonus", required=True),
                        reason: Option(str, description="The reason for the bonus", required=True),
                        cc: Option(int, description="The amount of Chain Codes", default=0, min_value=0, max_value=5),
                        credits: Option(int, description="The amount of Credits", default=0, min_value=0, max_value=250)):
        """
        Log a bonus for a player
        :param ctx: Context
        :param player: Member
        :param reason: Reason for the bonus
        :param gold: Amount of gold
        :param xp: Amoung of xp
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            print(f"No character information found for player [ {player.id} ], aborting")
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        act: Activity = ctx.bot.compendium.get_object("c_activity", "BONUS")

        log_entry = await create_logs(ctx, character, act, reason, cc, credits, None, True)

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))


    @log_commands.command(
        name="null",
        description="Nullifies a log"
    )
    @commands.check(is_admin)
    async def null_log(self, ctx: ApplicationContext,
                       log_id: Option(int, description="ID of the log to modify", required=True),
                       reason: Option(str, description="Reason for nulling the log", required=True)):
        await ctx.defer()

        log_entry: DBLog = await get_log(ctx.bot, log_id)

        if log_entry is None:
            return await ctx.respond(embed=ErrorEmbed(description=f"No log found with id [ {log_id} ]"), ephemeral=True)
        elif log_entry.invalid == True:
            return await ctx.respond(embed=ErrorEmbed(description=f"Log [ {log_entry.id} ] already invalidated."),
                                     ephemeral=True)
        else:
            character: PlayerCharacter = await get_character_from_char_id(ctx.bot, log_entry.character_id)

            if character is None:
                return await ctx.respond(embed=ErrorEmbed(description=f"No active character found associated with "
                                                                      f"log [ {log_id} ]"), ephemeral=True)
            elif character.guild_id != ctx.guild_id:
                return await ctx.respond(embed=ErrorEmbed(description=f"Not your server. Not your problem"),
                                         ephemeral=True)
            else:
                conf = await confirm(ctx,
                                     f"Are you sure you want to inactivate nullify the `{log_entry.activity.value}` log"
                                     f" for {character.name} for ( {log_entry.cc} Chain Codes, {log_entry.credits} credits"
                                     f"and {log_entry.token} leveling tokens?"
                                     f" (Reply with yes/no)", True)

                if conf is None:
                    return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
                elif not conf:
                    return await ctx.respond(f'Ok, cancelling.', delete_after=10)

                g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

                character.cc -= log_entry.cc
                character.credits -= log_entry.credits
                character.token -= log_entry.token

                if log_entry.created_ts > g.last_reset:
                    if log_entry.activity.diversion:
                        character.div_cc -= log_entry.cc

                note = f"{log_entry.activity.value} log # {log_entry.id} nulled by " \
                       f"{ctx.author} for reason: {reason}"

                act = ctx.bot.compendium.get_object("c_activity", "MOD")

                mod_log = DBLog(author=ctx.bot.user.id, cc=-log_entry.cc, credits=-log_entry.credits, token=-log_entry.token,
                                character_id=character.id, activity=act, notes=note, invalid=False)
                log_entry.invalid = True

                async with ctx.bot.db.acquire() as conn:
                    results = await conn.execute(insert_new_log(mod_log))
                    row = await results.first()
                    await conn.execute(update_log(log_entry))
                    await conn.execute(update_guild(g))
                    await conn.execute(update_character(character))

                result_log = LogSchema(ctx.bot.compendium).load(row)

                await ctx.respond(embed=DBLogEmbed(ctx, result_log, character))

    @log_commands.command(
        name="buy",
        description="Logs the sale of an item to a player"
    )
    async def buy_log(self, ctx: ApplicationContext,
                      player: Option(Member, description="Player who bought the item", required=True),
                      item: Option(str, description="The item being bought", required=True),
                      cost: Option(int, description="The cost of the item", min_value=0, max_value=9999999,
                                   required=True),
                      currency: Option(str, description="Credits or Chain Codes. Default: Credits",
                                       choices=['Credits', 'CC'], default="Credits", required=False)):

        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        act = ctx.bot.compendium.get_object("c_activity", "BUY")

        if currency == "Credits":
            if character.credits < cost:
                return await ctx.respond(embed=ErrorEmbed(description=f"{player.mention} cannot afford the {cost} credit cost"))

            log_entry: DBLog = await create_logs(ctx, character, act, item, 0, -cost)

        elif currency == "CC":
            if character.cc < cost:
                return await ctx.respond(embed=ErrorEmbed(description=f"{player.mention} cannot affort the {cost} CC cost"))

            log_entry: DBLog = await create_logs(ctx, character, act, item, -cost, 0, None, True)

        else:
            return await ctx.respond(embed=ErrorEmbed(description="Invalid currency selection"))

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))

    @log_commands.command(
        name="sell",
        description="Logs the sale of an item from a player. Not for player establishment sales"
    )
    async def sell_log(self, ctx: ApplicationContext,
                       player: Option(Member, description="Player who bought the item", required=True),
                       item: Option(str, description="The item being sold", required=True),
                       cost: Option(int, description="The cost of the item", min_value=0, max_value=9999999,
                                    required=True),
                       currency: Option(str, description="Credits or Chain Codes. Default: Credits",
                                        choices=['Credits', 'CC'], default="Credits", required=False)):
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        act = ctx.bot.compendium.get_object("c_activity", "SELL")

        if currency == "Credits":
            log_entry: DBLog = await create_logs(ctx, character, act, item, 0, cost)
        elif currency == "CC":
            log_entry: DBLog = await create_logs(ctx, character, act, item, cost,0,None,True)
        else:
            return await ctx.respond(embed=ErrorEmbed(description="Invalid currency selection"))

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))

    @log_commands.command(
        name="convert",
        description="Convert CC to credits or visa versa"
    )
    async def log_convert(self, ctx: ApplicationContext,
                          player: Option(Member, description="Player doing the conversion", required=True),
                          cc: Option(int, description="Amount of Chain Codes to convert", required=True),
                          to_credits: Option(bool, description="Converting CC to credits. Default = True",
                                             default=True, required=False)):
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        act = ctx.bot.compendium.get_object("c_activity", "CONVERSION")
        conversion = ctx.bot.compendium.get_object("c_code_conversion", character.level)

        credits = cc * conversion.value

        if to_credits:
            if character.cc < cc:
                return await ctx.respond(embed=ErrorEmbed(
                    description=f"{player.mention} doesn't have enough Chain Codes for this conversion. "
                                f"Requires {str(cc)} cc"))
            else:
                log_entry: DBLog = await create_logs(ctx, character, act, "Converting CC to Credits", -cc, credits, None, True)
        else:
            if character.credits < credits:
                return await ctx.respond(embed=ErrorEmbed(
                    description=f"{player.mention} doesn't have enought credits for this conversion. "
                                f"Requires {credits} credits"))
            else:
                log_entry: DBLog = await create_logs(ctx, character, act, "Converting Credits to CC", cc, -credits)

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))

    @log_commands.command(
        name="stats",
        description="Log statistics for a character"
    )
    @commands.check(is_admin)
    async def log_stats(self, ctx: ApplicationContext,
                        player: Option(Member, description="Player to view stats for", required=True)):
        await ctx.defer()

        player: Member = player

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)
        stats = []
        await get_character_stats(ctx.bot, character, stats)

        embed = Embed(title=f"Log Statistics for {character.name}")
        embed.set_thumbnail(url=player.display_avatar.url)

        for data in stats:
            ch = data['char']
            embed.add_field(name=f"Log Statistics for {ch.name}",
                            value=f"**Starting CC**: {data['cc_init']}\n"
                                  f"**Earned CC**: {data['cc_add']}\n"
                                  f"**Spent CC**: {data['cc_minus']}\n"
                                  f"**Total CC**: {data['cc_init']+data['cc_add']+data['cc_minus']}\n"
                                  f"**Total Logs**: {data['total']}",
                            inline=False)

            if len(data['adventures']) > 0:
                ad_str = '\n'.join(f"{x.name}{'*' if x.end_ts != None else ''}" for x in data['adventures'])
                embed.add_field(name=f"Adventures for {ch.name} (* = Closed)",
                                value=f"{ad_str}")


        await ctx.respond(embed=embed)



