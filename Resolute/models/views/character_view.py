from typing import Mapping
import discord
import re

from discord.ui.button import Button
from discord.ui import Modal, InputText
from discord import SelectOption

from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.helpers.characters import create_new_character, get_character, upsert_character, upsert_class, upsert_starship
from Resolute.helpers.general_helpers import confirm, get_webhook, is_admin, isImageURL, process_message
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player, manage_player_roles
from Resolute.models.categories import CharacterClass, CharacterSpecies, Activity
from Resolute.models.categories.categories import CharacterArchetype, Faction, StarshipSize
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.characters import CharacterEmbed, CharacterSettingsEmbed, LevelUpEmbed, NewCharacterSetupEmbed, NewcharacterEmbed, StarshipEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player, PlayerCharacter
from Resolute.models.objects.characters import CharacterRenown, CharacterStarship, PlayerCharacterClass
from Resolute.models.views.base import InteractiveView

# Character Manage Base setup
class CharacterManage(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "guild", "active_character", "active_ship")
    bot: G0T0Bot
    owner: discord.Member = None
    player: Player
    guild: PlayerGuild
    active_character: PlayerCharacter = None
    active_ship: CharacterStarship = None


# Main Character Manage UI
class CharacterManageUI(CharacterManage):
    @classmethod
    def new(cls, bot, owner, player, playerGuild):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.player = player
        inst.guild = playerGuild
        inst.new_character = PlayerCharacter(player_id=player.id, guild_id=playerGuild.id)
        inst.new_class = PlayerCharacterClass()
        inst.active_character = player.characters[0] if len(player.characters) > 0 else None
        return inst
    
    @discord.ui.select(placeholder="Select a character to manage", row=1)
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        self.active_character = self.player.characters[int(char.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, row=2)
    async def edit_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

    @discord.ui.button(label="New/Reroll", style=discord.ButtonStyle.green, row=2)
    async def new_character_create(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_NewCharacter, interaction)

    @discord.ui.button(label="Inactivate", style=discord.ButtonStyle.danger, row=2)
    async def inactivate_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_InactivateCharacter, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()
        
    async def _before_send(self):
        if len(self.player.characters) == 0:
            self.remove_item(self.edit_character)
            self.remove_item(self.character_select)
            self.new_character_create.label = "New Character"
        else:
            # Build the Character List
            char_list  = []
            for char in self.player.characters:
                char_list.append(SelectOption(label=f"{char.name}", value=f"{self.player.characters.index(char)}", default=True if self.player.characters.index(char) == self.player.characters.index(self.active_character) else False))
            self.character_select.options = char_list

        if not is_admin or len(self.player.characters) == 0:
            self.remove_item(self.inactivate_character)
    
    async def get_content(self) -> Mapping:
        embed = PlayerOverviewEmbed(self.player, self.guild, self.bot.compendium)

        return {"embed": embed, "content": ""}

# Character Manage - New Character 
class _NewCharacter(CharacterManage):
    def __init__(self, owner: discord.Member, *args, **kwargs):
        super().__init__(owner, *args, **kwargs)
        self.new_type = None
        self.transfer_ship = False
        self.new_character = PlayerCharacter()
        self.new_class = PlayerCharacterClass()
        self.new_cc = 0
        self.new_credits = 0

    @discord.ui.select(placeholder="Select new type", row=1)
    async def new_character_type(self, type: discord.ui.Select, interaction: discord.Interaction):
        self.new_type = type.values[0]
        if self.new_type == "new":
            self.transfer_ship = False
        await self.refresh_content(interaction)

    @discord.ui.button(label="Basic Information", style=discord.ButtonStyle.primary, row=2)
    async def new_character_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NewCharacterInformationModal(self.new_character, self.active_character, self.new_cc, self.new_credits, self.new_type, self.transfer_ship)
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_cc = response.new_cc
        self.new_credits = response.new_credits
        self.transfer_ship = response.transfer_ship

        await self.refresh_content(interaction)

    @discord.ui.button(label="Species/Class Information", style=discord.ButtonStyle.primary, row=2)
    async def new_character_species(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NewCharacterClassSpeciesModal(self.new_character, self.new_class, self.bot.compendium)
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_class = response.char_class

        await self.refresh_content(interaction)

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.green, row=3, disabled=True)
    async def new_character_create(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.new_character = await create_new_character(self.bot, self.new_type, self.player, self.new_character, self.new_class,
                                                        old_character=self.active_character,
                                                        transfer_ship=self.transfer_ship)

        new_activity = self.bot.compendium.get_activity("new_character")

        log_entry = await create_log(self.bot, self.owner, self.guild, new_activity, self.player, 
                                     character=self.new_character, 
                                     notes="Initial Log",
                                     cc=self.new_cc, 
                                     credits=self.new_credits,
                                     ignore_handicap=True)
        
        self.player = await get_player(self.bot, self.player.id, self.guild.id)

        await manage_player_roles(self.player, "Character Created!")

        await interaction.channel.send(embed=NewcharacterEmbed(self.owner, self.player, self.new_character, log_entry, self.bot.compendium))

        if self.guild.first_character_message and self.guild.first_character_message != "" and self.guild.first_character_message is not None and len(self.player.characters) == 1:
            mappings = {"character.name": self.new_character.name,
                        "character.level": str(self.new_character.level)}
            await interaction.channel.send(process_message(self.guild.first_character_message, self.guild, self.player.member, mappings))

        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)

    async def _before_send(self):
        new_character_type_options = []
        if len(self.player.characters) == 0 or len(self.player.characters) < self.guild.max_characters:
            self.new_type = 'new' if len(self.player.characters) == 0 else self.new_type
            new_character_type_options.append(SelectOption(label="New Character", value="new", default= True if self.new_type == "new" else False))
        
        if len(self.player.characters) > 0:
            new_character_type_options.append(SelectOption(label="Death Reroll", value="death", default=True if self.new_type == "death" else False))
            new_character_type_options.append(SelectOption(label="Free Reroll", value="freeroll", default=True if self.new_type == "freeroll" else False))

        self.new_character_type.options = new_character_type_options

        if self.new_type and self.new_character.is_valid(self.guild) and self.new_class.is_valid() and (self.player.cc + self.new_cc >= 0):
            self.new_character_create.disabled=False
        else:
            self.new_character_create.disabled=True

        pass

    async def get_content(self) -> Mapping:
        embed = NewCharacterSetupEmbed(self.player, self.guild, self.new_character, self.new_class, self.new_credits, self.new_cc, self.transfer_ship)
        return {"embed": embed, "content": ""}

# Character Manage - Inactivate Character
class _InactivateCharacter(CharacterManage):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def inactivate_character_confirm(self, _: Button, interaction: discord.Interaction):
        self.active_character.active = False
        activity = self.bot.compendium.get_activity("MOD_CHARACTER")

        log_entry = await create_log(self.bot, self.owner, self.guild, activity, self.player, 
                                     character=self.active_character, 
                                     notes="Inactivating Character")

        await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.player.member, self.active_character))

        await self.on_timeout()


    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)
        

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character, self.bot.compendium), "content": "Are you sure you want to inactivate this character?"}

