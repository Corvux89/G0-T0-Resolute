import re
from typing import Mapping

import discord
from discord import SelectOption
from discord.ui import InputText, Modal
from discord.ui.button import Button

from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers import (create_log, create_new_character, get_character,
                              get_player, get_webhook, is_admin, isImageURL,
                              manage_player_roles, process_message,
                              upsert_character, upsert_class)
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import update_activity_points
from Resolute.helpers.messages import get_char_name_from_message, get_player_from_say_message
from Resolute.helpers.players import build_rp_post
from Resolute.models.categories import CharacterClass, CharacterSpecies
from Resolute.models.categories.categories import CharacterArchetype, Faction
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.characters import (CharacterEmbed,
                                               CharacterSettingsEmbed,
                                               LevelUpEmbed, NewcharacterEmbed,
                                               NewCharacterSetupEmbed)
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.embeds.players import PlayerOverviewEmbed, RPPostEmbed
from Resolute.models.objects.characters import (CharacterRenown,
                                                PlayerCharacterClass)
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player, PlayerCharacter, RPPost
from Resolute.models.views.base import InteractiveView


# Character Manage Base setup
class CharacterManage(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "guild", "active_character")
    bot: G0T0Bot
    owner: discord.Member = None
    player: Player
    guild: PlayerGuild
    active_character: PlayerCharacter = None


# Main Character Manage UI
class CharacterManageUI(CharacterManage):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player, playerGuild: PlayerGuild):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.player = player
        inst.guild = playerGuild
        inst.active_character = player.characters[0] if len(player.characters) > 0 else None

        inst.new_character: PlayerCharacter = PlayerCharacter(player_id=player.id, guild_id=playerGuild.id)
        inst.new_class: PlayerCharacterClass = PlayerCharacterClass()

        return inst
    
    @discord.ui.select(placeholder="Select a character to manage", row=1)
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        self.active_character = next((c for c in self.player.characters if c.id == int(char.values[0])), None)
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
                char_list.append(SelectOption(label=f"{char.name}", value=f"{char.id}", default=True if self.active_character and char.id == self.active_character.id else False))
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
        self.new_character = PlayerCharacter()
        self.new_class = PlayerCharacterClass()
        self.transfer_renown: bool = False
        self.new_cc = 0
        self.new_credits = 0

    @discord.ui.select(placeholder="Select new type", row=1)
    async def new_character_type(self, type: discord.ui.Select, interaction: discord.Interaction):
        self.new_type = type.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Basic Information", style=discord.ButtonStyle.primary, row=3)
    async def new_character_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NewCharacterInformationModal(self.new_character, self.active_character, self.new_cc, self.new_credits, self.new_type)
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_cc = response.new_cc
        self.new_credits = response.new_credits

        await self.refresh_content(interaction)

    @discord.ui.button(label="Species/Class Information", style=discord.ButtonStyle.primary, row=3)
    async def new_character_species(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = NewCharacterClassSpeciesModal(self.new_character, self.new_class, self.bot.compendium)
        response = await self.prompt_modal(interaction, modal)

        self.new_character = response.character
        self.new_class = response.char_class

        await self.refresh_content(interaction)

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.green, row=4, disabled=True)
    async def new_character_create(self, _: discord.ui.Button, interaction: discord.Interaction):
        self.new_character = await create_new_character(self.bot, self.new_type, self.player, self.new_character, self.new_class,
                                                        old_character=self.active_character)

        log_entry = await create_log(self.bot, self.owner, "NEW_CHARACTER", self.player, 
                                     character=self.new_character, 
                                     notes="Initial Log",
                                     cc=self.new_cc, 
                                     credits=self.new_credits,
                                     ignore_handicap=True)
        
        self.player = await get_player(self.bot, self.player.id, self.guild.id)

        await manage_player_roles(self.bot, self.player, "Character Created!")

        await interaction.channel.send(embed=NewcharacterEmbed(self.owner, self.player, self.new_character, log_entry, self.bot.compendium))

        if self.guild.first_character_message and self.guild.first_character_message != "" and self.guild.first_character_message is not None and len(self.player.characters) == 1:
            mappings = {"character.name": self.new_character.name,
                        "character.level": str(self.new_character.level)}
            await interaction.channel.send(process_message(self.guild.first_character_message, self.guild, self.player.member, mappings))

        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
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
        embed = NewCharacterSetupEmbed(self.player, self.guild, self.new_character, self.new_class, self.new_credits, self.new_cc)
        return {"embed": embed, "content": ""}

