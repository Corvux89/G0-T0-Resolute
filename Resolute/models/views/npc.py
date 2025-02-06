from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import is_admin
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.npc import NPCEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.npc import NPC
from Resolute.models.views.base import InteractiveView


class NPCSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "guild", "adventure", "npc", "back_menu", "role")
    bot: G0T0Bot
    guild: PlayerGuild
    adventure: Adventure
    back_menu: type[InteractiveView] 

    npc: NPC = None
    role: discord.Role = None


    async def get_content(self) -> Mapping:
        embed = NPCEmbed(self.guild,
                         self.adventure.npcs if self.adventure and self.adventure.npcs else [] if self.adventure else self.guild.npcs if self.guild and self.guild.npcs else [],  
                         self.npc)

        return {"content": "", "embed": embed}
    
    async def send_to(self, interaction, *args, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send()

        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)

    async def commit(self):
        if self.adventure:
            self.adventure = await self.bot.get_adventure_from_category(self.adventure.category_channel_id)
        elif self.guild:
              self.guild = await self.bot.get_player_guild(self.guild.id)


    

class NPCSettingsUI(NPCSettings):
    @classmethod
    def new(cls, bot, owner, guild, back_menu, **kwargs):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.back_menu = back_menu
        inst.guild = guild
        inst.adventure = kwargs.get("adventure")
        return inst
    
    async def _before_send(self):
        npcs = []
        if self.adventure:
            self.remove_item(self.add_npc_role)
            self.remove_item(self.remove_npc_role)
            self.remove_item(self.role_select)

            if not is_admin:
                self.remove_item(self.new_npc)
                self.remove_item(self.delete_npc_button)
                self.remove_item(self.edit_npc)

            if self.adventure.npcs and len(self.adventure.npcs) > 0:
                     npcs = self.adventure.npcs
        else:
            if self.guild.npcs and len(self.guild.npcs) > 0:
                npcs = self.guild.npcs
                

        if len(npcs) == 0:
                self.remove_item(self.npc_select)
        else:
            if not self.get_item("npc_select"):
                self.add_item(self.npc_select)

            npc_list = [discord.SelectOption(label=f"{n.name}", 
                                                value=f"{n.key}", 
                                                default=True if self.npc and self.npc.key == n.key else False) for n in npcs]

            self.npc_select.options = npc_list

        self.edit_npc.disabled = False if self.npc else True
        self.delete_npc_button.disabled = False if self.npc else True

        self.add_npc_role.disabled = False if self.role else True
        self.remove_npc_role.disabled = False if self.role else True


    
    @discord.ui.select(placeholder="Select an NPC", row=1, custom_id="npc_select")
    async def npc_select(self, n: discord.ui.Select, interaction: discord.Interaction):
        self.npc = next((i for i in self.guild.npcs if i.key == n.values[0]), None)
        await self.refresh_content(interaction)

    @discord.ui.role_select(placeholder="Select a role", custom_id="role_select", row=2)
    async def role_select(self, r: discord.ui.Select, interaction: discord.Interaction):
        self.role = r.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="New NPC", style=discord.ButtonStyle.primary, row=3)
    async def new_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
         modal = NPCModal(self.bot, 
                          guild=self.guild,
                          adventure=self.adventure)
         
         await self.prompt_modal(interaction, modal)
         await self.refresh_content(interaction)


    @discord.ui.button(label="Edit NPC", style=discord.ButtonStyle.primary, row=3)
    async def edit_npc(self, _: discord.ui.Button, interaction: discord.Interaction):
         modal = NPCModal(self.bot,
                          guild=self.guild,
                          adventure=self.adventure,
                          npc=self.npc)
         await self.prompt_modal(interaction, modal)
         await self.refresh_content(interaction)

    @discord.ui.button(label="Delete NPC", style=discord.ButtonStyle.danger, row=3)
    async def delete_npc_button(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.npc.delete()
        self.npc = None
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.primary, row=4)
    async def add_npc_role(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.role.id not in self.npc.roles:
            self.npc.roles.append(self.role.id)
            await self.npc.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.primary, row=4)
    async def remove_npc_role(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.role.id in self.npc.roles:
            self.npc.roles.remove(self.role.id)
            await self.npc.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(self.back_menu, interaction)

class NPCModal(discord.ui.Modal):
    bot: G0T0Bot
    guild: PlayerGuild
    adventure: Adventure
    npc: NPC

    def __init__(self, bot: G0T0Bot,  **kwargs):
        super().__init__(title="New NPC")
        self.bot=bot
        self.npc = kwargs.get("npc")
        self.guild = kwargs.get("guild")
        self.adventure = kwargs.get("adventure")
        if not self.npc:
            self.add_item(discord.ui.InputText(label="Key", placeholder="Key", max_length=20, value=self.npc.key if self.npc else None))
        self.add_item(discord.ui.InputText(label="Name", placeholder="Name", max_length=100, value=self.npc.name if self.npc else None))
        self.add_item(discord.ui.InputText(label="Avatar URL", placeholder="Avatar URL", required=False, max_length=100, value=self.npc.avatar_url if self.npc else None))

    async def callback(self, interaction: discord.Interaction):
        key=self.children[0].value.strip() if not self.npc else self.npc.key
        name=self.children[1].value if not self.npc else self.children[0].value
        url=self.children[2].value if not self.npc else self.children[1].value

        if not self.npc and (npc := next((n for n in self.guild.npcs if n.key == key), None)): 
            await interaction.response.send_message(embed=ErrorEmbed(f"An NPC already exists with that key"), 
                                                    ephemeral=True) 
            self.stop()
            
        elif self.npc:
             self.npc.key = key
             self.npc.name = name
             self.npc.avatar_url = url             
        else:
             self.npc = NPC(self.bot.db, 
                            self.guild.id, key, name, 
                            avatar_url=url,
                            adventure_id=self.adventure.id if self.adventure else None)

        await self.npc.upsert()
        self.bot.dispatch("refresh_guild_cache", self.guild)
                      
        await interaction.response.defer()
        self.stop()

