import logging
import math

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import (APPROVAL_EMOJI, DENIED_EMOJI, EDIT_EMOJI,
                                NULL_EMOJI)
from Resolute.helpers import (confirm, create_log, get_adventure_from_category,
                              get_guild, get_log_from_entry,
                              get_market_request, get_player, is_admin,
                              is_adventure_npc_message, is_player_say_message,
                              is_staff, update_activity_points)
from Resolute.helpers.logs import null_log
from Resolute.models.categories.categories import CodeConversion
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.arenas import ArenaPost
from Resolute.models.objects.exceptions import G0T0Error, TransactionError
from Resolute.models.objects.logs import upsert_log
from Resolute.models.views.arena_view import ArenaRequestCharacterSelect
from Resolute.models.views.character_view import SayEditModal
from Resolute.models.views.market import TransactionPromptUI

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(Messages(bot))


class Messages(commands.Cog):
    # TODO: Setup approve to work with RP/Snapshots
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
                                    raise G0T0Error(f"Transaction was previously denied. Please make a new request")
                                
                if transaction.player.id != ctx.author.id:
                    raise G0T0Error("You can only edit your own transactions")
                
                await message.add_reaction(EDIT_EMOJI[0])
                ui = TransactionPromptUI.new(self.bot, transaction.player.member, transaction.player, transaction)
                await ui.send_to(ctx.author)

        # Arena Board
        if guild.arena_board and message.channel.id == guild.arena_board.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")
            elif len(player.characters) <= 1:
                raise G0T0Error(f"There is nothing to edit")
            
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
        guild = await get_guild(self.bot, ctx.guild.id)
        player = await get_player(self.bot, ctx.author.id, guild.id)

        # Arena Board
        if guild.arena_board and message.channel.id == guild.arena_board.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")

            await message.delete()

        # Character Say
        if is_player_say_message(player, message):
            await update_activity_points(self.bot, player, guild, False)
            await message.delete()

        # Adventure NPC
        if (adventure := await get_adventure_from_category(self.bot, ctx.channel.category.id)) and ctx.author.id in adventure.dms and is_adventure_npc_message(adventure, message):
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
                                    raise G0T0Error(f"Transaction was previously denied. Please make a new request")
        
                # Selling items
                if transaction.type.value == "Sell Items":
                    await message.add_reaction(APPROVAL_EMOJI[0])
                    
                    log_entry = await create_log(self.bot, ctx.author, "SELL", transaction.player,
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
                        raise TransactionError(f"{transaction.player.member.mention} cannot afford the {transaction.cc:,} CC cost.")
                        
                    if transaction.credits > 0 and transaction.character.credits - transaction.credits < 0:
                        rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, transaction.character.level)
                        convertedCC = math.ceil((abs(transaction.credits) - transaction.character.credits) / rate.value)

                        if transaction.player.cc < convertedCC:
                            raise TransactionError(f"{transaction.character.name} cannot afford the {transaction.credits:,} credit cost or to convert the {convertedCC:,} needed.")
    
                        else: 
                            converted_entry = await create_log(self.bot, ctx.author, "CONVERSION", transaction.player,
                                                                character=transaction.character,
                                                                notes=transaction.log_notes,
                                                                cc=-convertedCC,
                                                                credits=convertedCC*rate.value,
                                                                ignore_handicap=True)
                            
                            await guild.market_channel.send(embed=LogEmbed(converted_entry, user, transaction.player.member, transaction.character, True), delete_after=5)

                    await message.add_reaction(APPROVAL_EMOJI[0])

                    log_entry = await create_log(self.bot, ctx.author, "BUY", transaction.player,
                                                    character=transaction.character,
                                                    notes=transaction.log_notes,
                                                    cc=-transaction.cc,
                                                    credits=-transaction.credits,
                                                    ignore_handicap=True)
                    
                    await message.edit(content="", embed=LogEmbed(log_entry, ctx.author, transaction.player.member, transaction.character, True))
        
        await ctx.delete()

    @commands.message_command(
        name="Null"
    )
    @commands.check(is_admin)
    async def message_null(self, ctx: discord.ApplicationContext, message: discord.Message):
        log_entry = await get_log_from_entry(self.bot, message)
        await ctx.defer()
        
        reason = await confirm(ctx, f"What is the reason for nulling the log?", True, self.bot, response_check=None)

        player = await get_player(self.bot, log_entry.player_id, log_entry.guild_id, True)
        character = next((c for c in player.characters if c.id == log_entry.character_id), None) if log_entry.character_id else None
        mod_log = await null_log(self.bot, ctx, log_entry, reason)
        

        await message.add_reaction(NULL_EMOJI[0])

        return await ctx.respond(content=None, embed=LogEmbed(mod_log, ctx.author, player.member, character))