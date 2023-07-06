from discord import *
from discord.ext import commands
from Resolute.bot import G0T0Bot
from Resolute.helpers import confirm, get_all_players, get_global, get_player, \
    get_character, create_logs, close_global
from Resolute.models.db_objects import GlobalEvent, GlobalPlayer, PlayerCharacter
from Resolute.models.embeds import GlobalEmbed
from discord.commands import SlashCommandGroup
from Resolute.models.schemas import GlobalPlayerSchema
from Resolute.queries import insert_new_global_event, update_global_event, \
    add_global_player, update_global_player

log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(GlobalEvents(bot))


# TODO: Add command to mass alter modifier based on # of messages
class GlobalEvents(commands.Cog):
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    global_event_commands = SlashCommandGroup("global_event", "Commands related to global event management.")

    def __init__(self, bot):
        self.bot = bot

        log.info(f'Cog \'Global\' loaded')

    @global_event_commands.command(
        name="new_event",
        description="Create a new global event",
    )
    async def gb_new(self, ctx: ApplicationContext,
                     gname: Option(str, description="Global event name", required=True),
                     cc: Option(int, description="Base cc for the event", required=True)):
        """
        Create a new global event

        :param ctx: Context
        :param gname: GlobalEvent name
        :param gold: GlobalEvent base gold
        :param xp: GlobalEvent base xp
        :param combat: Whether the GlobalEvent is combat focused, if false then RP focused
        :param mod: Default GlobalModifier for the event
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is not None:
            return await ctx.respond(f'Error: Already an active global event', ephemeral=True)

        g_event = GlobalEvent(guild_id=ctx.guild_id, name=gname, base_cc=cc, channels=[])

        async with self.bot.db.acquire() as conn:
            await conn.execute(insert_new_global_event(g_event))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, []))

    @global_event_commands.command(
        name="update_event",
        description="Change global event defaults"
    )
    async def gb_update(self, ctx: ApplicationContext,
                        gname: Option(str, description="Global event name", required=False),
                        cc: Option(int, description="Base cc for the event", required=False)):
        """
        Updates a GlobalEvent's information

        :param ctx: Context
        :param gname: GlobalEvent name
        :param gold: GlobalEvent.base_gold
        :param xp: GlobalEvent.base_xp
        :param mod: GlobalEvent.base_mod
        :param combat: Boolean whether the global is combat focused, if false assumed RP focused.
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        elif gname is None and cc is None:
            return await ctx.respond(f'Error: Nothing given to update', ephemeral=True)

        if gname is not None:
            g_event.name = gname

        if cc is not None:
            g_event.base_cc = cc

        async with self.bot.db.acquire() as conn:
            await conn.execute(update_global_event(g_event))

        if cc is not None:
            players = await get_all_players(ctx.bot, ctx.guild_id)
            if players is not None:
                for p in players:
                    if p.active and p.update:
                        p.cc = g_event.base_cc

                        async with self.bot.db.acquire() as conn:
                            await conn.execute(update_global_player(p))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, players))

    #
    @global_event_commands.command(
        name="purge_event",
        description="Purge all global event currently staged"
    )
    async def gb_purge(self, ctx: ApplicationContext):
        """
        Clears out the currently stages GlobalEvent and GlobalPlayer

        :param ctx: Context
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        to_end = await confirm(ctx, "Are you sure you want to close this global without logging? (Reply with yes/no)", True)

        if to_end is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not to_end:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)

        await close_global(ctx.bot.db, g_event.guild_id)

        embed = Embed(title="Global purge")
        embed.set_footer(text="Sickness must be purged!")
        embed.set_image(url="https://cdn.discordapp.com/attachments/987038574245474304/1022686290908561408/unknown.png")

        await ctx.respond(embed=embed)

    @global_event_commands.command(
        name="scrape",
        description="Scrapes a channel and adds the non-bot users to the global event"
    )
    async def gb_scrape(self, ctx: ApplicationContext,
                        channel: Option(TextChannel, description="Channel to pull players from", required=True)):
        """
        Scrapes over a channel adding non-bot players to the GlobalEvent and gathering statistics

        :param ctx: Context
        :param channel: TextChannel to scrape
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        players = await get_all_players(ctx.bot, ctx.guild_id)
        messages = await channel.history(oldest_first=True, limit=600).flatten()

        for msg in messages:
            if not msg.author.bot:
                if msg.author.id in players:
                    player = players[msg.author.id]
                    player.num_messages += 1

                    if msg.channel.id not in player.channels:
                        player.channels.append(msg.channel.id)

                else:
                    player = GlobalPlayer(player_id=msg.author.id, guild_id=g_event.guild_id, cc=g_event.base_cc,
                                          update=True, active=True, num_messages=1, channels=[msg.channel.id]
                                          )
                    async with self.bot.db.acquire() as conn:
                        results = await conn.execute(add_global_player(player))
                        row = await results.first()

                    player = GlobalPlayerSchema(ctx.bot.compendium).load(row)

                players[player.player_id] = player

        if channel.id not in g_event.channels:
            g_event.channels.append(channel.id)
            async with self.bot.db.acquire() as conn:
                await conn.execute(update_global_event(g_event))

                for p in players.keys():
                    await conn.execute(update_global_player(players[p]))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(players.values())))

    @global_event_commands.command(
        name="player_update",
        description="Fine tune a player, or add a player. Will re-activate a player if previously inactive"
    )
    async def gb_user_update(self, ctx: ApplicationContext,
                             player: Option(Member, description="Player to add/modify", required=True),
                             cc: Option(int, description="Players gold Chain Codes.", required=True)):
        """
        Updates or adds a GlobalPlayer to the GlobalEvent

        :param ctx: Context
        :param player: Member
        :param mod: GlobalModifier
        :param host: HostStatus
        :param gold: Player gold
        :param xp: Player xp
        """
        await ctx.defer()

        g_event = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        g_player: GlobalPlayer = await get_player(ctx.bot, ctx.guild_id, player.id)

        if g_player is None:
            g_player = GlobalPlayer(player_id=player.id, guild_id=g_event.guild_id, cc=cc,
                                    update=True if cc == g_event.base_cc else False,
                                    active=True, num_messages=0, channels=[])

            async with self.bot.db.acquire() as conn:
                await conn.execute(add_global_player(g_player))
        else:
            g_player.cc = cc
            g_player.update = True if cc == g_event.base_cc else False
            g_player.active = True

            async with self.bot.db.acquire() as conn:
                await conn.execute(update_global_player(g_player))

        g_players = await get_all_players(ctx.bot, ctx.guild_id)

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(g_players.values())))

    @global_event_commands.command(
        name="remove",
        description="Remove a player from the global event"
    )
    async def gb_remove(self, ctx: ApplicationContext,
                        player: Option(Member, description="Player to remove from the Global Event", required=True)):
        """
        Removes a player from the GlobalEvent

        :param ctx: Context
        :param player: Member to remove
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        g_player: GlobalPlayer = await get_player(ctx.bot, ctx.guild_id, player.id)

        if g_player is None:
            await ctx.respond(f'Player is not in the current global event', ephemeral=True)

        if not g_player.active:
            await ctx.respond(f'Player is already inactive for the global', ephemeral=True)
        else:
            g_player.active = False
            async with self.bot.db.acquire() as conn:
                await conn.execute(update_global_player(g_player))

        players = await get_all_players(ctx.bot, ctx.guild_id)

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(players.values())))

    @global_event_commands.command(
        name="review",
        description="Review the currently staged global event information"
    )
    async def gb_review(self, ctx: ApplicationContext,
                        gblist: Option(bool, description="Whether to list out all players in the global", required=True,
                                       default=False)):
        """
        Review the currently staged GlobalEvent information
        :param ctx: Context
        :param gblist: Bool - List all active members
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)
        else:
            players = await get_all_players(ctx.bot, ctx.guild_id)
            await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(players.values()), gblist))

    @global_event_commands.command(
        name="commit",
        description="Commits the global rewards"
    )
    async def gb_commit(self, ctx: ApplicationContext):
        """
        Commits the GlobalEvent and creates appropriate logs.

        :param ctx: Context
        """
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        to_end = await confirm(ctx, "Are you sure you want to log this global? (Reply with yes/no)", True)

        if to_end is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not to_end:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)

        players = await get_all_players(ctx.bot, ctx.guild_id)
        fail_players = []
        log_list = []
        act = ctx.bot.compendium.get_object("c_activity", "GLOBAL")

        for p in players:
            player = players[p]
            character: PlayerCharacter = await get_character(ctx.bot, player.player_id, g_event.guild_id)
            if player.active:
                if not character:
                    fail_players.append(player)
                else:
                    log_list.append(await create_logs(ctx, character, act, g_event.name, player.cc))

        await close_global(ctx.bot.db, g_event.guild_id)

        embed = Embed(title=f"Global: {g_event.name} - has been logged")
        embed.add_field(name="**# of Entries**",
                        value=f"{len(log_list)}",
                        inline=False)

        if fail_players:
            embed.add_field(name="**Failed entries due to player not having an active character**",
                            value="\n".join([f"\u200b {p.get_name(ctx)}" for p in fail_players]))

        await ctx.respond(embed=embed)

    @global_event_commands.command(
        name="mass_adjust",
        description="Given a threshold and operator, adjust player modifiers"
    )
    async def gb_adjust(self, ctx: ApplicationContext,
                        threshold: Option(int, description="The threshold of # of messages to meet", required=True),
                        operator: Option(str,
                                         description="Above or below the threshold (Threshold is always included <= or >=",
                                         required=True, choices=["Above", "Below"]),
                        cc: Option(int, description="Chain codes to adjust players to", required=True)):
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        players = await get_all_players(ctx.bot, ctx.guild_id)

        for p in players.values():
            if p.update:
                if operator == "Above":
                    if p.num_messages >= threshold:
                        p.cc = cc
                        p.update = True if cc == g_event.base_cc else False
                elif operator == "Below":
                    if p.num_messages <= threshold:
                        p.cc = cc
                        p.update = True if cc == g_event.base_cc else False


                async with self.bot.db.acquire() as conn:
                    await conn.execute(update_global_player(p))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(players.values())))
