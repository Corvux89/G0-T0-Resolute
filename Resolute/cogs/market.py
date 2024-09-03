import logging
import math

from discord import ApplicationContext, SlashCommandGroup, RawReactionActionEvent
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI, BOT_OWNERS, DENIED_EMOJI, EDIT_EMOJI, NULL_EMOJI
from Resolute.helpers.general_helpers import confirm, is_admin
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log
from Resolute.helpers.market import get_market_log, get_market_request
from Resolute.helpers.players import get_player
from Resolute.models.categories.categories import CodeConversion
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects import TempCtx
from Resolute.models.objects.logs import upsert_log
from Resolute.models.views.market import MarketPromptUI, TransactionPromptUI


log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Market(bot))
    pass

class Market(commands.Cog):
    bot: G0T0Bot
    market_commands = SlashCommandGroup("market", "Market commands")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Market\' loaded')

    @market_commands.command(
        name="request",
        description="Setup a market request"
    )
    async def market_request(self, ctx: ApplicationContext):
        await ctx.defer()
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id)

        if not player.characters:
            return await ctx.respond(embed=ErrorEmbed(description=f"No character information found for {ctx.author.mention}"),
                                        ephemeral=True)

        if len(player.characters) == 1:
            ui = TransactionPromptUI.new(self.bot, ctx.author, player)
        else:
            ui = MarketPromptUI.new(self.bot, ctx.author, player)

        await ui.send_to(ctx)
        await ctx.delete()

    # Listeners
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if not hasattr(self.bot, "db") or not hasattr(self.bot, "compendium"):
            return

        guild = await get_guild(self.bot, payload.guild_id)
        if guild.market_channel and payload.channel_id == guild.market_channel.id:
            user = guild.guild.get_member(payload.user_id)

            # Approve
            if guild.archivist_role in user.roles or guild.senate_role in user.roles:
                if payload.emoji.name in APPROVAL_EMOJI:
                    message = None

                    try:
                        message = await guild.guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    except:
                        pass

                    if message and (transaction := await get_market_request(self.bot, message)):
                        if len(message.reactions) > 1:
                            for reaction in message.reactions[:-1]:
                                if reaction.emoji in DENIED_EMOJI:
                                    users = await reaction.users().flatten()
                                    for user in users:
                                        if guild.archivist_role in user.roles or guild.senate_role in user.roles or user.id == self.bot.user.id:
                                            await message.clear_reaction(payload.emoji)
                                            return await guild.market_channel.send(embed=ErrorEmbed(description=f"Transaction was previously denied. Either clear reactions, or make a new request"), delete_after=5)
                        if transaction.type.value != "Sell Items":
                            if transaction.player.cc - transaction.cc < 0:
                                await message.clear_reactions()
                                await message.add_reaction(DENIED_EMOJI[0])
                                return await guild.market_channel.send(embed=ErrorEmbed(description=f"{transaction.player.member.mention} cannot afford the {transaction.cc:,} CC cost."), delete_after=5)

                            if transaction and (activity := self.bot.compendium.get_activity("BUY")):
                                if transaction.credits > 0 and transaction.character.credits-transaction.credits < 0:
                                    rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, transaction.character.level)
                                    convertedCC = math.ceil((abs(transaction.credits) - transaction.character.credits) / rate.value)
                                    if transaction.player.cc < convertedCC:
                                        return await guild.market_channel.send(embed=ErrorEmbed(description=f"{transaction.character.name} cannot afford the {transaction.credits:,} credit cost or to convert the {convertedCC:,} needed."), delete_after=5)

                                    if convert_activity := self.bot.compendium.get_activity("CONVERSION"):
                                        converted_entry  = await create_log(self.bot, user, guild, convert_activity, transaction.player,
                                                                            character=transaction.character,
                                                                            notes=transaction.log_notes,
                                                                            cc=-convertedCC,
                                                                            credits=convertedCC*rate.value,
                                                                            ignore_handicap=True)
                                        
                                        await guild.market_channel.send(embed=LogEmbed(converted_entry, user, transaction.player.member, transaction.character, True), delete_after=5)

                                log_entry = await create_log(self.bot, user, guild, activity, transaction.player,
                                                            character=transaction.character,
                                                            notes=transaction.log_notes,
                                                            cc=-transaction.cc,
                                                            credits=-transaction.credits,
                                                            ignore_handicap=True)
                                await message.edit(content=None, embed=LogEmbed(log_entry, user, transaction.player.member, transaction.character, True))
                        elif activity := self.bot.compendium.get_activity("SELL"):
                            log_entry = await create_log(self.bot, user, guild, activity, transaction.player,
                                                         character=transaction.character,
                                                         notes=transaction.log_notes,
                                                         cc=transaction.cc,
                                                         credits=transaction.credits,
                                                         ignore_handicap=True)
                            await message.edit(content=None, embed=LogEmbed(log_entry, user, transaction.player.member, transaction.character, True))

            # Null
            if (guild.senate_role in user.roles or user.id in BOT_OWNERS) and payload.emoji.name in NULL_EMOJI:

                message = None
                try:
                    message = await guild.guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                except:
                    pass

                if message and (log_entry := await get_market_log(self.bot, message)):
                    if log_entry.invalid:
                        return await message.channel.send(f"Log [ {log_entry.id} ] has already been invalidated.", delete_after=5)

                    player = await get_player(self.bot, log_entry.player_id, guild.id)
                    if log_entry.character_id:
                        character = next((c for c in player.characters if c.id == log_entry.character_id), None)
                    else:
                        character = None

                    ctx = TempCtx(message.channel, self.bot, user)
                        
                    conf = await confirm(ctx,
                            f"Are you sure you want to nullify the `{log_entry.activity.value}` log"
                            f" for {player.member.display_name} {f'[ Character: {character.name} ]' if character else ''} "
                            f" for {log_entry.cc} chain codes, {log_entry.credits} credits\n"
                            f"(Reply with yes/no)", True, self.bot)

                    if conf is None:
                        return await message.channel.send(f"Times out waiting for a response or invalid response.", delete_after=5)
                    elif not conf:
                        return await message.channel.send(f"Ok, cancelling.", delete_after=5)
                    
                    reason = await confirm(ctx, f"What is the reason for nulling the log?", True, self.bot, response_check=None)
                    
                    if activity := self.bot.compendium.get_activity("MOD"):
                        if log_entry.created_ts > guild._last_reset and log_entry.activity.diversion:
                            player.div_cc -= log_entry.cc
                    
                        note = f"{log_entry.activity.value} log # {log_entry.id} nulled by "\
                                f"{ctx.author} for reason: {reason}"

                        mod_log = await create_log(self.bot, ctx.author, guild, activity, player,
                                                    character=character,
                                                    notes=note,
                                                    cc=-log_entry.cc,
                                                    credits=-log_entry.credits,
                                                    ignore_handicap=True)
                        log_entry.invalid = True

                        async with self.bot.db.acquire() as conn:
                            await conn.execute(upsert_log(log_entry))

                        await message.channel.send(content=None, embed=LogEmbed(mod_log, user, player.member, character))         

            # Edit
            if payload.emoji.name in EDIT_EMOJI:
                message = None
                try:
                    message = await guild.guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                except:
                    pass

                if message and (transaction := await get_market_request(self.bot, message)):
                    if len(message.reactions) > 1:
                        for reaction in message.reactions[:-1]:
                            if reaction.emoji in DENIED_EMOJI:
                                users = await reaction.users().flatten()
                                for user in users:
                                    if guild.archivist_role in user.roles or guild.senate_role in user.roles or user.id == self.bot.user.id:
                                        await message.clear_reaction(payload.emoji)
                                        return await guild.market_channel.send(embed=ErrorEmbed(description=f"Transaction was previously denied. Please make a new request"), delete_after=5)
                    
                    if transaction.player.member.id != payload.user_id:
                        return

                    if message.thread is None:
                        thread = await message.create_thread(name=f"{transaction.player.member.display_name}", auto_archive_duration=10080)
                    else:
                        thread = message.thread

                    ui = TransactionPromptUI.new(self.bot, transaction.player.member, transaction.player, transaction)
                    await ui.send_to(thread)
                

