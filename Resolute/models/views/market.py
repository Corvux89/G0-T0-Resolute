from typing import Mapping

import discord
from discord.ui import InputText

from Resolute.bot import G0T0Bot
from Resolute.helpers import get_guild
from Resolute.models.categories.categories import (LevelCost,
                                                   TransactionSubType,
                                                   TransactionType)
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.market import TransactionEmbed
from Resolute.models.objects.market import MarketTransaction
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class MarketPrompt(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "transaction")
    bot: G0T0Bot
    owner: discord.Member = None
    player: Player
    transaction: MarketTransaction = None


class MarketPromptUI(MarketPrompt):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        character = player.characters[0] if len(player.characters) > 0 else None
        inst.transaction = MarketTransaction(inst.player, character=character)
        return inst
    
    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(self, char: discord.ui.Select, interation: discord.Interaction):
        self.transaction.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interation)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, row=2)
    async def transaction_prompt(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(TransactionPromptUI, interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if not self.player.characters:
            self.on_timeout()
        
        char_list = []
        for char in self.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{self.player.characters.index(char)}", default=True if self.player.characters.index(char) == self.player.characters.index(self.transaction.character) else False))
        self.character_select.options = char_list

    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Select a character this is for:\n"}

class TransactionPromptUI(MarketPrompt):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player, transaction: MarketTransaction = None):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        character = transaction.character if transaction else player.characters[0] if len(player.characters) > 0 else None
        inst.transaction = transaction or MarketTransaction(inst.player, character=character)
        return inst
    
    @discord.ui.select(placeholder="Select transaction type", row=1)
    async def transaction_select(self, type: discord.ui.Select, interaction: discord.Interaction):
        self.transaction.type = self.bot.compendium.get_object(TransactionType, int(type.values[0]))
        self.transaction.subtype = None

        if self.transaction.type:
            if self.transaction.type.value == "Leveling":
                new_level = self.transaction.character.level+1
                cost = self.bot.compendium.get_object(LevelCost, new_level)

                self.transaction.notes = f"Purchasing level {new_level}"
                self.transaction.cc = cost.cc if cost else 0

            if self.transaction.type.currency == "CC":
                self.transaction.credits = 0
            elif self.transaction.type.currency == "CR":
                self.transaction.cc = 0

        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Select transaction subtype", row=2, custom_id="subtype")
    async def transaction_sub_select(self, subtype: discord.ui.Select, interaction: discord.Interaction):
        self.transaction.subtype = self.bot.compendium.get_object(TransactionSubType, int(subtype.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Details", style=discord.ButtonStyle.primary, row=3)
    async def transaction_details(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = TransactionDetails(self.transaction)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, row=3)
    async def submit_transaction(self, _: discord.ui.Button, interaction: discord.Interaction):
        guild = await get_guild(self.bot, self.player.guild_id)
        if self.transaction.message:
            await self.transaction.message.edit(embed=TransactionEmbed(self.transaction))
            await self.transaction.message.clear_reactions()
        elif guild.market_channel:
            await guild.market_channel.send(embed=TransactionEmbed(self.transaction))           
            await interaction.response.send_message("Request Submitted!", ephemeral=True)
        else:
            await interaction.response.send_message("Issue submitting request", ephemeral=True)
        await self.on_timeout()

    @discord.ui.button(label="Change Character", style=discord.ButtonStyle.secondary, row=4)
    async def change_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(MarketPromptUI, interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def exit(self, *_):
        if self.transaction.message:
            await self.transaction.message.edit(embed=TransactionEmbed(self.transaction))
            await self.transaction.message.clear_reactions()
        await self.on_timeout()

    async def get_content(self) -> Mapping:
        return {"embed": TransactionEmbed(self.transaction), "content": ""}

    async def _before_send(self):
        if len(self.player.characters) == 1:
            self.remove_item(self.change_character)        

        self.transaction_select.options = [discord.SelectOption(label=f"{x.value}", value=f"{x.id}", default=True if self.transaction.type and self.transaction.type.id == x.id else False) for x in self.bot.compendium.transaction_type[0].values()]

        subtypes = [discord.SelectOption(label=f"{x.value}", value=f"{x.id}", default=True if self.transaction.subtype and self.transaction.subtype.id == x.id else False) for x in self.bot.compendium.transaction_subtype[0].values() if self.transaction.type and self.transaction.type.id == x.parent]

        self.transaction_details.disabled = False if self.transaction.type else True
        self.submit_transaction.disabled = False if self.transaction.type and (self.transaction.cc > 0 if self.transaction.type.currency == "CC" else self.transaction.credits > 0 if self.transaction.type.currency == "CR" else (self.transaction.cc > 0 or self.transaction.credits > 0)) else True

        if len(subtypes) > 0:
            if not self.get_item("subtype"):
                self.add_item(self.transaction_sub_select)
            self.transaction_sub_select.options = subtypes
        else:
            self.remove_item(self.transaction_sub_select)

class TransactionDetails(discord.ui.Modal):
    transaction: MarketTransaction

    def __init__(self, transaction: MarketTransaction):
        super().__init__(title=f"Market Request Details")

        self.transaction = transaction

        self.add_item(InputText(label="Transaction Details", placeholder="Transaction Details", style=discord.InputTextStyle.long, max_length=2000, 
                                value=transaction.notes))
        
        if self.transaction.type.currency == "CC" or self.transaction.type.currency == "Both":
            self.add_item(InputText(label="Total CC Cost", placeholder="Total CC Cost",
                                    value=transaction.cc))

        if self.transaction.type.currency == "CR" or self.transaction.type.currency == "Both":
            self.add_item(InputText(label="Total Credit Cost", placeholder="Total Credit Cost",
                                    value=transaction.credits))
        
    async def callback(self, interaction: discord.Interaction):
        err_str = []       
        self.transaction.notes = self.children[0].value

        try:
            if self.transaction.type.currency == "CC" or self.transaction.type.currency == "Both":
                self.transaction.cc = int(self.children[1].value) or 0
            else:
                self.transaction.credits = int(self.children[1].value) or 0

            if self.transaction.type.currency == "Both":
                self.transaction.credits = int(self.children[2].value) or 0
        except:
            err_str.append("Cost must be a number")

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()