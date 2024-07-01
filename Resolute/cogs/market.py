import logging
import math

from discord import ApplicationContext, SlashCommandGroup, RawReactionActionEvent
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI, DENIED_EMOJI, EDIT_EMOJI
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log
from Resolute.helpers.market import get_market_request
from Resolute.helpers.players import get_player
from Resolute.models.categories.categories import CodeConversion
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.views.market import MarketPromptUI, TransactionPromptUI


log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    # bot.add_cog(Market(bot))
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
                
