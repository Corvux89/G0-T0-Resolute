import logging

from discord import SlashCommandGroup, Option, ApplicationContext, Member, Role
from discord.ext import commands

from ProphetBot.helpers import get_character, create_logs, get_adventure_from_role, get_or_create_guild, get_level_cap, \
    get_log, get_character_from_char_id, confirm
from ProphetBot.bot import BpBot
from ProphetBot.models.db_objects import PlayerCharacter, Activity, DBLog, Adventure, LevelCaps, PlayerGuild
from ProphetBot.models.embeds import ErrorEmbed, HxLogEmbed, DBLogEmbed, AdventureEPEmbed
from ProphetBot.models.schemas import LogSchema, CharacterSchema
from ProphetBot.queries import get_n_player_logs, get_multiple_characters, update_adventure, update_log, update_guild, \
    update_character

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Log(bot))


class Log(commands.Cog):
    bot: BpBot
    log_commands = SlashCommandGroup("log", "Logging commands for the magewrongs")

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

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))

    @log_commands.command(
        name="bonus",
        description="Give bonus gold and/or xp to a player"
    )
    async def bonus_log(self, ctx: ApplicationContext,
                        player: Option(Member, description="Player receiving the bonus", required=True),
                        reason: Option(str, description="The reason for the bonus", required=True),
                        gold: Option(int, description="The amount of gold", default=0, min_value=0, max_value=2000),
                        xp: Option(int, description="The amount of xp", default=0, min_value=0, max_value=150)):
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

        log_entry = await create_logs(ctx, character, act, reason, gold, xp)

        await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))

    @log_commands.command(
        name="ep",
        description="Grants adventure rewards to the players of a given adventure role"
    )
    async def ep_log(self, ctx: ApplicationContext,
                     role: Option(Role, description="The adventure role to get rewards", required=True),
                     ep: Option(int, description="The number of EP to give rewards for")):
        await ctx.defer()

        adventure: Adventure = await get_adventure_from_role(ctx.bot, role.id)

        if adventure is None:
            return await ctx.respond(embed=ErrorEmbed(description=f"No adventure found for {role.mention}"),
                                     ephemeral=True)
        elif len(role.members) == 0:
            return await ctx.respond(embed=ErrorEmbed(description=f"Role {role.mention} has no members. Aborting."),
                                     ephemeral=True)

        players = [p.id for p in role.members]
        adventure.ep += ep

        char_act: Activity = ctx.bot.compendium.get_object("c_activity", "ADVENTURE")
        dm_act: Activity = ctx.bot.compendium.get_object("c_activity", "ADVENTURE_DM")
        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_adventure(adventure))
            async for row in await conn.execute(get_multiple_characters(players, ctx.guild.id)):
                if row is not None:
                    character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)
                    cap: LevelCaps = get_level_cap(character, g, ctx.bot.compendium)

                    activity = char_act if character.player_id not in adventure.dms else dm_act
                    await create_logs(ctx, character, activity, adventure.name, (cap.max_gold * activity.ratio) * ep,
                                      (cap.max_xp * activity.ratio) * ep, adventure)

        await ctx.respond(embed=AdventureEPEmbed(ctx, adventure, ep))

    @log_commands.command(
        name="null",
        description="Nullifies a log"
    )
    async def null_log(self, ctx: ApplicationContext,
                       log_id: Option(int, description="ID of the log to modify", required=True)):
        await ctx.defer()

        log_entry: DBLog = await get_log(ctx.bot, log_id)

        if log_entry is None:
            return await ctx.respond(embed=ErrorEmbed(description=f"No log found with id [ {log_id} ]"), ephemeral=True)
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
                                     f" for {character.name} for ( {log_entry.gold}gp and {log_entry.xp} xp)?"
                                     f" (Reply with yes/no)", True)

                if conf is None:
                    return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
                elif not conf:
                    return await ctx.respond(f'Ok, cancelling.', delete_after=10)

                log_entry.activity = ctx.bot.compendium.get_object("c_activity", "MOD")
                g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

                character.gold -= log_entry.gold
                character.xp -= log_entry.xp

                if log_entry.created_ts > g.last_reset:
                    g.week_xp -= log_entry.server_xp
                    if log_entry.activity.diversion:
                        character.div_gold -= log_entry.gold
                        character.div_xp -= log_entry.xp
                else:
                    g.server_xp -= log_entry.server_xp

                log_entry.xp = 0
                log_entry.gold = 0
                log_entry.server_xp = 0
                if log_entry.notes is None:
                    log_entry.notes = f"[Nulled by {ctx.author.name}#{ctx.author.discriminator}]"
                else:
                    log_entry.notes = log_entry.notes + f" [Nulled by {ctx.author.name}#{ctx.author.discriminator}]"

                async with ctx.bot.db.acquire() as conn:
                    await conn.execute(update_log(log_entry))
                    await conn.execute(update_guild(g))
                    await conn.execute(update_character(character))

                await ctx.respond(embed=DBLogEmbed(ctx, log_entry, character))
