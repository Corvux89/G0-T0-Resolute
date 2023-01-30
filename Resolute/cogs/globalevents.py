from discord import *
from discord.ext import commands
from ProphetBot.bot import BpBot
from ProphetBot.helpers import calc_amt, confirm, get_all_players, global_mod_autocomplete, get_global, get_player, \
    get_character, create_logs, close_global, global_host_autocomplete
from ProphetBot.models.db_objects import GlobalEvent, GlobalPlayer, PlayerCharacter
from ProphetBot.models.embeds import GlobalEmbed
from discord.commands import SlashCommandGroup
from ProphetBot.models.schemas import GlobalPlayerSchema
from ProphetBot.queries import insert_new_global_event, update_global_event, \
    add_global_player, update_global_player

log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(GlobalEvents(bot))


# TODO: Add command to mass alter modifier based on # of messages
class GlobalEvents(commands.Cog):
    bot: BpBot  # Typing annotation for my IDE's sake
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
                     gold: Option(int, description="Base gold for the event", required=True),
                     xp: Option(int, description="Base experience for the event", required=True),
                     combat: Option(bool, description="Indicated if this is a global event or not. If true then "
                                                      "ignores mod", required=False, default=False),
                     mod: Option(str, description="Base modifier for the event",
                                 autocomplete=global_mod_autocomplete, required=False)):
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

        if mod is None:
            mod = "Medium"

        mod = ctx.bot.compendium.get_object("c_global_modifier", mod)

        g_event = GlobalEvent(guild_id=ctx.guild_id, name=gname, base_gold=gold, base_xp=xp, base_mod=mod,
                              combat=combat, channels=[])

        async with self.bot.db.acquire() as conn:
            await conn.execute(insert_new_global_event(g_event))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, []))

    @global_event_commands.command(
        name="update_event",
        description="Change global event defaults"
    )
    async def gb_update(self, ctx: ApplicationContext,
                        gname: Option(str, description="Global event name", required=False),
                        gold: Option(int, description="Base gold for the event", required=False),
                        xp: Option(int, description="Base experience for the event", required=False),
                        mod: Option(str, description="Base modifier for the event",
                                    autocomplete=global_mod_autocomplete, required=False),
                        combat: Option(bool, description="Indicated if this is a global event or not. If true then "
                                                         "ignores mod", required=False, default=False)):
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

        elif gname is None and gold is None and xp is None and mod is None and combat is None:
            return await ctx.respond(f'Error: Nothing given to update', ephemeral=True)

        oldMod = g_event.base_mod

        if gname is not None:
            g_event.name = gname

        if gold is not None:
            g_event.base_gold = gold

        if xp is not None:
            g_event.base_xp = xp

        if mod is not None:
            g_event.base_mod = ctx.bot.compendium.get_object("c_global_modifier", mod)

        if combat is not None:
            g_event.combat = combat

        async with self.bot.db.acquire() as conn:
            await conn.execute(update_global_event(g_event))

        if gold or xp or mod or combat is not None:
            players = await get_all_players(ctx.bot, ctx.guild_id)
            if players is not None:
                for p in players:
                    if p.active and p.update:
                        bGold = g_event.base_gold if gold is None else gold
                        bExp = g_event.base_xp if xp is None else xp

                        if p.modifier == oldMod:
                            bMod = g_event.base_mod if mod is None else mod
                        else:
                            bMod = p.modifier

                        p.gold = bGold if g_event.combat else calc_amt(ctx.bot.compendium, bGold, bMod, p.host)
                        p.xp = bExp if g_event.combat else calc_amt(ctx.bot.compendium, bExp, bMod, p.host)

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
        messages = await channel.history(oldest_first=True).flatten()

        for msg in messages:
            if not msg.author.bot:
                if msg.author.id in players:
                    player = players[msg.author.id]
                    player.num_messages += 1

                    if msg.channel.id not in player.channels:
                        player.channels.append(msg.channel.id)

                else:
                    player = GlobalPlayer(player_id=msg.author.id, guild_id=g_event.guild_id,
                                          modifier=g_event.base_mod, host=None,
                                          gold=g_event.base_gold if not g_event.combat else calc_amt(
                                              ctx.bot.compendium, g_event.base_gold, g_event.base_mod),
                                          xp=g_event.base_xp if not g_event.combat else calc_amt(
                                              ctx.bot.compendium, g_event.base_xp, g_event.base_mod),
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
                             mod: Option(str, description="Players effort modifier",
                                         autocomplete=global_mod_autocomplete, required=False),
                             host: Option(str, description="Players host status",
                                          autocomplete=global_host_autocomplete, required=False),
                             gold: Option(int,
                                          description="Players gold reward. NOTE: This will disable auto-calculation "
                                                      "for a user",
                                          required=False),
                             xp: Option(int,
                                        description="Players xp reward. NOTE: This will disable auto-calculation "
                                                    "for a user",
                                        required=False)):
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

        if gold or xp is not None:
            update = False
        else:
            update = True

        if g_player is None:
            bGold = g_event.base_gold if gold is None else gold
            bExp = g_event.base_xp if xp is None else xp
            bMod = g_event.base_mod if mod is None else ctx.bot.compendium.get_object("c_global_modifier", mod)
            bHost = None if host is None else ctx.bot.compendium.get_object("c_host_status", host)

            g_player = GlobalPlayer(player_id=player.id, guild_id=g_event.guild_id, modifier=bMod, host=bHost,
                                    gold=calc_amt(ctx.bot.compendium, bGold, bMod, bHost) if update else bGold,
                                    xp=calc_amt(ctx.bot.compendium, bExp, bMod, bHost) if update else bGold,
                                    update=update, active=True, num_messages=0, channels=[])

            async with self.bot.db.acquire() as conn:
                await conn.execute(add_global_player(g_player))
        else:
            bGold = g_event.base_gold if gold is None else gold
            bExp = g_event.base_xp if xp is None else xp
            bMod = g_event.base_mod if mod is None else ctx.bot.compendium.get_object("c_global_modifier", mod)
            bHost = None if host is None else ctx.bot.compendium.get_object("c_host_status", host)

            g_player.gold = calc_amt(ctx.bot.compendium, bGold, bMod, bHost) if update and not g_event.combat else bGold
            g_player.xp = calc_amt(ctx.bot.compendium, bExp, bMod, bHost) if update and not g_event.combat else bExp
            g_player.modifier = bMod
            g_player.host = bHost
            g_player.update = update
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
                    log_list.append(await create_logs(ctx, character, act, g_event.name, player.gold, player.xp))

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
                        mod: Option(str, description="Modifier to adjust players to",
                                    autocomplete=global_mod_autocomplete)):
        await ctx.defer()

        g_event: GlobalEvent = await get_global(ctx.bot, ctx.guild_id)

        if g_event is None:
            return await ctx.respond(f'Error: No active global event on this server', ephemeral=True)

        players = await get_all_players(ctx.bot, ctx.guild_id)
        adj_mod = ctx.bot.compendium.get_object("c_global_modifier", mod)

        for p in players.values():
            if p.update and ((p.host is not None and p.host.value.upper() != "HOSTING ONLY") or p.host is None):
                if operator == "Above":
                    if p.num_messages >= threshold:
                        p.modifier = adj_mod
                elif operator == "Below":
                    if p.num_messages <= threshold:
                        p.modifier = adj_mod

                p.gold = calc_amt(ctx.bot.compendium, g_event.base_gold, p.modifier, p.host)
                p.xp = calc_amt(ctx.bot.compendium, g_event.base_xp, p.modifier, p.host)

                async with self.bot.db.acquire() as conn:
                    await conn.execute(update_global_player(p))

        await ctx.respond(embed=GlobalEmbed(ctx, g_event, list(players.values())))

    @global_event_commands.command(
        name="help",
        description="Summary of the global event command group"
    )
    async def gb_help(self, ctx: ApplicationContext):
        embed = Embed(title=f"**Global Events Command Group Overview**")
        embed.add_field(name="**Overview of the group**",
                        value=f"This group is used to help manage and stage a global event. This will allow for the "
                              f"creation, administration, and changes to an event without actually committing. "
                              f"The primary intent is to be able to log event rewards for multiple players without "
                              f"having to do individual commands for each player\n\n"
                              f"**Only one (1) global event can be running at a time**",
                        inline=False)

        embed.add_field(name=f"**How Rewards are calculated**",
                        value=f"*Combat global* - All players and hosts receive the base gold/xp unless otherwise "
                              f"modified\n\n"
                              f"*Non-combat global* - Players will receive base gold/xp * effort modifier capped at"
                              f"a defined maximum per modifier\n"
                              f"__Modifier multipliers:__ High (1.25), Medium (1.00), Low (0.75)\n"
                              f"__Defined maximum:__ High (250), Medium (200), Low (150)\n\n"
                              f"*Hosts* - Players flagged as hosts will have different rewards\n"
                              f"__Participating__ - Player will get their participation rewards from above + 100\n"
                              f"__Hosting Only__ - Player will not participation rewards, rather the equivalent of 100 "
                              f"+ a Low effort modified reward",
                        inline=False)

        embed.add_field(name=f"Commands",
                        value=f"**new_event** - Creates a new global event\n"
                              f"**update_event** - Updates information for an event\n"
                              f"**purge_event** - Clears out the currently staged event. "
                              f"Used if there are a bunch of mistakes\n"
                              f"**scrape** - Scrapes a given channel, and adds all the non-bot users to the event"
                              f"with the default settings\n"
                              f"**player_update** - Updates a given players details, or manually add a player "
                              f"to the event\n"
                              f"**remove** - Manually removes a player from the global event\n"
                              f"**mass_adjust** - Given a threshold and operator, will adjust all players participating"
                              f"in the global to the designated modifier\n"
                              f"**review** - Shows the standard global embed with the option to list all the "
                              f"active players\n"
                              f"**commit** - Will log the event and clear it out (no need to purge after this\n"
                              f"**help** - Bruh.....",
                        inline=False)

        await ctx.respond(embed=embed)
