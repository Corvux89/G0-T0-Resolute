import discord

from math import ceil
from typing import Mapping, Type
from datetime import datetime, timezone
from discord import SelectOption
from discord.ui import Modal, InputText

from Resolute.bot import G0T0Bot
from Resolute.helpers.adventures import update_dm, upsert_adventure
from Resolute.helpers.general_helpers import confirm, is_admin
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player
from Resolute.models.categories import Activity
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.adventures import AdventureRewardEmbed, AdventureSettingsEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.views.base import InteractiveView

class AdventureSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "adventure", "dm_select")
    bot: G0T0Bot
    owner: discord.Member = None
    adventure: Adventure
    dm_select: bool = False
    member: discord.Member = None
    character: PlayerCharacter = None
    
    async def _before_send(self, interaction: discord.Interaction):
        pass

    async def commit(self):
        await upsert_adventure(self.bot, self.adventure)

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content(destination)
        await self._before_send(destination)
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["AdventureSettings"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send(interaction)
        await view.refresh_content(interaction)

    async def get_content(self, interaction: discord.Interaction) -> Mapping:
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content(interaction)
        await self._before_send(interaction)
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
            g = await get_guild(self.bot, interaction.guild.id)
            self.adventure.cc += response.cc

            if dm_activity := self.bot.compendium.get_object(Activity, "ADVENTURE_DM"):
                dm_reward = response.cc + ceil(response.cc * .25)
                for dm in self.adventure.dms:
                    player = await get_player(self.bot, dm, interaction.guild.id)
                    await create_log(self.bot, self.owner, g, dm_activity, player, 
                                     notes=f"{self.adventure.name}",
                                     cc=dm_reward, 
                                     adventure=self.adventure)
            else:
                await interaction.channel.send(embed=ErrorEmbed(description=f"Error getting DM Activity"), delete_after=5)
            
            if player_activity := self.bot.compendium.get_object(Activity, "ADVENTURE"):
                player_reward = response.cc

                for character in self.adventure.player_characters:
                    player = await get_player(self.bot, character.player_id, interaction.guild.id)
                    await create_log(self.bot, self.owner, g, player_activity, player, 
                                     character=character, 
                                     notes=f"{self.adventure.name}", 
                                     cc=player_reward, 
                                     adventure=self.adventure)
            else:
                await interaction.channel.send(embed=ErrorEmbed(description=f"Error getting Player Adventure Activity"), delete_after=5)
            
            await interaction.channel.send(embed=AdventureRewardEmbed(interaction, self.adventure, response.cc))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Close Adventure", style=discord.ButtonStyle.danger, row=2)
    async def adventure_close(self, _: discord.ui.Button, interaction: discord.Interaction):
        if adventure_role := interaction.guild.get_role(self.adventure.role_id):
            conf = await confirm(interaction, "Are you sure you want to end this adventure? (Reply with yes/no)", True, self.bot)

            if conf is None:
                await interaction.channel.send(embed=ErrorEmbed(description=f"Timed out waiting for a response or invalid response."), delete_after=5)
                await self.refresh_content(interaction)
            elif not conf:
                await interaction.channel.send(embed=ErrorEmbed(description=f"Ok, cancelling"), delete_after=5)
                await self.refresh_content(interaction)
            else:
                self.adventure.end_ts = datetime.now(timezone.utc)

                await adventure_role.delete(reason=f"Closing adventure")

                await upsert_adventure(self.bot, self.adventure)
                await self.on_timeout()
        

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self, interaction: discord.Interaction):
        if self.owner.id not in self.adventure.dms and not is_admin(interaction):
            self.remove_item(self.adventure_dm)
            self.remove_item(self.adventure_players)
            self.remove_item(self.adventure_close)

    
    async def get_content(self, interaction: discord.Interaction) -> Mapping:
        return {"embed": AdventureSettingsEmbed(interaction, self.adventure), "content": ""}
    
class _AdventureMemberSelect(AdventureSettings):
    @discord.ui.user_select(placeholder="Select a Player", row=1)
    async def member_select(self, user: discord.ui.Select, interaction: discord.Interaction):
        member: discord.Member = user.values[0]
        self.member = member
        self.player = await get_player(self.bot, self.member.id, interaction.guild.id)
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

        if self.member is None:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Select someone to add"), delete_after=5)
        if self.dm_select:
            if self.member.id in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} is already a DM of this adventure"), delete_after=5)
            elif character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} can't be a player and a DM"), delete_after=5)
            else:
                self.adventure.dms.append(self.member.id)

                adventure_category = interaction.guild.get_channel(self.adventure.category_channel_id)               
                category_overwrites = await update_dm(self.member, adventure_category.overwrites, adventure_role, self.adventure.name)
                await adventure_category.edit(overwrites=category_overwrites)

                for channel in adventure_category.channels:
                    channel_overwrites = await update_dm(self.member, channel.overwrites, adventure_role, self.adventure.name)
                    await channel.edit(overwrites=channel_overwrites)
        else:
            if self.character is None:
                if not self.player.characters:
                    await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} has no characters."), delete_after=5)
                else:
                    await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} has no characters."), delete_after=5)
            else:
                if self.adventure.characters and self.character.id in self.adventure.characters:
                    await interaction.channel.send(embed=ErrorEmbed(description=f"{self.character.name} is already in the adventure"), delete_after=5)
                elif self.member.id in self.adventure.dms:
                    await interaction.channel.send(embed=ErrorEmbed(description=f"{self.character.name} is a DM for this adventure"), delete_after=5)
                elif character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                    await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} already has a character in the adventure"), delete_after=5)
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
                await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} is not a DM of this adventure"), delete_after=5)
            elif len(self.adventure.dms) == 1:
                await interaction.channel.send(embed=ErrorEmbed(description=f"Cannot remove the last DM. Either add another one first, or close the adventure"), delete_after=5)
            else:
                self.adventure.dms.remove(self.member.id)

                adventure_category = interaction.guild.get_channel(self.adventure.category_channel_id)
                category_overwrites = await update_dm(self.member, adventure_category.overwrites, adventure_role, self.adventure.name, True)
                await adventure_category.edit(overwrites=category_overwrites)

                for channel in adventure_category.channels:
                    channel_overwrites = await update_dm(self.member, channel.overwrites, adventure_role, self.adventure.name, True)
                    await channel.edit(overwrites=channel_overwrites)
                await upsert_adventure(self.bot, self.adventure)
        else:
            if character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                self.adventure.player_characters.remove(character)
                self.adventure.characters.remove(character.id)

                if adventure_role in self.member.roles:
                    await self.member.remove_roles(adventure_role, reason=f"Removed from {self.adventure.name} by {self.owner.name}")
            else:
                await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} is not part of this adventure"), delete_after=5)
                
            
        await self.refresh_content(interaction)


    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.character = None
        self.player = None
        self.member = None
        await self.defer_to(AdventureSettingsUI, interaction)

    async def _before_send(self, interaction: discord.Interaction):
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


    async def get_content(self, interaction: discord.Interaction) -> Mapping:
        return {"embed": AdventureSettingsEmbed(interaction, self.adventure), "content": ""}
    
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
            await interaction.channel.send(embed=ErrorEmbed(description=f"Chain codes must be a number!"), delete_after=5)
        
        await interaction.response.defer()
        self.stop()