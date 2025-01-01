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
from Resolute.helpers.messages import get_char_name_from_message, get_player_from_say_message
from Resolute.models.categories.categories import CodeConversion
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.arenas import ArenaPost
from Resolute.models.objects.exceptions import G0T0Error, TransactionError
from Resolute.models.views.arena_view import ArenaRequestCharacterSelect
from Resolute.models.views.character_view import RPPostUI, SayEditModal
from Resolute.models.views.market import TransactionPromptUI
from Resolute.models.views.messages import MessageLogUI

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
                                    raise G0T0Error(f"Transaction was previously denied. Please make a new request")
                                
                if transaction.player.id != ctx.author.id:
                    raise G0T0Error("You can only edit your own transactions")
                
                await message.add_reaction(EDIT_EMOJI[0])
                ui = TransactionPromptUI.new(self.bot, transaction.player.member, transaction.player, transaction)
                await ui.send_to(ctx.author)

        # Arena Board
        elif guild.arena_board_channel and message.channel.id == guild.arena_board_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")
            elif len(player.characters) <= 1:
                raise G0T0Error(f"There is nothing to edit")
            
            post = ArenaPost(player)
            post.message = message

            ui = ArenaRequestCharacterSelect.new(self.bot, ctx.author, player, post)
            await ui.send_to(ctx.author)

        # RP Post
        elif guild.rp_post_channel and message.channel.id == guild.rp_post_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this roleplay board post")
            
            ui = RPPostUI.new(self.bot, ctx.author, player, message)
            await ui.send_to(ctx.author)            
            
        # Character Say 
        elif is_player_say_message(player, message):
            modal = SayEditModal(self.bot, message)
            return await ctx.send_modal(modal) 
        else:
            raise G0T0Error("This message cannot be edited")
        
        await ctx.delete()

    @commands.message_command(
        name="Delete"
    )
    async def message_delete(self, ctx: discord.ApplicationContext, message: discord.Message):
        guild = await get_guild(self.bot, ctx.guild.id)
        player = await get_player(self.bot, ctx.author.id, guild.id)

        # Arena Board
        if guild.arena_board_channel and message.channel.id == guild.arena_board_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")

            await message.delete()

        # RP Post
        elif guild.rp_post_channel and message.channel.id == guild.rp_post_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this roleplay board post")
            
            await message.delete()

        # Character Say
        elif is_player_say_message(player, message):
            if not guild.is_dev_channel(ctx.channel):
                if (player := await get_player_from_say_message(self.bot, message)) and (char := next((c for c in player.characters if c.name ==  get_char_name_from_message(message)), None)):
                    await player.update_post_stats(self.bot, char, message, retract=True)
                await update_activity_points(self.bot, player, guild, False)
            await message.delete()

        # Staff Say Delete
        elif message.author.bot and is_staff and (orig_player := await get_player_from_say_message(self.bot, message)):
            if not guild.is_dev_channel(ctx.channel):
                await update_activity_points(self.bot, orig_player, guild, False)
                if (char := next((c for c in orig_player.characters if c.name == get_char_name_from_message(message)), None)):
                    await orig_player.update_post_stats(self.bot, char, message, retract=True)
            await message.delete()

        # Adventure NPC
        elif (adventure := await get_adventure_from_category(self.bot, ctx.channel.category.id)) and ctx.author.id in adventure.dms and is_adventure_npc_message(adventure, message):
            if not guild.is_dev_channel(ctx.channel):
                await update_activity_points(self.bot, player, guild, False)
                if npc := next((npc for npc in adventure.npcs if npc.name.lower() == message.author.name.lower()), None):
                    await player.update_post_stats(self.bot, npc, message, retract=True)
            await message.delete()
        
        else:
            raise G0T0Error("This message cannot be deleted")

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
                    
                    await message.edit(content=None, embed=LogEmbed(log_entry, ctx.author, transaction.player.member, transaction.character, True))

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
                            
                            await guild.market_channel.send(embed=LogEmbed(converted_entry, ctx.author, transaction.player.member, transaction.character, True), delete_after=5)

                    await message.add_reaction(APPROVAL_EMOJI[0])

                    log_entry = await create_log(self.bot, ctx.author, "BUY", transaction.player,
                                                    character=transaction.character,
                                                    notes=transaction.log_notes,
                                                    cc=-transaction.cc,
                                                    credits=-transaction.credits,
                                                    ignore_handicap=True)
                    
                    await message.edit(content="", embed=LogEmbed(log_entry, ctx.author, transaction.player.member, transaction.character, True))

        elif guild.staff_role and guild.staff_role.mention in message.content and len(message.mentions) > 0:
            ui = await MessageLogUI.new(self.bot, ctx.author, message)
            await ui.send_to(ctx)
        
        else:
            raise G0T0Error("Nothing to approve here. Move along.")
        
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