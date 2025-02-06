from datetime import datetime, timezone
from math import ceil
from typing import Mapping, Type

from discord import ButtonStyle, Interaction, Member, SelectOption
from discord.ui import (Button, InputText, Modal, Select, button, select,
                        user_select)

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import confirm, is_admin
from Resolute.models.categories.categories import Faction
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.adventures import (AdventureRewardEmbed,
                                               AdventureSettingsEmbed)
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.views.base import InteractiveView
from Resolute.models.views.npc import NPCSettingsUI


class AdventureView(InteractiveView):
    """
    AdventureView is a subclass of InteractiveView that manages the interaction
    and display of an adventure within the bot.
    Attributes:
        bot (G0T0Bot): The bot instance.
        owner (Member, optional): The owner of the adventure. Defaults to None.
        adventure (Adventure): The adventure instance.
        dm_select (bool, optional): Flag indicating if DM selection is enabled. Defaults to False.
        member (Member, optional): The member associated with the view. Defaults to None.
        character (PlayerCharacter, optional): The player character associated with the view. Defaults to None.
    Methods:
        commit(): Commits the current state of the adventure to the database.
        send_to(destination, *args, **kwargs): Sends the view to the specified destination.
        defer_to(view_type, interaction, stop=True): Defers the interaction to another view type.
        get_content(interaction): Retrieves the content to be displayed in the view.
        refresh_content(interaction, **kwargs): Refreshes the content of the view.
    """
    __menu_copy_attrs__ = ("bot", "adventure", "dm_select")
    bot: G0T0Bot
    owner: Member = None
    adventure: Adventure
    dm_select: bool = False
    member: Member = None
    character: PlayerCharacter = None
    

    async def commit(self):
        await self.adventure.upsert()

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content(destination)
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["AdventureView"], interaction: Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self, interaction: Interaction) -> Mapping:
        return {"embed": AdventureSettingsEmbed(interaction, self.adventure), "content": ""}

    async def refresh_content(self, interaction: Interaction, **kwargs):
        content_kwargs = await self.get_content(interaction)
        await self._before_send()
        await self.commit()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)
    