# Character Manage - Inactivate Character
class _InactivateCharacter(CharacterManage):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def inactivate_character_confirm(self, _: Button, interaction: discord.Interaction):
        self.active_character.active = False

        log_entry = await create_log(self.bot, self.owner, "MOD_CHARACTER", self.player, 
                                     character=self.active_character, 
                                     notes="Inactivating Character")

        await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.player.member, self.active_character))

        await self.on_timeout()


    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterManageUI, interaction)
        

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character), "content": "Are you sure you want to inactivate this character?"}

# Character Manage - Edit Character
class _EditCharacter(CharacterManage):
    @discord.ui.button(label="Manage Classes", style=discord.ButtonStyle.primary, row=1)
    async def manage_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterClass, interaction)

    @discord.ui.button(label="Manage Renown", style=discord.ButtonStyle.primary, row=1)
    async def manage_renown(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterRenown, interaction)

    @discord.ui.button(label="Edit Information", style=discord.ButtonStyle.primary, row=2)
    async def edit_character_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterInformationModal(self.active_character, self.bot.compendium)
        response: CharacterInformationModal = await self.prompt_modal(interaction, modal)

        if response.update:
            await create_log(self.bot, self.owner, "MOD_CHARACTER", self.player, 
                             character=self.active_character,
                             notes="Character Modification")

        await self.refresh_content(interaction)

    @discord.ui.button(label="Level Up", style=discord.ButtonStyle.primary, row=2)
    async def level_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.player.highest_level_character.level < 3 and (self.player.needed_rps > self.player.completed_rps or self.player.needed_arenas > self.player.completed_arenas):

            raise G0T0Error(f"{self.player.member.mention} has not completed their requirements to level up.\n"
                            f"Completed RPs: {min(self.player.completed_rps, self.player.needed_rps)}/{self.player.needed_rps}\n"
                            f"Completed Arena Phases: {min(self.player.completed_arenas, self.player.needed_arenas)}/{self.player.needed_arenas}")
        
        self.active_character.level += 1
        await create_log(self.bot, self.owner, "LEVEL", self.player,
                            character=self.active_character,
                            notes="Player level up")
        await manage_player_roles(self.bot, self.player, "Level up")

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

    async def _before_send(self):
        if not is_admin:
            self.remove_item(self.manage_renown)

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.player, self.active_character), "content": ""}

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
            raise G0T0Error(f"Character only has one class")
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
        return {"embed": CharacterEmbed(self.player, self.active_character), "content": ""}
    
