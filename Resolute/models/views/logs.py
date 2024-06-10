import math
import discord

from typing import Mapping, Optional, Type
from Resolute.bot import G0T0Bot
from Resolute.helpers.logs import create_log
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player
from Resolute.models.categories import Activity, CodeConversion
from Resolute.models.views.base import InteractiveView


class LogPrompt(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "member", "activity", "credits", "guild", "notes", "cc", "ignore_handicap", "conversion")
    owner: discord.Member = None
    member = discord.Member = None
    bot: G0T0Bot
    guild: PlayerGuild
    activity: Activity
    credits: int = 0
    cc: int = 0
    player: Player
    character: PlayerCharacter = None
    notes: str = None
    ignore_handicap: bool = False
    conversion: bool = False

   
    
class LogPromptUI(LogPrompt):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, member: discord.Member, player: Player, guild: PlayerGuild, activity: Activity, 
            credits: int = 0, cc: int = 0, notes: str = None, ignore_handicap: bool = False, conversion: bool = False):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.member = member
        inst.guild = guild
        inst.player = player
        inst.activity = activity
        inst.credits = credits
        inst.cc = cc
        inst.notes = notes
        inst.character = player.characters[0] if len(player.characters) > 0 else None
        inst.ignore_handicap=ignore_handicap
        inst.conversion = conversion
        return inst
    
    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(self, char: discord.ui.Select, interation: discord.Interaction):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interation)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, row=2)
    async def confirm_log(self, _: discord.ui.Button, interaction: discord.Interaction):
        rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, self.character.level)
        if self.conversion:
            self.credits = abs(self.cc) * rate.value
            self.ignore_handicap = True

        if (self.character.credits + self.credits) < 0:
            convertedCC = math.ceil((self.credits - self.character.credits) / rate.value)
            if self.player.cc < convertedCC:
                await interaction.channel.send(embed=ErrorEmbed(description=f"{self.character.name} cannot afford the {self.credits} credit cost or to convert the {convertedCC} needed."))
            else:
                convert_activity = self.bot.compendium.get_object(Activity, "CONVERSION")
                converted_entry = await create_log(self.bot, self.owner, self.guild, convert_activity, self.player, self.character, self.notes, -convertedCC, convertedCC*rate.value, None, True)
                await interaction.channel.send(embed=LogEmbed(converted_entry, self.owner, self.member, self.character, True))
                log_entry = await create_log(self.bot, self.owner, self.guild, self.activity, self.player, self.character, self.notes, self.cc, self.credits, None, self.ignore_handicap)
                await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.member, self.character))
        else:
            log_entry = await create_log(self.bot, self.owner, self.guild, self.activity, self.player, self.character, self.notes, self.cc, self.credits, None, self.ignore_handicap)
            await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.member, self.character))
        await self.on_timeout()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if not self.player.characters:
            self.on_timeout()
        
        char_list = []
        for char in self.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{self.player.characters.index(char)}", default=True if self.player.characters.index(char) == self.player.characters.index(self.character) else False))
        self.character_select.options = char_list   
    
    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Select a character to log this for:\n"}
    