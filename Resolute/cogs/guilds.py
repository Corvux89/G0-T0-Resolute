import datetime

import discord
from discord import *
from Resolute.bot import G0T0Bot
from discord.ext import commands, tasks
from timeit import default_timer as timer
from Resolute.helpers import get_or_create_guild, get_weekly_stipend, create_logs, \
    get_guild_character_summary_stats, get_level_cap
from Resolute.models.embeds import GuildEmbed, GuildStatus
from Resolute.models.schemas import CharacterSchema, RefWeeklyStipendSchema, GuildSchema
from Resolute.queries import update_guild, get_characters, update_character, insert_weekly_stipend, \
    update_weekly_stipend, delete_weekly_stipend, get_guild_weekly_stipends, get_multiple_characters, \
    get_guilds_with_reset
from Resolute.models.db_objects import PlayerGuild, PlayerCharacter, RefWeeklyStipend, LevelCaps

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))


class Guilds(commands.Cog):
    bot: G0T0Bot
    guilds_commands = SlashCommandGroup("guild", "Commands related to guild specific settings")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Guilds\' loaded')

    @commands.Cog.listener()
    async def on_compendium_loaded(self):
        if not self.schedule_weekly_reset.is_running():
            asyncio.ensure_future(self.schedule_weekly_reset.start())

    @guilds_commands.command(
        name="max_reroll",
        description="Set the max number of character rerolls. Default is 1"
    )
    async def set_max_reroll(self, ctx: ApplicationContext,
                             amount: Option(int, description="Max number of rerolls allowed", required=True,
                                            default=1)):
        """
        Used to set the max number of rerolls allowed on a guild

        :param ctx: Context
        :param amount: Max number of rerolls allowed
        """

        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        g.max_reroll = amount
        async with self.bot.db.acquire() as conn:
            await conn.execute(update_guild(g))

        await ctx.respond(embed=GuildEmbed(ctx, g))

    @guilds_commands.command(
        name="max_level",
        description="Set the maximum character level for the server. Default is 3"
    )
    async def set_max_level(self, ctx: ApplicationContext,
                            amount: Option(int, description="Max character level", required=True,
                                           default=3)):
        """
        Used to set the maximum character level for a guild

        :param ctx: Context
        :param amount: Max character level
        """

        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)
        g.max_level = amount
        async with self.bot.db.acquire() as conn:
            await conn.execute(update_guild(g))

        await ctx.respond(embed=GuildEmbed(ctx, g))

    @guilds_commands.command(
        name="status",
        description="Gets the current server's settings/status"
    )
    async def guild_status(self, ctx: ApplicationContext,
                           display_inactive: Option(bool, description="Display inactive players",
                                                    required=False,
                                                    default=False)):
        """
        Displays the current server's/Guilds status

        :param ctx: Context
        :param display_inactive: Display the inactive players (defined by no logs in the past two weeks)
        """
        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        total, inactive = await get_guild_character_summary_stats(ctx.bot, ctx.guild_id)

        await ctx.respond(embed=GuildStatus(ctx, g, total, inactive, display_inactive))

    @guilds_commands.command(
        name="add_stipend",
        description="Add/modify a role in the stipend list for weekly resets"
    )
    async def stipend_add(self, ctx: ApplicationContext,
                          role: Option(Role, description="Role to give a stipend for", required=True),
                          amount: Option(float, description="Amount of the stipend in Chain Codes", required=True),
                          reason: Option(str, description="Reason for the stipend", required=False),
                          leadership: Option(bool, description="Note if this is a leadership stipend. "
                                                               "These will not stack", required=False, default=False)):
        """
        Add/modify a stipend for a server

        :param ctx: Context
        :param role: Role for stipend
        :param amount: Ratio of weekly cap for the stipend
        :param reason: Reason for the stipend
        :param leadership: Whether or not this stipend is for a leadership position
        """
        await ctx.defer()

        stipend: RefWeeklyStipend = await get_weekly_stipend(ctx.bot.db, role)

        if stipend is None:
            stipend = RefWeeklyStipend(role_id=role.id, amount=amount, guild_id=ctx.guild_id, reason=reason,
                                       leadership=leadership)
            async with ctx.bot.db.acquire() as conn:
                await conn.execute(insert_weekly_stipend(stipend))
        elif stipend.guild_id != ctx.guild_id:
            return await ctx.respond(f"Error: Stipend is not for this server")
        else:
            stipend.amount = amount
            stipend.reason = stipend.reason if reason is None else reason
            stipend.leadership = leadership
            async with ctx.bot.db.acquire() as conn:
                await conn.execute(update_weekly_stipend(stipend))

        await ctx.respond(f"Stipend for @{role.name} for {stipend.amount} chain codes added/updated")

    @guilds_commands.command(
        name="remove_stipend",
        description="Remove a stipend"
    )
    async def stipend_remove(self, ctx: ApplicationContext,
                             role: Option(Role, description="Role to remove stipend for", required=True)):
        """
        Removes a stipend

        :param ctx: Context
        :param role: Role to remove stipend for
        """
        await ctx.defer()

        stipend: RefWeeklyStipend = await get_weekly_stipend(ctx.bot.db, role)

        if stipend is None:
            return await ctx.respond(f"No stipend for the given role")
        elif stipend.guild_id != ctx.guild_id:
            return await ctx.respond(f"Error: Stipend is not for this server")
        else:
            async with ctx.bot.db.acquire() as conn:
                await conn.execute(delete_weekly_stipend(stipend))

        return await ctx.respond(f"Stipend for {role.mention} removed", ephemeral=True)

    @guilds_commands.command(
        name="set_handicap",
        description="Set the handicap of CC's a player should get to help catchup"
    )
    async def set_handicap(self, ctx: ApplicationContext,
                           handicap: Option(int, description="Servicer handicap", required=True)):

        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        g.handicap_cc = handicap

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_guild(g))

        return await ctx.respond(embed=GuildEmbed(ctx, g))

    @guilds_commands.command(
        name="schedule_reset",
        description="Schedules the weekly reset"
    )
    async def schedule_reset(self, ctx: ApplicationContext,
                             day_of_week: Option(str, description="Day of week for the reset", required=True,
                                                 choices=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                                                          "Saturday", "Sunday", "None"]),
                             hour: Option(int, description="Hour to do the reset in UTC time",
                                          required=True, min_value=0, max_value=23)):
        """
        Sets up the schedule for weekly resets

        :param ctx: Context
        :param day_of_week: Day of the week
        :param hour: Hour in UTC time
        """
        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        if day_of_week == "None":
            day = None
            tm = None


        else:
            if day_of_week == "Monday":
                day = 0
            elif day_of_week == "Tuesday":
                day = 1
            elif day_of_week == "Wednesday":
                day = 2
            elif day_of_week == "Thursday":
                day = 3
            elif day_of_week == "Friday":
                day = 4
            elif day_of_week == "Saturday":
                day = 5
            else:
                day = 6

            tm = hour

        g.reset_day = day
        g.reset_hour = tm

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_guild(g))

        await ctx.respond(embed=GuildEmbed(ctx, g))


    @guilds_commands.command(
        name="weekly_reset",
        description="Performs a weekly reset for the server"
    )
    async def guild_weekly_reset(self, ctx: ApplicationContext):
        """
        Manually trigger the weekly reset for a server.

        :param ctx: Context
        """
        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        await self.perform_weekly_reset(g)
        await ctx.respond("Weekly reset manually completed")

    async def perform_weekly_reset(self, g: PlayerGuild):
        """
        Primary method for performing a weekly reset for a server

        :param g: PlayerGuild
        """
        # Setup
        start = timer()
        player_cc = 0
        stipend_list = []

        # Guild updates
        g.weeks += 1
        g.last_reset = datetime.datetime.utcnow()

        # Reset weekly stats
        async with self.bot.db.acquire() as conn:
            await conn.execute(update_guild(g))
            async for row in await conn.execute(get_characters(g.id)):
                if row is not None:
                    character: PlayerCharacter = CharacterSchema(self.bot.compendium).load(row)
                    player_cc += character.div_cc
                    character.div_cc = 0
                    await conn.execute(update_character(character))

            log.info(
                f"Weekly stats for {self.bot.get_guild(g.id).name} [ {g.id} ]: "
                f"Player Chain Codes = {player_cc}")

            # Stipends
            async for row in await conn.execute(get_guild_weekly_stipends(g.id)):
                if row is not None:
                    stipend: RefWeeklyStipend = RefWeeklyStipendSchema().load(row)
                    stipend_list.append(stipend)

        if len(stipend_list) > 0:
            stipend_list.sort(key=lambda s: s.amount, reverse=True)
            act: Activity = self.bot.compendium.get_object("c_activity", "STIPEND")
            s_players = []
            for s in stipend_list:
                if stipend_role := self.bot.get_guild(g.id).get_role(s.role_id):
                    if s.leadership:
                        players = list(filter(lambda s: s not in s_players, [p.id for p in stipend_role.members]))
                    else:
                        players = [p.id for p in stipend_role.members]
                    async with self.bot.db.acquire() as conn:
                        async for row in await conn.execute(get_multiple_characters(players, g.id)):
                            if row is not None:
                                character: PlayerCharacter = CharacterSchema(self.bot.compendium).load(row)
                                if s.leadership:
                                    s_players.append(character.player_id)
                                await create_logs(self, character, act,
                                                  f"Stipend Role: {stipend_role.name} - {s.reason}",s.amount,0)
                else:
                    # Role doesn't exist....
                    async with self.bot.db.acquire() as conn:
                        await conn.execute(delete_weekly_stipend(s))

        end = timer()

        # Announce we're all done!
        if announcement_channel := discord.utils.get(self.bot.get_guild(g.id).channels, name="announcements"):
            try:
                await announcement_channel.send(content=f"Weekly reset complete in {end - start:.2f} seconds.")
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"WEEKLY RESET: Error sending message to announcements channel in "
                              f"{self.bot.get_guild(g.id).name} [ {g.id} ]")
                else:
                    log.error(error)

    # --------------------------- #
    # Task Helpers
    # --------------------------- #
    @tasks.loop(minutes=30)
    async def schedule_weekly_reset(self):
        hour = datetime.datetime.utcnow().hour
        day = datetime.datetime.utcnow().weekday()
        log.info(f"GUIlDS: Checking reset for day {day} and hour {hour}")
        async with self.bot.db.acquire() as conn:
            async for row in await conn.execute(get_guilds_with_reset(day, hour)):
                if row is not None:
                    g: PlayerGuild = GuildSchema().load(row)
                    await self.perform_weekly_reset(g)
