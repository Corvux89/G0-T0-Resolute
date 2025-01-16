from datetime import datetime, timezone
from math import ceil
from typing import Mapping, Type

import discord
from discord import SelectOption
from discord.ui import InputText, Modal

from Resolute.bot import G0T0Bot
from Resolute.helpers.adventures import update_dm
from Resolute.helpers.general_helpers import confirm, is_admin
from Resolute.helpers.logs import create_log
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.adventures import (AdventureRewardEmbed,
                                               AdventureSettingsEmbed)
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.views.base import InteractiveView
from Resolute.models.views.npc import NPCSettingsUI


class AdventureSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "adventure", "dm_select")
    bot: G0T0Bot
    owner: discord.Member = None
    adventure: Adventure
    dm_select: bool = False
    member: discord.Member = None
    character: PlayerCharacter = None
    

    async def commit(self):
        await self.adventure.upsert()

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content(destination)
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["AdventureSettings"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self, interaction: discord.Interaction) -> Mapping:
        return {"embed": AdventureSettingsEmbed(interaction, self.adventure), "content": ""}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content(interaction)
        await self._before_send()
        await self.commit()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)
    
class AdventureSettingsUI(AdventureSettings):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, adventure: Adventure):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.adventure = adventure

        return inst
    
    @discord.ui.button(label="Manage DM(s)", style=discord.ButtonStyle.primary, row=1)
    async def adventure_dm(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.dm_select = True
        await self.defer_to(_AdventureMemberSelect, interaction)

    @discord.ui.button(label="Manage Player(s)", style=discord.ButtonStyle.primary, row=1)
    async def adventure_players(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.dm_select = False
        await self.defer_to(_AdventureMemberSelect, interaction)

    @discord.ui.button(label="Reward CC", style=discord.ButtonStyle.green, row=2)
    async def adventure_reward(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = AdventureRewardModal(self.adventure)
        response = await self.prompt_modal(interaction, modal)

        if response.cc > 0:
            self.adventure.cc += response.cc

            dm_reward = response.cc + ceil(response.cc * .25)
            for dm in self.adventure.dms:
                player = await self.bot.get_player(dm, interaction.guild.id)
                await create_log(self.bot, self.owner, "ADVENTURE_DM", player, 
                                    notes=f"{self.adventure.name}",
                                    cc=dm_reward, 
                                    adventure=self.adventure)
            
            player_reward = response.cc

            for character in self.adventure.player_characters:
                player = await self.bot.get_player(character.player_id, interaction.guild.id)
                await create_log(self.bot, self.owner, "ADVENTURE", player, 
                                    character=character, 
                                    notes=f"{self.adventure.name}", 
                                    cc=player_reward, 
                                    adventure=self.adventure)
            
            await interaction.channel.send(embed=AdventureRewardEmbed(interaction, self.adventure, response.cc))
        await self.refresh_content(interaction)

    @discord.ui.button(label="NPCs", style=discord.ButtonStyle.primary, row=2)
    async def npcs(self, _: discord.ui.Button, interaction: discord.Interaction):
        guild = await self.bot.get_player_guild(self.adventure.guild_id)
        view = NPCSettingsUI.new(self.bot, self.owner, guild, AdventureSettingsUI,
                               adventure=self.adventure)
        await view.send_to(interaction)

    @discord.ui.button(label="Factions", style=discord.ButtonStyle.primary, row=2)
    async def factions(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_AdventureFactions, interaction)

    @discord.ui.button(label="Close Adventure", style=discord.ButtonStyle.danger, row=2)
    async def adventure_close(self, _: discord.ui.Button, interaction: discord.Interaction):
        if adventure_role := interaction.guild.get_role(self.adventure.role_id):
            conf = await confirm(interaction, "Are you sure you want to end this adventure? (Reply with yes/no)", True, self.bot)

            if conf is None:
                raise TimeoutError()
            elif not conf:
                raise G0T0Error("Ok, cancelling")
            else:
                # Log Renown if applicable
                if len(self.adventure.factions) > 0:
                    renown = await confirm(interaction, "Is this being closed due to inactivity? (Reply with yes/no)", True, self.bot)

                    if renown is None:
                        raise TimeoutError()
                    elif not renown:
                        amount = 1 if len(self.adventure.factions) > 1 else 2

                        for char in self.adventure.player_characters:
                            player = await self.bot.get_player(char.player_id, self.adventure.guild_id)
                            for faction in self.adventure.factions:
                                await create_log(self.bot, self.owner, "RENOWN", player,
                                                            character=char,
                                                            notes=f"Adventure Reward: {self.adventure.name}",
                                                            renown=amount,
                                                            faction=faction)
                
                # Close adventure and clean up role
                self.adventure.end_ts = datetime.now(timezone.utc)
                await adventure_role.delete(reason=f"Closing adventure")
                await self.adventure.upsert()

                # NPC Cleanup
                for npc in self.adventure.npcs:
                    await npc.delete()

                await self.on_timeout()
        

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if self.owner.id not in self.adventure.dms and not is_admin:
            self.remove_item(self.adventure_dm)
            self.remove_item(self.adventure_players)
            self.remove_item(self.adventure_close)
    
class _AdventureMemberSelect(AdventureSettings):
    async def _before_send(self):
        self.add_member.disabled = False if self.character else True
        self.remove_member.disabled = False if self.character else True

    @discord.ui.user_select(placeholder="Select a Player", row=1)
    async def member_select(self, user: discord.ui.Select, interaction: discord.Interaction):
        member: discord.Member = user.values[0]
        self.member = member
        self.player = await self.bot.get_player(self.member.id, interaction.guild.id)
        self.character = None
        if not self.dm_select and self.get_item("char_select") is None:
            self.add_item(self.character_select)
        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Select a character", options=[SelectOption(label="You should never see me")], row=2, custom_id="char_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Player", row=3)
    async def add_member(self, _: discord.ui.Button, interaction: discord.Interaction):
        adventure_role = interaction.guild.get_role(self.adventure.role_id)

        if self.dm_select:
            if self.member.id in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is already a DM of this adventure"), delete_after=5)
            elif character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} can't be a player and a DM"), delete_after=5)
            else:
                self.adventure.dms.append(self.member.id)

                category_overwrites = await update_dm(self.member, self.adventure.category_channel.overwrites, adventure_role, self.adventure.name)
                await self.adventure.category_channel.edit(overwrites=category_overwrites)

                for channel in self.adventure.category_channel.channels:
                    channel_overwrites = await update_dm(self.member, channel.overwrites, adventure_role, self.adventure.name)
                    await channel.edit(overwrites=channel_overwrites)
        else:
            if self.adventure.characters and self.character.id in self.adventure.characters:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.character.name} is already in the adventure"), delete_after=5)
            elif self.member.id in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.character.name} is a DM for this adventure"), delete_after=5)
            elif character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} already has a character in the adventure"), delete_after=5)
            else:
                self.adventure.player_characters.append(self.character)
                self.adventure.characters.append(self.character.id)

                if adventure_role not in self.member.roles:
                    await self.member.add_roles(adventure_role, reason=f"{self.character.name} added to {self.adventure.name} by {self.owner.name}")
            
                await interaction.channel.send(f"{self.character.name} ({self.member.mention}) added to {self.adventure.name}")

        await self.refresh_content(interaction)
        
    @discord.ui.button(label="Remove Player", row=3)
    async def remove_member(self, _: discord.ui.Button, interaction: discord.Interaction):
        adventure_role = interaction.guild.get_role(self.adventure.role_id)

        if self.dm_select:
            if self.member.id not in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not a DM of this adventure"), delete_after=5)
            elif len(self.adventure.dms) == 1:
                await interaction.channel.send(embed=ErrorEmbed(f"Cannot remove the last DM. Either add another one first, or close the adventure"), delete_after=5)
            else:
                self.adventure.dms.remove(self.member.id)

                category_overwrites = await update_dm(self.member, self.adventure.category_channel.overwrites, adventure_role, self.adventure.name, True)
                await self.adventure.category_channel.edit(overwrites=category_overwrites)

                for channel in self.adventure.category_channel.channels:
                    channel_overwrites = await update_dm(self.member, channel.overwrites, adventure_role, self.adventure.name, True)
                    await channel.edit(overwrites=channel_overwrites)
                await self.adventure.upsert()
        else:
            if character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                self.adventure.player_characters.remove(character)
                self.adventure.characters.remove(character.id)

                if adventure_role in self.member.roles:
                    await self.member.remove_roles(adventure_role, reason=f"Removed from {self.adventure.name} by {self.owner.name}")
            else:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not part of this adventure"), delete_after=5)
                
            
        await self.refresh_content(interaction)


    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.character = None
        self.player = None
        self.member = None
        await self.defer_to(AdventureSettingsUI, interaction)

    async def _before_send(self):
        if self.member is None or self.dm_select:
            self.remove_item(self.character_select)
        else:
            if self.player.characters:
                if self.character is None:
                    self.character = self.player.characters[0]

                char_list = []
                for char in self.player.characters:
                    char_list.append(SelectOption(label=f"{char.name}", value=f"{self.player.characters.index(char)}", default=True if self.character and  self.player.characters.index(char) == self.player.characters.index(self.character) else False))
                self.character_select.options = char_list
            else:
                self.remove_item(self.character_select)
    
        if self.dm_select:
            self.member_select.placeholder = "Select a DM"
            self.add_member.label = "Add DM"
            self.remove_member.label = "Remove DM"
        else:
            self.member_select.placeholder = "Select a Player"
            self.add_member.label = "Add Player"
            self.remove_member.label = "Remove Player"    