# Character Manage - Edit Character
class _EditCharacter(CharacterManage):
    @discord.ui.button(label="Manage Classes", style=discord.ButtonStyle.primary, row=1)
    async def manage_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterClass, interaction)

    @discord.ui.button(label="Manage Ships", style=discord.ButtonStyle.primary, row=1)
    async def manage_ship(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterShips, interaction)

    @discord.ui.button(label="Manage Renown", style=discord.ButtonStyle.primary, row=1)
    async def manage_renown(self, _: discord.ui.Button, interaction: discord.Interaction):
        # TODO: Update this to route to the new view
        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit Information", style=discord.ButtonStyle.primary, row=2)
    async def edit_character_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterInformationModal(self.active_character, self.bot.compendium)
        response: CharacterInformationModal = await self.prompt_modal(interaction, modal)

        if response.update and (activity := self.bot.compendium.get_object(Activity, "MOD_CHARACTER")):
            await create_log(self.bot, self.owner, self.guild, activity, self.player, 
                             character=self.active_character,
                             notes="Character Modification")

        await self.refresh_content(interaction)

    @discord.ui.button(label="Level Up", style=discord.ButtonStyle.primary, row=2)
    async def level_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.player.highest_level_character.level < 3 and (self.player.needed_rps > self.player.completed_rps or self.player.needed_arenas > self.player.completed_arenas):
            await interaction.channel.send(embed=ErrorEmbed(f"{self.player.member.mention} has not completed their requirements to level up.\n"
                                                      f"Completed RPs: {min(self.player.completed_rps, self.player.needed_rps)}/{self.player.needed_rps}\n"
                                                      f"Completed Arena Phases: {min(self.player.completed_arenas, self.player.needed_arenas)}/{self.player.needed_arenas}"),
                                                      delete_after=5)
        elif (activity := self.bot.compendium.get_object(Activity, "LEVEL")):
            self.active_character.level += 1
            await create_log(self.bot, self.owner, self.guild, activity, self.player,
                             character=self.active_character,
                             notes="Player level up")
            await manage_player_roles(self.player, "Level up")

            await interaction.channel.send(embed=LevelUpEmbed(self.player, self.active_character))

        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)

    async def _before_send(self):
        if self.active_character.level+1 > self.guild.max_level:
            self.level_character.disabled = True
        else:
            self.level_character.disabled = False
        pass

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character, self.bot.compendium), "content": ""}