# Character Manage - Edit Renown
class _EditCharacterRenown(CharacterManage):
    faction: Faction = None

    async def _before_send(self):
        faction_list = []

        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(SelectOption(label=f"{faction.value}", value=f"{faction.id}", default=True if self.faction and self.faction.id == faction.id else False))

        self.select_faction.options = faction_list

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def select_faction(self, fac: discord.ui.Select, interaction: discord.Interaction):
        self.faction = self.bot.compendium.get_object(Faction, int(fac.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add/Remove Renown", style=discord.ButtonStyle.primary, row=2)
    async def modify_renown(self, _: discord.ui.Button, interaction: discord.Interaction):
        renown = next((r for r in self.active_character.renown if r.faction.id == self.faction.id), CharacterRenown(faction=self.faction, character_id=self.active_character.id))
        modal = CharacterRenownModal(renown)
        response = await self.prompt_modal(interaction, modal)

        if response.amount != 0:
            log_entry = await create_log(self.bot, interaction.user, "RENOWN", self.player, 
                                        character=self.active_character,
                                        renown=response.amount,
                                        faction=self.faction)

            self.active_character = await get_character(self.bot, self.active_character.id)
            await interaction.channel.send(embed=LogEmbed(log_entry, interaction.user, self.player.member, self.active_character, True))
            await self.on_timeout()
        else:
            self.refresh_content(interaction)
      
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacter, interaction)

# Character Manage Modals    
class NewCharacterInformationModal(Modal):
    character: PlayerCharacter
    active_character: PlayerCharacter
    new_cc: int
    new_credits: int
    new_type: str

    def __init__(self, character, active_character, new_cc: int = 0, new_credits: int = 0, new_type: str = None):
        super().__init__(title=f"{character.name if character.name else 'New Character'} Setup")
        self.character = character
        self.active_character = active_character
        self.new_cc = new_cc
        self.new_credits = new_credits
        self.new_type=new_type

        self.add_item(InputText(label="Character Name", style=discord.InputTextStyle.short, required=True, placeholder="Character Name", max_length=2000, value=self.character.name if self.character.name else ''))
        self.add_item(InputText(label="Level", style=discord.InputTextStyle.short, required=True, placeholder="Level", max_length=2, value=str(self.character.level)))
        self.add_item(InputText(label="Credits", style=discord.InputTextStyle.short, required=True, placeholder="Credits", max_length=7, value=str(self.new_credits)))
        self.add_item(InputText(label="CC Refund/Adjustment", style=discord.InputTextStyle.short, required=False, placeholder="Chain Codes", max_length=7, value=str(self.new_cc)))

    
    async def callback(self, interaction: discord.Interaction):        
        err_str = []
        self.character.name = self.children[0].value
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

class CharacterRenownModal(Modal):
    renown: CharacterRenown
    amount: int = 0

    def __init__(self, renown):
        super().__init__(title=f"Modify Renown")
        self.renown = renown

        self.add_item(InputText(label="Renown Amount (+/-)", placeholder="Renown Amount (+/-)", max_length=4))
    
    async def callback(self, interaction: discord.Interaction):
        try:
            amount = max(0, self.renown.renown + int(self.children[0].value))
            if amount == 0:
                await interaction.channel.send(embed=ErrorEmbed(f"Renown cannot go below `0`"))
            else:
                self.amount = int(self.children[0].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed(f"Renown must be a number!"))

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

# Say Edit
class SayEditModal(Modal):
    message: discord.Message
    bot: G0T0Bot

    def __init__(self, bot: G0T0Bot, message: discord.Message = None):
        super().__init__(title="Edit Message")
        self.bot = bot
        self.message = message

        self.add_item(InputText(label="Message", placeholder="", value=message.content, style=discord.InputTextStyle.long, max_length=2000))

    async def callback(self, interaction: discord.Interaction):
        webook = await get_webhook(interaction.channel)
        content = self.children[0].value            

        try:
            if (player := await get_player_from_say_message(self.bot, self.message)) and (char_name := get_char_name_from_message(self.message)) and (char := next((c for c in player.characters if c.name == char_name), None)):
                await player.update_post_stats(self.bot, char, self.message, retract=True)
                await player.update_post_stats(self.bot, char, self.message, content=content)
                guild = await get_guild(self.bot, player.guild_id)

                if len(content) <= ACTIVITY_POINT_MINIMUM and len(self.message.content) >= ACTIVITY_POINT_MINIMUM:
                    await update_activity_points(self.bot, player, guild, False)
                elif len(content) >= ACTIVITY_POINT_MINIMUM and len(self.message.content) <= ACTIVITY_POINT_MINIMUM:
                    await update_activity_points(self.bot, player, guild, False)
                    
            await webook.edit_message(self.message.id, content=content)
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

        self.add_channel.disabled = False if self.active_channel else True
        self.remove_channel.disabled = False if self.active_channel else True
    
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

        self.add_item(InputText(label="Avatar Image URL", placeholder="", value=character.avatar_url, required=False))

    async def callback(self, interaction: discord.Interaction):
        url = self.children[0].value

        if url and not isImageURL(url):
            await interaction.response.send_message(embed=ErrorEmbed("Not a valid image url"), ephemeral=True)
            return self.stop()
        else:
            self.character.avatar_url = self.children[0].value
            await upsert_character(self.bot, self.character)

        await interaction.response.defer()
        self.stop()

# Character Get View
class CharacterGet(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "active_character", "guild")

    bot: G0T0Bot
    player: Player
    guild: PlayerGuild
    active_character: PlayerCharacter = None

    async def get_content(self) -> Mapping:
        if self.active_character:
            embed = CharacterEmbed(self.player, self.active_character)
        else:
            embed = PlayerOverviewEmbed(self.player, self.guild, self.bot.compendium)

        return {"content": "", "embed": embed}
    
    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(view=None, embed=PlayerOverviewEmbed(self.player, self.guild, self.bot.compendium))
        except discord.HTTPException:
            pass

class CharacterGetUI(CharacterGet):
    @classmethod
    def new(cls, bot, owner, player: Player, guild: PlayerGuild):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.player = player
        inst.guild = guild
        return inst

    async def _before_send(self):
        char_list = [SelectOption(label="Player Overview", default=False if self.active_character else True, value="def")]

        for char in self.player.characters:
                char_list.append(SelectOption(label=f"{char.name}", value=f"{char.id}", default=True if self.active_character and char.id == self.active_character.id else False))
        self.character_select.options = char_list

    @discord.ui.select(placeholder="Select a character", row=1)
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        try:
            self.active_character = next((c for c in self.player.characters if c.id == int(char.values[0])), None)
        except:
            self.active_character = None

        await self.refresh_content(interaction)

# Character RP Post Request View
class RPPostView(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "posts", "message")

    bot: G0T0Bot
    player: Player
    posts: list[RPPost] = []
    orig_message: discord.Message = None

    async def get_content(self):
        return {"content": "", "embed": RPPostEmbed(self.player, self.posts)}
    
class RPPostUI(RPPostView):
    character: PlayerCharacter = None

    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player, orig_message: discord.Message = None):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.player = player
        inst.orig_message = orig_message
        inst.posts = []

        if orig_message:
            for field in orig_message.embeds[0].fields:
                if (c := next((c for c in player.characters if c.name == field.name), None)):
                    inst.posts.append(RPPost(c, note=field.value))
        return inst
    
    async def _before_send(self):
        char_list = []
        for char in self.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{char.id}", default=True if self.character and char.id == self.character.id else False))
        self.character_select.options = char_list

        self.queue_character.disabled = False if self.character else True
        self.character_select.disabled = False if len(self.posts) < 3 else True
        self.remove_character.disabled = False if self.character and next((p for p in self.posts if p.character.id == self.character.id), None) else True

    
    @discord.ui.select(placeholder="Select a character", row=1, custom_id="character_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        character = await get_character(self.bot, char.values[0])
 
        if character.player_id != interaction.user.id and interaction.user.id != self.owner.id:
            raise G0T0Error("Thats not your character")
        
        self.character = character
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Setup Post", style=discord.ButtonStyle.primary, custom_id="add_character", row=2)
    async def queue_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        post = next((p for p in self.posts if p.character.id == self.character.id), RPPost(self.character))
        modal = RPPostNoteModal(post)
        await self.prompt_modal(interaction, modal)

        if post.character not in [p.character for p in self.posts]:
            self.posts.append(post)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red, custom_id="remove_character", row=2)
    async def remove_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        if post := next((p for p in self.posts if p.character.id == self.character.id), None):
            self.posts.remove(post)
        await self.refresh_content(interaction)
        
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary, row=3)
    async def next_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        if await build_rp_post(self.bot, self.player, self.posts, self.orig_message.id if self.orig_message else None):
            await interaction.channel.send("Request Submitted!", delete_after=5)
        else:
            await interaction.channel.send("Something went wrong", delete_after=5)

        await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=3)
    async def exit_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.on_timeout()

class RPPostNoteModal(Modal):
    post: RPPost

    def __init__(self, post: RPPost):
        super().__init__(title="Post Note")
        self.post = post

        self.add_item(InputText(label="Note", placeholder="", value=self.post.note or "", required=False, style=discord.InputTextStyle.long, max_length=1000))

    async def callback(self, interaction: discord.Interaction):
        note = self.children[0].value

        self.post.note = note

        await interaction.response.defer()
        self.stop()