class AdventureSettingsUI(AdventureView):
    """
    A user interface class for managing adventure settings in the G0-T0 bot.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: Member, adventure: Adventure):
        Creates a new instance of AdventureSettingsUI.
    adventure_dm(self, _: Button, interaction: Interaction):
        Handles the "Manage DM(s)" button click event.
    adventure_players(self, _: Button, interaction: Interaction):
        Handles the "Manage Player(s)" button click event.
    adventure_reward(self, _: Button, interaction: Interaction):
        Handles the "Reward CC" button click event and rewards players and DMs with CC.
    npcs(self, _: Button, interaction: Interaction):
        Handles the "NPCs" button click event and opens the NPC settings UI.
    factions(self, _: Button, interaction: Interaction):
        Handles the "Factions" button click event and defers to the adventure factions view.
    adventure_close(self, _: Button, interaction: Interaction):
        Handles the "Close Adventure" button click event and closes the adventure after confirmation.
    exit(self, *_):
        Handles the "Exit" button click event and exits the UI.
    _before_send(self):
        Removes certain buttons if the user is not a DM or admin.
    """

    @classmethod
    def new(cls, bot: G0T0Bot, owner: Member, adventure: Adventure):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.adventure = adventure

        return inst
    
    @button(label="Manage DM(s)", style=ButtonStyle.primary, row=1)
    async def adventure_dm(self, _: Button, interaction: Interaction):
        self.dm_select = True
        await self.defer_to(_AdventureMemberSelect, interaction)

    @button(label="Manage Player(s)", style=ButtonStyle.primary, row=1)
    async def adventure_players(self, _: Button, interaction: Interaction):
        self.dm_select = False
        await self.defer_to(_AdventureMemberSelect, interaction)

    @button(label="Reward CC", style=ButtonStyle.green, row=2)
    async def adventure_reward(self, _: Button, interaction: Interaction):
        modal = AdventureRewardModal(self.adventure)
        response = await self.prompt_modal(interaction, modal)

        if response.cc > 0:
            self.adventure.cc += response.cc

            dm_reward = response.cc + ceil(response.cc * .25)
            for dm in self.adventure.dms:
                player = await self.bot.get_player(dm, interaction.guild.id)
                await self.bot.log(interaction, player, self.owner, "ADVENTURE_DM",
                                   notes=f"{self.adventure.name}",
                                   cc=dm_reward,
                                   adventure=self.adventure,
                                   silent=True)
            
            player_reward = response.cc

            for character in self.adventure.player_characters:
                player = await self.bot.get_player(character.player_id, interaction.guild.id)
                await self.bot.log(interaction, player, self.owner, "ADVENTURE",
                                   character=character,
                                   notes=f"{self.adventure.name}",
                                   cc=player_reward,
                                   adventure=self.adventure,
                                   silent=True)            
            await interaction.channel.send(embed=AdventureRewardEmbed(interaction, self.adventure, response.cc))
        await self.refresh_content(interaction)

    @button(label="NPCs", style=ButtonStyle.primary, row=2)
    async def npcs(self, _: Button, interaction: Interaction):
        guild = await self.bot.get_player_guild(self.adventure.guild_id)
        view = NPCSettingsUI.new(self.bot, self.owner, guild, AdventureSettingsUI,
                               adventure=self.adventure)
        await view.send_to(interaction)

    @button(label="Factions", style=ButtonStyle.primary, row=2)
    async def factions(self, _: Button, interaction: Interaction):
        await self.defer_to(_AdventureFactions, interaction)

    @button(label="Close Adventure", style=ButtonStyle.danger, row=2)
    async def adventure_close(self, _: Button, interaction: Interaction):
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
                            await self.bot.log(interaction, player, self.owner, "RENOWN",
                                               character=char,
                                               notes=f"Adventure Reward: {self.adventure.name}",
                                               renown=amount,
                                               faction=faction,
                                               silent=True)
            
            # Close adventure and clean up role
            self.adventure.end_ts = datetime.now(timezone.utc)
            try:
                await self.adventure.role.delete(reason=f"Closing adventure")
            except:
                pass
            await self.adventure.upsert()

            # NPC Cleanup
            for npc in self.adventure.npcs:
                await npc.delete()

            await self.on_timeout()
        

    @button(label="Exit", style=ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self):
        if self.owner.id not in self.adventure.dms and not is_admin:
            self.remove_item(self.adventure_dm)
            self.remove_item(self.adventure_players)
            self.remove_item(self.adventure_close)
    