class _AdventureFactions(AdventureSettings):
    faction: Faction = None

    async def _before_send(self):
        faction_list = [SelectOption(label=f"{f.value}", value=f"{f.id}", default=True if self.faction and self.faction.id == f.id else False) for f in self.bot.compendium.faction[0].values()]

        self.faction_select.options = faction_list

        self.add_faction.disabled = False if self.faction else True
        self.remove_faction.disabled = False if self.faction else True

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def faction_select(self, f: discord.ui.Select, interaction: discord.Interaction):
        self.faction = self.bot.compendium.get_object(Faction, int(f.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Faction", style=discord.ButtonStyle.primary, row=2)
    async def add_faction(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.faction and self.faction.id not in [f.id for f in self.adventure.factions]:
            if len(self.adventure.factions) >= 2 and not is_admin:
                await interaction.channel.send(embed=ErrorEmbed(f"You do not have the ability to add more than 2 factions to an adventure"), delete_after=5)
            else:
                self.adventure.factions.append(self.faction)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Faction", style=discord.ButtonStyle.primary, row=2)
    async def remove_faction(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.faction and self.faction.id in [f.id for f in self.adventure.factions]:
            faction = next((f for f in self.adventure.factions if f.id == self.faction.id), None)
            self.adventure.factions.remove(faction)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.faction = None
        await self.defer_to(AdventureSettingsUI, interaction)   
    
class AdventureRewardModal(Modal):
    adventure: Adventure
    cc: int = 0

    def __init__(self, adventure: Adventure):
        super().__init__(title=f"{adventure.name} Rewards")
        self.adventure = adventure

        self.add_item(InputText(label="CC Amount", required=True, placeholder="CC Amount", max_length=3))

    async def callback(self, interaction: discord.Interaction):
        try:
            self.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed(f"Chain codes must be a number!"), delete_after=5)
        
        await interaction.response.defer()
        self.stop()