import logging
import re

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import (ACTIVITY_POINT_MINIMUM, APPROVAL_EMOJI, DENIED_EMOJI, EDIT_EMOJI,
                                NULL_EMOJI)
from Resolute.helpers.general_helpers import confirm, is_admin, is_staff
from Resolute.helpers.market import get_market_request
from Resolute.helpers.messages import get_char_name_from_message, get_player_from_say_message, is_adventure_npc_message, is_player_say_message
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.applications import ArenaPost
from Resolute.models.objects.exceptions import G0T0Error, LogNotFound
from Resolute.models.objects.logs import DBLog
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
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id)

        # Market
        if player.guild.market_channel and message.channel.id == player.guild.market_channel.id:
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
        elif player.guild.arena_board_channel and message.channel.id == player.guild.arena_board_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")
            elif len(player.characters) <= 1 and player.guild.member_role and player.guild.member_role not in player.member.roles:
                raise G0T0Error(f"There is nothing to edit")
            
            post = ArenaPost(player)
            post.message = message

            ui = ArenaRequestCharacterSelect.new(self.bot, player, post)
            await ui.send_to(ctx.author)

        # RP Post
        elif player.guild.rp_post_channel and message.channel.id == player.guild.rp_post_channel.id:
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
        player = await self.bot.get_player(ctx.author.id, ctx.guild.id)

        # Arena Board
        if player.guild.arena_board_channel and message.channel.id == player.guild.arena_board_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this arena board post")

            await message.delete()

        # Market
        elif player.guild.market_channel and message.channel.id == player.guild.market_channel.id:
            if transaction := await get_market_request(self.bot, message):
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()

                            for user in users:
                                if is_staff(ctx) or user.id == self.bot.user.id:
                                    raise G0T0Error(f"Transaction was previously denied. Please make a new request")
                
                if transaction.player.id != ctx.author.id:
                    raise G0T0Error("You can only edit your own transactions")
                
                await message.delete()

        # RP Post
        elif player.guild.rp_post_channel and message.channel.id == player.guild.rp_post_channel.id:
            if not message.author.bot or message.embeds[0].footer.text != f"{ctx.author.id}":
                raise G0T0Error("You cannot edit this roleplay board post")
            
            await message.delete()

        # Character Say
        elif is_player_say_message(player, message):
            if not player.guild.is_dev_channel(ctx.channel):
                if (char := next((c for c in player.characters if c.name ==  get_char_name_from_message(message)), None)):
                    await player.update_post_stats(char, message, retract=True)
                if len(message.content) >= ACTIVITY_POINT_MINIMUM:
                    await self.bot.update_player_activity_points(player, False)
            await message.delete()

        # Staff Say Delete
        elif message.author.bot and is_staff and (orig_player := await get_player_from_say_message(self.bot, message)):
            if not player.guild.is_dev_channel(ctx.channel):
                if len(message.content) >= ACTIVITY_POINT_MINIMUM:
                    await self.bot.update_player_activity_points(orig_player, False)
                if (char := next((c for c in orig_player.characters if c.name == get_char_name_from_message(message)), None)):
                    await orig_player.update_post_stats(char, message, retract=True)
            await message.delete()

        # Adventure NPC
        elif ctx.channel.category and (adventure := await self.bot.get_adventure_from_category(ctx.channel.category.id)) and ctx.author.id in adventure.dms and is_adventure_npc_message(adventure, message):
            if not player.guild.is_dev_channel(ctx.channel):
                if len(message.content) >= ACTIVITY_POINT_MINIMUM:
                    await self.bot.update_player_activity_points(player, False)
                if npc := next((npc for npc in adventure.npcs if npc.name.lower() == message.author.name.lower()), None):
                    await player.update_post_stats(npc, message, retract=True)
            await message.delete()

        # Global NPC
        elif message.author.bot and (npc := next((n for n in player.guild.npcs if n.name == message.author.name), None)):
            if not player.guild.is_dev_channel(ctx.channel):
                if len(message.content) >= ACTIVITY_POINT_MINIMUM:
                    await self.bot.update_player_activity_points(player, False)
                                    
                await player.update_post_stats(npc, message, retract=True)

            await message.delete()
        
        else:
            raise G0T0Error("This message cannot be deleted")

        await ctx.delete()

    @commands.message_command(
        name="Approve"
    )
    @commands.check(is_staff)
    async def message_approve(self, ctx: discord.ApplicationContext, message: discord.Message):
        guild = await self.bot.get_player_guild(ctx.guild.id)

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
                    log_entry = await self.bot.log(ctx, transaction.player, ctx.author, "SELL",
                                                   character=transaction.character,
                                                   notes=transaction.log_notes,
                                                   cc=transaction.cc,
                                                   credits=transaction.credits,
                                                   ignore_handicap=True,
                                                   show_values=True,
                                                   silent=True)                    
                    await message.edit(content=None, embed=LogEmbed(log_entry, True))

                else:
                    try:
                        log_entry = await self.bot.log(ctx, transaction.player, ctx.author, "BUY",
                                                       character=transaction.character,
                                                       notes=transaction.log_notes,
                                                       cc=-transaction.cc,
                                                       credits=-transaction.credits,
                                                       show_values=True,
                                                       ignore_handicap=True)
                        await message.add_reaction(APPROVAL_EMOJI[0])
                        await message.edit(content="", embed=LogEmbed(log_entry, True))
                    except Exception as error:
                        await message.clear_reactions
                        await message.add_reaction(DENIED_EMOJI[0])
                        raise error                    

        # RP
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
        await ctx.defer()
        log_entry = await self._get_log_from_entry(message)
        
        reason = await confirm(ctx, f"What is the reason for nulling the log?", True, self.bot, response_check=None)
        await log_entry.null(ctx, reason)        
        await message.add_reaction(NULL_EMOJI[0])
        
    
    # --------------------------- #
    # Private Methods
    # --------------------------- #
    async def _get_log_from_entry(self, message: discord.Message) -> DBLog:
        try:
            embed = message.embeds[0]
            log_id = self._get_match(f"ID:\s*(\d+)", embed.footer.text)

            log_entry = await self.bot.get_log(log_id)

        except:
            raise LogNotFound()

        return log_entry
    
    def _get_match(self, pattern, text, group=1, default=None):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(group) if match and match.group(group) != 'None' else default