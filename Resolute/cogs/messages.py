import logging
import math

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI, DENIED_EMOJI, EDIT_EMOJI, NULL_EMOJI
from Resolute.helpers.general_helpers import confirm, is_admin, is_staff
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log, get_log_from_entry, update_activity_points
from Resolute.helpers.market import get_market_request
from Resolute.helpers.messages import is_guild_npc_message, is_player_say_message
from Resolute.helpers.players import get_player
from Resolute.models.categories.categories import CodeConversion
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.arenas import ArenaPost
from Resolute.models.objects.logs import upsert_log
from Resolute.models.views.arena_view import ArenaRequestCharacterSelect
from Resolute.models.views.character_view import SayEditModal
from Resolute.models.views.market import TransactionPromptUI


log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Messages(bot))


class Messages(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Messages\' loaded') 

    @commands.message_command(
        name="Edit"
    )
    async def message_edit(self, ctx: discord.ApplicationContext, message: discord.Message):
        guild = await get_guild(self.bot, ctx.guild.id)
        player = await get_player(self.bot, ctx.author.id, guild.id)

        # Market
        if guild.market_channel and message.channel.id == guild.market_channel.id:
            if transaction := await get_market_request(self.bot, message):

                # Check if transaction was denied previously
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()
                            for user in users:
                                if is_staff(ctx) or user.id == self.bot.user.id:
                                    return await ctx.respond(embed=ErrorEmbed(f"Transaction was previously denied. Please make a new request"), ephemeral=True)
                                
                if transaction.player.id != ctx.author.id:
                    return await ctx.respond(embed=ErrorEmbed("You can only edit your own transactions"), ephemeral=True)
                
                await message.add_reaction(EDIT_EMOJI[0])
                ui = TransactionPromptUI.new(self.bot, transaction.player.member, transaction.player, transaction)
                await ui.send_to(ctx.author)

        # Arena Board
        if guild.arena_board and message.channel.id == guild.arena_board.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                return await ctx.respond(embed=ErrorEmbed(f"You cannot edit this arena board post"), ephemeral=True)
            elif len(player.characters) <= 1:
                return await ctx.respond(embed=ErrorEmbed(f"There is nothing for you to edit"), ephemeral=True)
            
            post = ArenaPost(player)
            post.message = message

            ui = ArenaRequestCharacterSelect.new(self.bot, ctx.author, player, post)
            await ui.send_to(ctx.author)

        # Character Say 
        if is_player_say_message(player, message):
            modal = SayEditModal(message)
            return await ctx.send_modal(modal) 

        await ctx.delete()

    @commands.message_command(
        name="Delete"
    )
    async def message_delete(self, ctx: discord.ApplicationContext, message: discord.Message):
        # TODO: Setup for adventure NPC commands as well
        guild = await get_guild(self.bot, ctx.guild.id)
        player = await get_player(self.bot, ctx.author.id, guild.id)

        # Arena Board
        if guild.arena_board and message.channel.id == guild.arena_board.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                return await ctx.respond(embed=ErrorEmbed(f"You cannot edit this arena board post"), ephemeral=True)

            await message.delete()

        # Character Say
        if is_player_say_message(player, message) or is_guild_npc_message(guild, message):
            await update_activity_points(self.bot, player, guild, False)
            await message.delete()

        await ctx.delete()

    @commands.message_command(
        name="Approve"
    )
    @commands.check(is_staff)
    async def message_approve(self, ctx: discord.ApplicationContext, message: discord.Message):
        guild = await get_guild(self.bot, ctx.guild.id)

        # Market Transactions
        if guild.market_channel and message.channel.id == guild.market_channel.id:
            if transaction := await get_market_request(self.bot, message):

                # Check if transaction was denied previously
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()
                            for user in users:
                                if is_staff(ctx) or user.id == self.bot.user.id:
                                    return await ctx.respond(embed=ErrorEmbed(f"Transaction was previously denied. Either clear reactions, or have the user make a new request"), ephemeral=True)
                # Selling items
                if transaction.type.value == "Sell Items" and (activity := self.bot.compendium.get_activity("SELL")):
                    await message.add_reaction(APPROVAL_EMOJI[0])
                    log_entry = await create_log(self.bot, ctx.author, guild, activity, transaction.player,
                                                 character=transaction.character,
                                                 notes=transaction.log_notes,
                                                 cc=transaction.cc,
                                                 credits=transaction.credits,
                                                 ignore_handicap=True) 
                    
                    await message.edit(content=None, embed=LogEmbed(log_entry, user, transaction.player.member, transaction.character, True))

                else:
                    if transaction.player.cc - transaction.cc < 0:
                        await message.clear_reactions()
                        await message.add_reaction(DENIED_EMOJI[0])
                        return await ctx.respond(embed=ErrorEmbed(f"{transaction.player.member.mention} cannot afford the {transaction.cc:,} CC cost."), ephemeral=True)
                    
                    if activity := self.bot.compendium.get_activity("BUY"):
                        
                        if transaction.credits > 0 and transaction.character.credits - transaction.credits < 0:
                            rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, transaction.character.level)
                            convertedCC = math.ceil((abs(transaction.credits) - transaction.character.credits) / rate.value)

                            if transaction.player.cc < convertedCC:
                                return await ctx.respond(embed=ErrorEmbed(f"{transaction.character.name} cannot afford the {transaction.credits:,} credit cost or to convert the {convertedCC:,} needed."), ephemeral=True)
                            elif covnerted_activity := self.bot.compendium.get_activity("CONVERSION"):
                                converted_entry = await create_log(self.bot, ctx.author, guild, covnerted_activity, transaction.player,
                                                                   character=transaction.character,
                                                                   notes=transaction.log_notes,
                                                                   cc=-convertedCC,
                                                                   credits=convertedCC*rate.value,
                                                                   ignore_handicap=True)
                                
                                await guild.market_channel.send(embed=LogEmbed(converted_entry, user, transaction.player.member, transaction.character, True), delete_after=5)

                        await message.add_reaction(APPROVAL_EMOJI[0])
                        log_entry = await create_log(self.bot, ctx.author, guild, activity, transaction.player,
                                                     character=transaction.character,
                                                     notes=transaction.log_notes,
                                                     cc=-transaction.cc,
                                                     credits=-transaction.credits,
                                                     ignore_handicap=True)
                        
                        await message.edit(content=None, embed=LogEmbed(log_entry, ctx.author, transaction.player.member, transaction.character, True))
        
        await ctx.delete()

    @commands.message_command(
        name="Null"
    )
    @commands.check(is_admin)
    async def message_null(self, ctx: discord.ApplicationContext, message: discord.Message):
        guild = await get_guild(self.bot, ctx.guild.id)

        if log_entry := await get_log_from_entry(self.bot, message):
            if log_entry.invalid:
                return await ctx.respond(embed=ErrorEmbed(f"Log [ {log_entry.id} ] has already been invalidated."), ephemeral=True)
            
            player = await get_player(self.bot, log_entry.player_id, guild.id)
            character = next((c for c in player.characters if c.id == log_entry.character_id), None) if log_entry.character_id else None
            await ctx.defer()

            conf = await confirm(ctx,
                                 f"Are you sure you want to nullify the `{log_entry.activity.value}` log"
                                 f" for {player.member.display_name} {f'[Character: {character.name} ]' if character else ''} "
                                 f" for {log_entry.cc} chain codes, {log_entry.credits} credits\n"
                                 f"(Reply with yes/no)", True, self.bot)
            
            if conf is None:
                return await ctx.respond(f"Timed out waiting for a response or invalid response.", ephemeral=True)
            elif not conf:
                return await ctx.respond(f"Ok, cancelling.", ephemeral=True)
            
            reason = await confirm(ctx, f"What is the reason for nulling the log?", True, self.bot, response_check=None)

            if activity := self.bot.compendium.get_activity("MOD"):
                if log_entry.created_ts > guild._last_reset and log_entry.activity.diversion:
                    player.div_cc = max(player.div_cc - log_entry.cc, 0)

                note = (f"{log_entry.activity.value} log # {log_entry.id} nulled by "
                        f"{ctx.author} for reason: {reason}")
                
                mod_log = await create_log(self.bot, ctx.author, guild, activity, player,
                                           character=character,
                                           notes=note,
                                           cc=-log_entry.cc,
                                           credits=-log_entry.credits,
                                           ignore_handicap=True)
                
                log_entry.invalid = True

                await message.add_reaction(NULL_EMOJI[0])

                async with self.bot.db.acquire() as conn:
                    await conn.execute(upsert_log(log_entry))

                return await ctx.respond(content=None, embed=LogEmbed(mod_log, ctx.author, player.member, character))
        
        await ctx.delete()