# Character Manage - Edit Character Class
class _EditCharacterClass(CharacterManage):
    active_class: PlayerCharacterClass = None

    @discord.ui.select(placeholder="Select class", row=1)
    async def select_class(self, char_class: discord.ui.Select, interaction: discord.Interaction):
        self.active_class = self.active_character.classes[int(char_class.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Class", style=discord.ButtonStyle.grey, row=2)
    async def new_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterClassModal(self.active_character, self.bot.compendium)
        response: CharacterClassModal = await self.prompt_modal(interaction, modal)
        new_class = PlayerCharacterClass(character_id=self.active_character.id, primary_class=response.primary_class, archetype=response.archetype)

        if new_class.primary_class:
           new_class = await upsert_class(self.bot, new_class)
           self.active_character.classes.append(new_class)
           
        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit Class", style=discord.ButtonStyle.grey, row=2)
    async def edit_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterClassModal(self.active_character, self.bot.compendium, self.active_class)
        response = await self.prompt_modal(interaction, modal)

        if response.primary_class and (response.primary_class != self.active_class.primary_class or response.archetype != self.active_class.archetype):
            self.active_class.primary_class = response.primary_class
            self.active_class.archetype = response.archetype
            await upsert_class(self.bot, self.active_class)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Delete Class", style=discord.ButtonStyle.red, row=2)
    async def delete_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        if len(self.active_character.classes) == 1:
            await interaction.channel.send(embed=ErrorEmbed(f"Character only has one class"), delete_after=5)
        else:
            self.active_character.classes.pop(self.active_character.classes.index(self.active_class))
            self.active_class.active = False
            await upsert_class(self.bot, self.active_class)
            self.active_class = self.active_character.classes[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

    async def _before_send(self):
        if not self.active_class:
            self.active_class = self.active_character.classes[0]
        class_list = []
        for char_class in self.active_character.classes:
            class_list.append(SelectOption(label=f"{char_class.get_formatted_class()}", value=f"{self.active_character.classes.index(char_class)}", default=True if self.active_class and self.active_character.classes.index(char_class) == self.active_character.classes.index(self.active_class) else False))
        self.select_class.options = class_list

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character, self.bot.compendium), "content": ""}
    
# Character Manage - Edit Renown
class _EditCharacterRenown(CharacterManage):
    active_renown: CharacterRenown = None

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def select_faction(self, fac: discord.ui.Select, interaction: discord.Interaction):
        faction = self.bot.compendium.get_object(Faction, int(fac.values[0]))
      
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

# Character Manage - Edit Starships
class _EditCharacterShips(CharacterManage):

    @discord.ui.select(placeholder="Select a ship", row=1, options=[SelectOption(label="Placeholder")])
    async def select_ship(self, ship: discord.ui.Select, interaction: discord.Interaction):
        self.active_ship = self.active_character.starships[int(ship.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Ship", style=discord.ButtonStyle.grey, row=2)
    async def add_ship(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = StarshipModal(self.active_character, self.bot.compendium)
        response = await self.prompt_modal(interaction, modal)

        if response.starship and response.starship is not None:
            starship = await upsert_starship(self.bot, response.starship)
            self.active_character.starships.append(starship)
            
        await self.refresh_content(interaction)


    @discord.ui.button(label="Edit Ship", style=discord.ButtonStyle.grey, row=2)
    async def edit_ship(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditStarship, interaction)

    @discord.ui.button(label="Delete Ship", style=discord.ButtonStyle.red, row=2)
    async def delete_ship(self, _: discord.ui.Button, interaction: discord.Interaction):
        owners = ", ".join([f"{char.name} ( {self.guild.guild.get_member(char.player_id).mention} )" for char in self.active_ship.owners])
        conf = await confirm(interaction, f"Are you sure you want to inactivate `{self.active_ship.get_formatted_starship(self.bot.compendium)}` for {owners}? (Reply with yes/no)", True)

        if conf is None:
            await interaction.channel.send(embed=ErrorEmbed(f"Timed out waiting for a response or invalid response."), delete_after=5)
            await self.refresh_content(interaction)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed(f"Ok, cancelling"), delete_after=5)
            await self.refresh_content(interaction)
        else:
            self.active_ship.active = False
            self.active_character.starships.remove(self.active_ship)
            await upsert_starship(self.bot, self.active_ship)
            await self.defer_to(_EditCharacter, interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

    async def _before_send(self):
        if not self.active_character.starships:
            self.remove_item(self.select_ship)
        else:
            if not self.active_ship:
                self.active_ship = self.active_character.starships[0]
                
            self.active_ship.owners = []
            for char_id in self.active_ship.character_id:
                character = await get_character(self.bot, char_id)
                self.active_ship.owners.append(character)


            ship_options = []
            for ship in self.active_character.starships:
                ship_options.append(SelectOption(label=f"{ship.name}", value=f"{self.active_character.starships.index(ship)}", default=True if self.active_ship and self.active_character.starships.index(ship) == self.active_character.starships.index(self.active_ship) else False))
            self.select_ship.options = ship_options

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character, self.bot.compendium), "content": ""}

# Character Manage - Edit Starship
class _EditStarship(CharacterManage):
    @discord.ui.button(label="Edit Information", style=discord.ButtonStyle.grey, row=1)
    async def edit_ship_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = StarshipModal(self.active_character, self.bot.compendium, self.active_ship)

        response = await self.prompt_modal(interaction, modal)

        if response.starship:
            await upsert_starship(self.bot, self.active_ship)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Edit Owners", style=discord.ButtonStyle.grey, row=1)
    async def edit_ship_owners(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditStarshipOwners, interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterShips, interaction)

    async def get_content(self) -> Mapping:
        return {"embed": StarshipEmbed(self.bot, self.player, self.active_ship), "content": ""}
    
class _EditStarshipOwners(CharacterManage):
    owner_member: discord.Member = None
    owner_player: Player = None
    owner_character: PlayerCharacter = None

    @discord.ui.user_select(placeholder="Select a Player", row=1)
    async def member_select(self, user: discord.ui.Select, interaction: discord.Interaction):
        member: discord.Member = user.values[0]
        self.owner_member = member
        self.owner_player = await get_player(self.bot, member.id, interaction.guild.id)
        self.owner_character = None

        if self.get_item("ship_char_select") is None:
            self.add_item(self.character_select)

        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Select a character", options=[SelectOption(label="You should never see me")], row=2, custom_id="ship_char_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        self.owner_character = self.owner_player.characters[int(char.values[0])]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Player", row=3)
    async def add_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.owner_member is None:
            await interaction.channel.send(embed=ErrorEmbed(f"Select someone to add"), delete_after=5)
        elif self.owner_character is None:
            await interaction.channel.send(embed=ErrorEmbed(f"Select a character to add"), delete_after=5)
        elif self.owner_character.id in self.active_ship.character_id:
            await interaction.channel.send(embed=ErrorEmbed(f"Character is already an owner of this ship"), delete_after=5)
        else:
            self.active_ship.character_id.append(self.owner_character.id)
            self.active_ship.owners.append(self.owner_character)
            await upsert_starship(self.bot, self.active_ship)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Player", row=3)
    async def remove_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if len(self.active_ship.character_id) == 1:
            await interaction.channel.send(embed=ErrorEmbed(f"Can't remove the last owner. Either add someone first or delete the ship"), delete_after=5)
        elif self.owner_member is None:
            await interaction.channel.send(embed=ErrorEmbed(f"Select someone to remove"), delete_after=5)
        elif self.owner_character is None:
            self.owner_character = next((ch for ch in self.owner_player.characters if ch.id in self.active_ship.character_id), None)

        if self.owner_character is None:
            await interaction.channel.send(embed=ErrorEmbed(f"Select a character to remove"), delete_after=5)
        else:
            self.active_ship.character_id.remove(self.owner_character.id)
            self.active_ship.owners = [owner for owner in self.active_ship.owners if owner.id != self.owner_character.id]
            if self.owner_member == self.player.member:
                self.active_character.starships.remove(self.active_ship)

            await upsert_starship(self.bot, self.active_ship)
            
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditStarship, interaction)

    async def _before_send(self):
        if self.owner_member is None:
            self.remove_item(self.character_select)
        else:
            if self.owner_player.characters:
                char_list = []
                if self.owner_character is None:
                    self.owner_character = self.owner_player.characters[0]

                for char in self.owner_player.characters:
                    char_list.append(SelectOption(label=f"{char.name}", value=f"{self.owner_player.characters.index(char)}", default=True if self.owner_character and  self.owner_player.characters.index(char) == self.owner_player.characters.index(self.owner_character) else False))
                self.character_select.options = char_list
            else:
                self.remove_item(self.character_select)

    async def get_content(self) -> Mapping:
        return {"embed": StarshipEmbed(self.bot, self.player, self.active_ship), "content": ""}

# Character Manage Modals    
class NewCharacterInformationModal(Modal):
    character: PlayerCharacter
    active_character: PlayerCharacter
    new_cc: int
    new_credits: int
    new_type: str
    transfer_ship: bool

    def __init__(self, character, active_character, new_cc: int = 0, new_credits: int = 0, new_type: str = None, transfer_ship: bool = False):
        super().__init__(title=f"{character.name if character.name else 'New Character'} Setup")
        self.character = character
        self.active_character = active_character
        self.new_cc = new_cc
        self.new_credits = new_credits
        self.new_type=new_type
        self.transfer_ship = transfer_ship

        self.add_item(InputText(label="Character Name", style=discord.InputTextStyle.short, required=True, placeholder="Character Name", max_length=2000, value=self.character.name if self.character.name else ''))
        self.add_item(InputText(label="Level", style=discord.InputTextStyle.short, required=True, placeholder="Level", max_length=2, value=str(self.character.level)))
        self.add_item(InputText(label="Credits", style=discord.InputTextStyle.short, required=True, placeholder="Credits", max_length=7, value=str(self.new_credits)))
        self.add_item(InputText(label="CC Refund/Adjustment", style=discord.InputTextStyle.short, required=False, placeholder="Chain Codes", max_length=7, value=str(self.new_cc)))

        if self.new_type in ['freeroll', 'death'] and len(self.active_character.starships) > 0:
            self.add_item(InputText(label="Transfer Ship to new character?", style=discord.InputTextStyle.short, required=False, placeholder="Transfer Ship?", max_length=5, value=self.transfer_ship))

    
    async def callback(self, interaction: discord.Interaction):        
        err_str = []
        self.character.name = self.children[0].value
        self.transfer_ship = self.children[4].value if len(self.children) >= 5 and self.children[4] else False
        int_values = [
            (self.children[2].value, "new_credits", "Credits must be a number!"),
            (self.children[3].value, "new_cc", "Chain codes must be a number!")
        ]

        for value, node, err_msg in int_values:
            try:
                setattr(self, node, int(value))
            except:
                err_str.append(err_msg)

        try:
            self.character.level = int(self.children[1].value)
        except:
            err_str.append("Level must be a number!")

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()

class NewCharacterClassSpeciesModal(Modal):
    compendium: Compendium
    character: PlayerCharacter
    char_class: PlayerCharacterClass

    def __init__(self, character, char_class, compendium):
        super().__init__(title=f"{character.name if character.name else 'New Character'} Setup")
        self.character = character
        self.char_class = char_class
        self.compendium = compendium

        self.add_item(InputText(label="Species", style=discord.InputTextStyle.short, required=True, placeholder="Species", max_length=100, value=self.character.species.value if hasattr(self.character.species, "value") else ''))
        self.add_item(InputText(label="Class", style=discord.InputTextStyle.short, required=True, placeholder="Class", max_length=100, value=self.char_class.primary_class.value if hasattr(self.char_class, "primary_class") and self.char_class.primary_class else ''))
        self.add_item(InputText(label="Archetype", style=discord.InputTextStyle.short, required=False, placeholder="Archetype", max_length=100, value=self.char_class.archetype.value if hasattr(self.char_class, "archetype") and self.char_class.archetype else ''))

    async def callback(self, interaction: discord.Interaction):
        err_str = []

        if species := self.compendium.get_object(CharacterSpecies, self.children[0].value):
            self.character.species = species
        else:
            err_str.append(f"`{self.children[0].value}` is not a valid species!")

        if primary_class := get_primary_class(self.children[1].value, self.compendium, err_str):
            self.char_class.primary_class = primary_class

            if self.children[2].value != '' and (archetype := get_archetype(self.children[2].value, primary_class, self.compendium, err_str)):
                self.char_class.archetype = archetype
            else:
                self.char_class.archetype = None

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()

class CharacterClassModal(Modal):
    compendium: Compendium
    character: PlayerCharacter
    char_class: CharacterClass
    primary_class: CharacterClass
    archetype: CharacterArchetype

    def __init__(self, character, compendium, char_class: PlayerCharacterClass = None):
        super().__init__(title=f"Class for {character.name}")

        self.character = character
        self.char_class = char_class or PlayerCharacterClass(character_id=character.id)
        self.primary_class = self.char_class.primary_class or None
        self.archetype = self.char_class.archetype or None
        self.compendium = compendium

        self.add_item(InputText(label="Class", style=discord.InputTextStyle.short, required=True, placeholder="Class", max_length=100, value=self.primary_class.value if self.primary_class else ''))
        self.add_item(InputText(label="Archetype", style=discord.InputTextStyle.short, required=False, placeholder="Archetype", max_length=100, value=self.archetype.value if self.archetype else ''))
    
    async def callback(self, interaction: discord.Interaction):            
        err_str = []
        if primary_class := get_primary_class(self.children[0].value, self.compendium, err_str):
            self.primary_class = primary_class

            if self.children[1].value != '' and (archetype := get_archetype(self.children[1].value, primary_class, self.compendium, err_str)):
                self.archetype = archetype
            else:
                self.archetype = None
        else:
            self.primary_class = None

        if self.primary_class:
            for char_class in self.character.classes:
                if char_class.primary_class == self.primary_class and char_class.archetype == self.archetype:
                    if hasattr(self.char_class, "id") and self.char_class.id == char_class.id:
                        pass
                    else:
                        err_str.append(f"Duplicate classes are not allowed")
                        self.primary_class = None
                        self.archetype = None

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()

class CharacterInformationModal(Modal):
    character: PlayerCharacter
    compendium: Compendium

    def __init__(self, character: PlayerCharacter, compendium: Compendium):
        super().__init__(title=f"Information for {character.name}")
        self.character = character
        self.compendium = compendium
        self.update = False

        self.add_item(InputText(label="Character Name", style=discord.InputTextStyle.short, required=True, placeholder="Character Name", max_length=2000, value=self.character.name if self.character.name else ''))
        self.add_item(InputText(label="Species", style=discord.InputTextStyle.short, required=True, placeholder="Species", max_length=100, value=self.character.species.value if hasattr(self.character.species, "value") else ''))

    async def callback(self, interaction: discord.Interaction):
        if self.character.name != self.children[0].value:
                self.character.name = self.children[0].value
                self.update = True
        
        if species := self.compendium.get_object(CharacterSpecies, self.children[1].value):
            if self.character.species != species:
                self.character.species = species
                self.update = True
        await interaction.response.defer()
        self.stop()

class StarshipModal(Modal):
    character: PlayerCharacter
    compendium: Compendium
    starship: CharacterStarship

    def __init__(self, character: PlayerCharacter, compendium: Compendium, starship: CharacterStarship = None):
        super().__init__(title=f"Starship for {character.name}")

        self.character = character
        self.compendium = compendium
        self.starship = starship or CharacterStarship(character_id=[self.character.id])
        
        self.add_item(InputText(label="Ship Name", placeholder="Ship Name", max_length=200, value=self.starship.name))
        self.add_item(InputText(label="Ship Tier", placeholder="Ship Tier", max_length=2, value=f"{self.starship.tier}"))

        if not starship:
            self.add_item(InputText(label="Ship Size", placeholder="Ship Size", max_length=10))
            self.add_item(InputText(label="Ship Role", placeholder="Ship Role", max_length=50))
        

    async def callback(self, interaction: discord.Interaction):
        err_str = []
        try:
            self.starship.tier = int(self.children[1].value)
            self.starship.name = self.children[0].value
        except:
            self.starship = None
            err_str.append("Tier must be a number")

        if self.starship and (not hasattr(self.starship, "id") or self.starship.id is None):
            if ship_size := get_ship_size(self.children[2].value, self.compendium, err_str):
                if ship_role := get_ship_role(self.children[3].value, ship_size, self.compendium, err_str):
                    self.starship.starship = ship_role
                else:
                    self.starship = None
            else:
                self.starship = None

        if len(err_str) > 0:
            await interaction.channel.send(embed=ErrorEmbed("\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()
        

# Character Manage View specific helpers
def get_primary_class(class_value: str, compendium: Compendium, err_str: list = []):
    primary_class = compendium.get_object(CharacterClass, class_value)

    if not primary_class:
        class_value = re.sub(f'light|dark', '', class_value)
        primary_class = compendium.get_object(CharacterClass, class_value)

    if primary_class:
        return primary_class
    else:
        err_str.append(f"`{class_value}` is not a valid primary class")
        return None
    
def get_archetype(archetype_value: str, primary_class: CharacterClass, compendium: Compendium, err_str: list = []):
    valid_archetypes = [x for x in compendium.archetype[0].values() if x.parent == primary_class.id]

    archetype = next((at for at in valid_archetypes if archetype_value.lower() in at.value.lower()), None)

    if archetype:
        return archetype
    else:
        err_str.append(f"`{archetype_value}` is not a valid archetype for {primary_class.value}")
        return None
    
def get_ship_size(size_value: str, compendium: Compendium, err_str: list = []):
    ship_size = compendium.get_object(StarshipSize, size_value)

    if ship_size:
        return ship_size
    else:
        err_str.append(f"`{size_value}` is not a valid ship size")
        return None

def get_ship_role(role_value: str, ship_size: StarshipSize, compendium: Compendium, err_str: list = []):
    valid_roles = [x for x in compendium.starship_role[0].values() if x.size == ship_size.id]

    ship_role = next((r for r in valid_roles if role_value.lower() in r.value.lower()), None)

    if ship_role:
        return ship_role
    else:
        err_str.append(f"`{role_value}` is not a valid role for a {ship_size.value} ship")
        return None

# Say Edit
class SayEditModal(Modal):
    message: discord.Message

    def __init__(self, message: discord.Message = None):
        super().__init__(title="Edit Message")
        self.message = message

        self.add_item(InputText(label="Message", placeholder="", value=message.content, style=discord.InputTextStyle.long))

    async def callback(self, interaction: discord.Interaction):
        webook = await get_webhook(interaction.channel)

        try:
            await webook.edit_message(self.message.id, content=self.children[0].value)
        except:
            pass

        await interaction.response.defer()
        self.stop()

# Character Settings
class CharacterSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "active_character", "guild")

    bot: G0T0Bot
    player: Player
    guild: PlayerGuild
    active_character: PlayerCharacter = None
    active_channel: discord.TextChannel = None

    async def commit(self):
        await upsert_character(self.bot, self.active_character)
        self.player = await get_player(self.bot, self.player.id, self.guild.id)

    async def get_content(self) -> Mapping:
        embed = CharacterSettingsEmbed(self.player, self.active_character)

        return {"embed": embed, "content": ""}

class CharacterSettingsUI(CharacterSettings):
    @classmethod
    def new(cls, bot, owner, player: Player, guild: PlayerGuild):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.player = player
        inst.guild = guild
        inst.active_character = player.get_primary_character() if player.get_primary_character() else player.characters[0] if len(player.characters) > 0 else None
        return inst
    
    async def _before_send(self):
        char_list = []

        for char in self.player.characters:
                char_list.append(SelectOption(label=f"{char.name}", value=f"{char.id}", default=True if char.id == self.active_character.id else False))
        self.character_select.options = char_list
    
    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        self.active_character = next((c for c in self.player.characters if c.id == int(char.values[0])), None)
        await self.refresh_content(interaction)

    @discord.ui.channel_select(channel_types=[discord.ChannelType(0)], placeholder="Select Channel to use character in", row=2)
    async def character_channel(self, chan: discord.ui.Select, interaction: discord.Interaction):
        channel = chan.values[0]
        self.active_channel = channel
        for char in self.player.characters:
            if channel.id in char.channels:
                char.channels.remove(channel.id)
                await upsert_character(self.bot, char)

        if channel.id not in self.active_character.channels:
            self.active_character.channels.append(channel.id)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Channel", style=discord.ButtonStyle.primary, row=3)
    async def add_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        for char in self.player.characters:
            if self.active_channel.id in char.channels:
                char.channels.remove(self.active_channel.id)
                await upsert_character(self.bot, char)

            if self.active_channel.id not in self.active_character.channels:
                self.active_character.channels.append(self.active_channel.id)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Channel", style=discord.ButtonStyle.secondary, row=3)
    async def remove_channel(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.active_channel.id in self.active_character.channels:
            self.active_character.channels.remove(self.active_channel.id)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove All", style=discord.ButtonStyle.danger, row=3)
    async def remove_all_channels(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.active_character.channels = []
        await self.refresh_content(interaction)

    @discord.ui.button(label="Toggle Default Character", style=discord.ButtonStyle.primary, row=4)
    async def set_default(self, _: discord.ui.Button, interaction: discord.Interaction):
        for char in self.player.characters:
            if char.primary_character:
                char.primary_character = False
                await upsert_character(self.bot, char)

        self.active_character.primary_character = True
        await self.refresh_content(interaction)

    @discord.ui.button(label="More Settings", style=discord.ButtonStyle.primary, row=4)
    async def more_settings(self, _: discord.ui.button, interaction: discord.Interaction):
        await self.defer_to(_CharacterSettings2UI, interaction)


    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=4)
    async def exit(self, *_):
        await self.on_timeout()

class _CharacterSettings2UI(CharacterSettings):
    async def _before_send(self):
        faction_list = []
        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(SelectOption(label=f"{faction.value}", value=f"{faction.id}", default=True if self.active_character.faction == faction.id else False))

        if len(faction_list) > 0:
            self.faction_select.options = faction_list
        else:
            self.remove_item(self.faction_select)

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def faction_select(self, faction: discord.ui.Select, interaction: discord.Interaction):
        self.active_character.faction = self.bot.compendium.get_object(Faction, int(faction.values[0]))
        await upsert_character(self.bot, self.active_character)
        await self.refresh_content(interaction)  

    @discord.ui.button(label="Update Avatar", style=discord.ButtonStyle.primary, row=2)
    async def update_avatar(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterAvatarModal(self.bot, self.active_character)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction) 

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterSettingsUI, interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()


class CharacterAvatarModal(Modal):
    bot: G0T0Bot
    character: PlayerCharacter

    def __init__(self, bot: G0T0Bot, character: PlayerCharacter):
        super().__init__(title="Set Character Avatar")
        self.bot = bot
        self.character = character

        self.add_item(InputText(label="Avatar Image URL", placeholder="", value=character.avatar_url))

    async def callback(self, interaction: discord.Interaction):
        url = self.children[0].value

        if isImageURL(url):
            self.character.avatar_url = self.children[0].value
            await upsert_character(self.bot, self.character)
        else:
            await interaction.response.send_message(embed=ErrorEmbed("Not a valid image url"), ephemeral=True)
            return self.stop()

        await interaction.response.defer()
        self.stop()