import logging
import re

import discord
from discord.ext import commands

from Resolute.bot import G0T0Bot, G0T0Context
from Resolute.constants import APPROVAL_EMOJI, DENIED_EMOJI, EDIT_EMOJI, NULL_EMOJI
from Resolute.helpers import confirm, is_admin, is_staff
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.enum import WebhookType
from Resolute.models.objects.market import MarketTransaction
from Resolute.models.objects.players import ArenaPost
from Resolute.models.objects.exceptions import G0T0Error, LogNotFound
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.webhook import G0T0Webhook
from Resolute.models.views.arena_view import ArenaRequestCharacterSelect
from Resolute.models.views.character_view import RPPostUI, SayEditModal
from Resolute.models.views.market import TransactionPromptUI
from Resolute.models.views.messages import MessageLogUI

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(Messages(bot))


class Messages(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'Messages' loaded")

    @commands.message_command(name="Edit")
    async def message_edit(self, ctx: G0T0Context, message: discord.Message):
        player = ctx.player

        # Market
        if (
            player.guild.market_channel
            and message.channel.id == player.guild.market_channel.id
        ):
            if transaction := await MarketTransaction.get_request(self.bot, message):
                transaction: MarketTransaction

                # Check if transaction was denied previously
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()
                            for user in users:
                                if (
                                    player.guild.is_staff(player.member)
                                    or user.id == self.bot.user.id
                                ):
                                    raise G0T0Error(
                                        f"Transaction was previously denied. Please make a new request"
                                    )

                if transaction.player.id != ctx.author.id:
                    raise G0T0Error("You can only edit your own transactions")

                await message.add_reaction(EDIT_EMOJI[0])
                ui = TransactionPromptUI.new(
                    self.bot, transaction.player.member, transaction.player, transaction
                )
                await ui.send_to(ctx.author)

        # Arena Board
        elif (
            player.guild.arena_board_channel
            and message.channel.id == player.guild.arena_board_channel.id
        ):
            if not self._is_user_the_author(ctx, message):
                raise G0T0Error("You cannot edit this arena board post")
            elif (
                len(player.characters) <= 1
                and player.guild.member_role
                and player.guild.member_role not in player.member.roles
            ):
                raise G0T0Error(f"There is nothing to edit")

            post = ArenaPost(player)
            post.message = message

            await message.add_reaction(EDIT_EMOJI[0])
            ui = ArenaRequestCharacterSelect.new(self.bot, player, post)
            await ui.send_to(ctx.author)

        # RP Post
        elif (
            player.guild.rp_post_channel
            and message.channel.id == player.guild.rp_post_channel.id
        ):
            if not self._is_user_the_author(ctx, message):
                raise G0T0Error("You cannot edit this roleplay board post")

            await message.add_reaction(EDIT_EMOJI[0])
            ui = RPPostUI.new(self.bot, player, message)
            await ui.send_to(ctx.author)

        # Character Say
        elif (
            webhook := G0T0Webhook(ctx, message=message)
        ) and await webhook.is_valid_message():
            modal = SayEditModal(self.bot, webhook)
            return await ctx.send_modal(modal)

        else:
            raise G0T0Error("This message cannot be edited")

        await ctx.delete()

    @commands.message_command(name="Delete")
    async def message_delete(self, ctx: G0T0Context, message: discord.Message):
        player = ctx.player

        # Arena Board
        if (
            player.guild.arena_board_channel
            and message.channel.id == player.guild.arena_board_channel.id
        ):
            if not self._is_user_the_author(ctx, message):
                raise G0T0Error("You cannot edit this arena board post")

            await message.delete()

        # Market
        elif (
            player.guild.market_channel
            and message.channel.id == player.guild.market_channel.id
        ):
            if transaction := await MarketTransaction.get_request(self.bot, message):
                transaction: MarketTransaction
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()

                            for user in users:
                                if (
                                    player.guild.is_staff(player.member)
                                    or user.id == self.bot.user.id
                                ):
                                    raise G0T0Error(
                                        f"Transaction was previously denied. Please make a new request"
                                    )

                if transaction.player.id != ctx.author.id:
                    raise G0T0Error("You can only edit your own transactions")

                await message.delete()

        # RP Post
        elif (
            player.guild.rp_post_channel
            and message.channel.id == player.guild.rp_post_channel.id
        ):
            if not self._is_user_the_author(ctx, message):
                raise G0T0Error("You cannot edit this roleplay board post")

            await message.delete()

        # Character Say
        elif (
            webhook := G0T0Webhook(ctx, message=message)
        ) and await webhook.is_valid_message():
            await webhook.delete()

        # Staff Say Delete
        elif (
            player.guild.is_staff(player.member)
            and (webhook := G0T0Webhook(ctx, message=message))
            and await webhook.is_valid_message(update_player=True)
        ):
            await webhook.delete()

        # Adventure NPC
        elif (
            webhook := G0T0Webhook(ctx, type=WebhookType.adventure, message=message)
        ) and await webhook.is_valid_message():
            await webhook.delete()

        # Global NPC
        elif (
            webhook := G0T0Webhook(ctx, type=WebhookType.npc, message=message)
        ) and await webhook.is_valid_message():
            await webhook.delete()

        else:
            raise G0T0Error("This message cannot be deleted")

        await ctx.delete()

    @commands.message_command(name="Approve")
    @commands.check(is_staff)
    async def message_approve(self, ctx: G0T0Context, message: discord.Message):
        guild = ctx.player.guild

        # Market Transactions
        if guild.market_channel and message.channel.id == guild.market_channel.id:
            if transaction := await MarketTransaction.get_request(self.bot, message):
                transaction: MarketTransaction
                # Check if transaction was denied previously
                if len(message.reactions) > 0:
                    for reaction in message.reactions:
                        if reaction.emoji in DENIED_EMOJI:
                            users = await reaction.users().flatten()
                            for user in users:
                                if (
                                    guild.is_staff(ctx.player.member)
                                    or user.id == self.bot.user.id
                                ):
                                    raise G0T0Error(
                                        f"Transaction was previously denied. Please make a new request"
                                    )

                # Selling items
                if transaction.type.value == "Sell Items":
                    await message.add_reaction(APPROVAL_EMOJI[0])
                    log_entry = await DBLog.create(
                        self.bot,
                        ctx,
                        transaction.player,
                        ctx.author,
                        "SELL",
                        character=transaction.character,
                        notes=transaction.log_notes,
                        cc=transaction.cc,
                        credits=transaction.credits,
                        ignore_handicap=True,
                        show_values=True,
                        silent=True,
                    )
                    await message.edit(content=None, embed=LogEmbed(log_entry, True))

                else:
                    try:
                        log_entry = await DBLog.create(
                            self.bot,
                            ctx,
                            transaction.player,
                            ctx.author,
                            "BUY",
                            character=transaction.character,
                            notes=transaction.log_notes,
                            cc=-transaction.cc,
                            credits=-transaction.credits,
                            show_values=True,
                            ignore_handicap=True,
                        )
                        await message.add_reaction(APPROVAL_EMOJI[0])
                        await message.edit(content="", embed=LogEmbed(log_entry, True))
                    except Exception as error:
                        await message.clear_reactions()
                        await message.add_reaction(DENIED_EMOJI[0])
                        raise error

        # RP
        elif (
            guild.staff_role
            and guild.staff_role.mention in message.content
            and len(message.mentions) > 0
        ):
            ui = await MessageLogUI.new(self.bot, ctx.author, message)
            await ui.send_to(ctx)

        else:
            raise G0T0Error("Nothing to approve here. Move along.")

        await ctx.delete()

    @commands.message_command(name="Null")
    @commands.check(is_admin)
    async def message_null(self, ctx: G0T0Context, message: discord.Message):
        await ctx.defer()
        log_entry = await self._get_log_from_entry(message)
        reason = await confirm(
            ctx,
            f"What is the reason for nulling the log?",
            True,
            self.bot,
            response_check=None,
        )
        await log_entry.null(ctx, reason)
        await message.add_reaction(NULL_EMOJI[0])

    # --------------------------- #
    # Private Methods
    # --------------------------- #
    async def _get_log_from_entry(self, message: discord.Message) -> DBLog:
        try:
            embed = message.embeds[0]
            log_id = self._get_match(f"ID:\s*(\d+)", embed.footer.text)

            log_entry = await DBLog.get_log(self.bot, log_id)
        except:
            raise LogNotFound()

        return log_entry

    def _get_match(self, pattern, text, group=1, default=None):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(group) if match and match.group(group) != "None" else default

    def _is_user_the_author(self, ctx: G0T0Context, message: discord.Message):
        if not message.author.bot:
            return False

        try:
            embed = message.embeds[0]
        except:
            return False

        # Author id in the footer text
        if embed.footer and embed.footer.text == f"{ctx.author.id}":
            return True

        # Checking if the author icon_url if for the author. avatars = default profile; users = server profile
        elif (
            embed.author
            and self._get_match(r"(?:avatars|users)/(\d+)/", embed.author.icon_url)
            == f"{ctx.author.id}"
        ):
            return True

        return False
