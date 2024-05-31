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


class LogPrompt(discord.ui.View):
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

    def __init__(self, owner: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.message = None # type: Optional[discord.Message]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the owner of this interaction", ephemeral=True)
        return False
    
    @classmethod
    def from_menu(cls, other: "LogPromptUI"):
        inst = cls(owner=other.owner)
        inst.message = other.message
        for attr in cls.__menu_copy_attrs__:
            # copy the instance attr to the new instance if available, or fall back to the class default
            sentinel = object()
            value = getattr(other, attr, sentinel)
            if value is sentinel:
                value = getattr(cls, attr, None)
            setattr(inst, attr, value)
        return inst
    
    async def _before_send(self):
        pass

    async def commit(self):
        pass

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(view=None)
            await self.message.delete()
        except discord.HTTPException:
            pass

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["LogPromptUI"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self) -> Mapping:
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send()
        await self.commit()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)

    @staticmethod
    async def prompt_modal(interaction: discord.Interaction, modal):
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal
    
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
        if self.conversion:
            rate: CodeConversion = self.bot.compendium.get_object(CodeConversion, self.character.level)
            self.credits = abs(self.cc) * rate.value
            self.ignore_handicap = True

        if (self.character.credits + self.credits) < 0:
            await interaction.channel.send(embed=ErrorEmbed(description=f"{self.character.name} cannot afford the {self.credits} credit cost"))
        else:
            log_entry = await create_log(self.bot, self.owner, self.guild, self.activity, self.player, self.character, self.notes, self.cc, self.credits, None, self.ignore_handicap)
            await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.member, self.player, self.character))
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
        return {"embed": None, "content": "Select a charcter to log this for:\n"}
    