class _AdventureMemberSelect(AdventureView):
    async def _before_send(self):
        self.add_member.disabled = False if self.character else True
        self.remove_member.disabled = False if self.character else True

    @user_select(placeholder="Select a Player", row=1)
    async def member_select(self, user: Select, interaction: Interaction):
        member: Member = user.values[0]
        self.member = member
        self.player = await self.bot.get_player(self.member.id, interaction.guild.id)
        self.character = None
        if not self.dm_select and self.get_item("char_select") is None:
            self.add_item(self.character_select)
        await self.refresh_content(interaction)

    @select(placeholder="Select a character", options=[SelectOption(label="You should never see me")], row=2, custom_id="char_select")
    async def character_select(self, char: Select, interaction: Interaction):
        self.character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interaction)

    @button(label="Add Player", row=3)
    async def add_member(self, _: Button, interaction: Interaction):
        if self.dm_select:
            if self.member.id in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is already a DM of this adventure"), delete_after=5)
            elif character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} can't be a player and a DM"), delete_after=5)
            else:
                self.adventure.dms.append(self.member.id)
                await self.adventure.update_dm_permissions(self.member)
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

                if self.adventure.role not in self.member.roles:
                    await self.member.add_roles(self.adventure.role, reason=f"{self.character.name} added to {self.adventure.name} by {self.owner.name}")
            
                await interaction.channel.send(f"{self.character.name} ({self.member.mention}) added to {self.adventure.name}")

        await self.refresh_content(interaction)
        
    @button(label="Remove Player", row=3)
    async def remove_member(self, _: Button, interaction: Interaction):
        if self.dm_select:
            if self.member.id not in self.adventure.dms:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not a DM of this adventure"), delete_after=5)
            elif len(self.adventure.dms) == 1:
                await interaction.channel.send(embed=ErrorEmbed(f"Cannot remove the last DM. Either add another one first, or close the adventure"), delete_after=5)
            else:
                self.adventure.dms.remove(self.member.id)
                await self.adventure.update_dm_permissions(self.member, True)
                await self.adventure.upsert()
        else:
            if character := next((ch for ch in self.adventure.player_characters if ch.player_id == self.player.id), None):
                self.adventure.player_characters.remove(character)
                self.adventure.characters.remove(character.id)

                if self.adventure.role in self.member.roles:
                    await self.member.remove_roles(self.adventure.role, reason=f"Removed from {self.adventure.name} by {self.owner.name}")
            else:
                await interaction.channel.send(embed=ErrorEmbed(f"{self.member.mention} is not part of this adventure"), delete_after=5)
                
            
        await self.refresh_content(interaction)


    @button(label="Back", style=ButtonStyle.grey, row=4)
    async def back(self, _: Button, interaction: Interaction):
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

class _AdventureFactions(AdventureView):
    faction: Faction = None

    async def _before_send(self):
        faction_list = [SelectOption(label=f"{f.value}", value=f"{f.id}", default=True if self.faction and self.faction.id == f.id else False) for f in self.bot.compendium.faction[0].values()]

        self.faction_select.options = faction_list

        self.add_faction.disabled = False if self.faction else True
        self.remove_faction.disabled = False if self.faction else True

    @select(placeholder="Select a faction", row=1)
    async def faction_select(self, f: Select, interaction: Interaction):
        self.faction = self.bot.compendium.get_object(Faction, int(f.values[0]))
        await self.refresh_content(interaction)

    @button(label="Add Faction", style=ButtonStyle.primary, row=2)
    async def add_faction(self, _: Button, interaction: Interaction):
        if self.faction and self.faction.id not in [f.id for f in self.adventure.factions]:
            if len(self.adventure.factions) >= 2 and not is_admin:
                await interaction.channel.send(embed=ErrorEmbed(f"You do not have the ability to add more than 2 factions to an adventure"), delete_after=5)
            else:
                self.adventure.factions.append(self.faction)
        await self.refresh_content(interaction)

    @button(label="Remove Faction", style=ButtonStyle.primary, row=2)
    async def remove_faction(self, _: Button, interaction: Interaction):
        if self.faction and self.faction.id in [f.id for f in self.adventure.factions]:
            faction = next((f for f in self.adventure.factions if f.id == self.faction.id), None)
            self.adventure.factions.remove(faction)
        await self.refresh_content(interaction)

    @button(label="Back", style=ButtonStyle.grey, row=3)
    async def back(self, _: Button, interaction: Interaction):
        self.faction = None
        await self.defer_to(AdventureSettingsUI, interaction)   
    
class AdventureRewardModal(Modal):
    adventure: Adventure
    cc: int = 0

    def __init__(self, adventure: Adventure):
        super().__init__(title=f"{adventure.name} Rewards")
        self.adventure = adventure

        self.add_item(InputText(label="CC Amount", required=True, placeholder="CC Amount", max_length=3))

    async def callback(self, interaction: Interaction):
        try:
            self.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed(f"Chain codes must be a number!"), delete_after=5)
        
        await interaction.response.defer()
        self.stop()