import discord

from typing import Mapping
from Resolute.bot import G0T0Bot
from Resolute.models.embeds.npc import NPCEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.npc import NPC
from Resolute.models.views.base import InteractiveView


class NPCSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "guild", "adventure", "npc", "back_menu")
    bot: G0T0Bot
    guild: PlayerGuild
    adventure: Adventure
    npc: NPC
    back_menu: type[InteractiveView] 


    async def get_content(self) -> Mapping:
        embed = NPCEmbed(self.guild.npcs if self.guild and self.guild.npcs else self.adventure.npcs if self.adventure and self.adventure.npcs else [], self.npc)

        return {"content": "", "embed": embed}
    

class NPCSettingsUI(NPCSettings):
    @classmethod
    def new(cls, bot, owner,  back_menu, **kwargs):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.back_menu = back_menu
        inst.guild = kwargs.get("guild")
        inst.adventure = kwargs.get("adventure")

        return inst
    
    @discord.ui.select()