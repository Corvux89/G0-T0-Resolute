from typing import Mapping
import discord
import re

from discord.ui.button import Button
from discord.ui import Modal, InputText
from timeit import default_timer as timer
from discord import SelectOption

from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.helpers.characters import get_character, upsert_class, upsert_starship
from Resolute.helpers.general_helpers import confirm, is_admin, process_message
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player, manage_player_roles
from Resolute.models.categories import CharacterClass, CharacterSpecies, Activity
from Resolute.models.categories.categories import CharacterArchetype, StarshipSize
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.characters import CharacterEmbed, LevelUpEmbed, NewCharacterSetupEmbed, NewcharacterEmbed, StarshipEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player, PlayerCharacter
from Resolute.models.objects.characters import CharacterSchema, CharacterStarship, PlayerCharacterClass, upsert_character, upsert_class_query, upsert_starship_query
from Resolute.models.views.base import InteractiveView

class CharacterSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "player", "guild", "member", "discord_guild", "active_character", "active_ship")
    bot: G0T0Bot
    owner: discord.Member = None
    player: Player
    guild: PlayerGuild
    member: discord.Member
    discord_guild: discord.Guild
    active_character: PlayerCharacter = None
    active_ship: CharacterStarship = None

class CharacterSettingsUI(CharacterSettings):
    @classmethod
    def new(cls, bot, owner, member, player, playerGuild, guild):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.member = member
        inst.player = player
        inst.discord_guild = guild
        inst.guild = playerGuild
        inst.new_character = PlayerCharacter(player_id=player.id, guild_id=guild.id)
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
        embed = PlayerOverviewEmbed(self.player, self.member, self.guild, self.bot.compendium)

        return {"embed": embed, "content": ""}

class _NewCharacter(CharacterSettings):
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
        start = timer()
        new_activity = self.bot.compendium.get_object(Activity, "new_character")
        self.new_character.player_id = self.player.id
        self.new_character.guild_id = self.guild.id

        if self.new_type == 'freeroll':
            self.new_character.freeroll_from = self.active_character.id

        if self.new_type in ['freeroll', 'death']:
            self.new_character.reroll = True
            self.active_character.active = False
            self.player.handicap_amount = 0

            async with self.bot.db.acquire() as conn:
                await conn.execute(upsert_character(self.active_character))

        async with self.bot.db.acquire() as conn:
            results = await conn.execute(upsert_character(self.new_character))
            row = await results.first()

        self.new_character = CharacterSchema(self.bot.compendium).load(row)

        self.new_class.character_id = self.new_character.id

        async with self.bot.db.acquire() as conn:
            await conn.execute(upsert_class_query(self.new_class))

        self.new_character.classes.append(self.new_class)
        
        if self.active_character:
            for ship in self.active_character.starships:
                if self.transfer_ship:
                    ship.character_id.remove(self.active_character.id)
                    ship.character_id.append(self.new_character.id)
                    self.new_character.starships.append(ship)
                else:
                    ship.active = False

                async with self.bot.db.acquire() as conn:
                    await conn.execute(upsert_starship_query(ship))

        log_entry = await create_log(self.bot, self.owner, self.guild, new_activity, self.player, self.new_character, "Initial Log",self.new_cc, self.new_credits,None,True)

        await manage_player_roles(self.discord_guild, self.member, self.player, "Character Created!")
        end = timer()
        print(f"Time to create character {self.new_character.id}: [ {end-start:.2f} ]s")
        await interaction.channel.send(embed=NewcharacterEmbed(self.owner, self.member, self.new_character, log_entry, self.bot.compendium))

        if self.guild.first_character_message and self.guild.first_character_message != "" and self.guild.first_character_message is not None and not self.player.characters:
            mappings = {"character.name": self.new_character.name,
                        "character.level": str(self.new_character.level)}
            await interaction.channel.send(process_message(self.guild.first_character_message, self.discord_guild, self.member, mappings))

        await self.on_timeout()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterSettingsUI, interaction)

    async def _before_send(self):
        new_character_type_options = []
        if len(self.player.characters) == 0 or len(self.player.characters) < self.guild.max_characters:
            self.new_type = 'new' if len(self.player.characters) == 0 else self.new_type
            new_character_type_options.append(SelectOption(label="New Character", value="new", default= True if self.new_type == "new" else False))
        
        if len(self.player.characters) > 0:
            new_character_type_options.append(SelectOption(label="Death Reroll", value="death", default=True if self.new_type == "death" else False))
            new_character_type_options.append(SelectOption(label="Free Reroll", value="freeroll", default=True if self.new_type == "freeroll" else False))

        self.new_character_type.options = new_character_type_options

        if self.new_type and self.new_character.is_valid(self.guild) and self.new_class.is_valid():
            self.new_character_create.disabled=False
        else:
            self.new_character_create.disabled=True

        pass

    async def get_content(self) -> Mapping:
        embed = NewCharacterSetupEmbed(self.player, self.member, self.guild, self.new_character, self.new_class, self.new_credits, self.new_cc, self.transfer_ship)
        return {"embed": embed, "content": ""}
    
class _InactivateCharacter(CharacterSettings):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def inactivate_character_confirm(self, _: Button, interaction: discord.Interaction):
        self.active_character.active = False
        activity = self.bot.compendium.get_object(Activity, "MOD_CHARACTER")

        log_entry = await create_log(self.bot, self.owner, self.guild, activity, self.player, self.active_character, "Inactivating Character")

        await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, self.member, self.active_character))

        await self.on_timeout()


    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterSettingsUI, interaction)
        

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.member, self.active_character, self.bot.compendium), "content": "Are you sure you want to inactivate this character?"}
    
class _EditCharacter(CharacterSettings):
    @discord.ui.button(label="Manage Classes", style=discord.ButtonStyle.primary, row=1)
    async def manage_class(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterClass, interaction)

    @discord.ui.button(label="Manage Ships", style=discord.ButtonStyle.primary, row=1)
    async def manage_ship(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_EditCharacterShips, interaction)

    @discord.ui.button(label="Edit Information", style=discord.ButtonStyle.primary, row=2)
    async def edit_character_information(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = CharacterInformationModal(self.active_character, self.bot.compendium)
        response: CharacterInformationModal = await self.prompt_modal(interaction, modal)

        if response.update and (activity := self.bot.compendium.get_object(Activity, "MOD_CHARACTER")):
            await create_log(self.bot, self.owner, self.guild, activity, self.player, self.active_character, "Character Modification")

        await self.refresh_content(interaction)

    @discord.ui.button(label="Level Up", style=discord.ButtonStyle.primary, row=2)
    async def level_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.player.highest_level_character.level < 3 and (self.player.needed_rps > self.player.completed_rps or self.player.needed_arenas > self.player.completed_arenas):
            await interaction.channel.send(embed=ErrorEmbed(description=f"{self.member.mention} has not completed their requirements to level up.\n"
                                                      f"Completed RPs: {min(self.player.completed_rps, self.player.needed_rps)}/{self.player.needed_rps}\n"
                                                      f"Completed Arena Phases: {min(self.player.completed_arenas, self.player.needed_arenas)}/{self.player.needed_arenas}"),
                                                      delete_after=5)
        elif (activity := self.bot.compendium.get_object(Activity, "LEVEL")):
            self.active_character.level += 1
            await create_log(self.bot, self.owner, self.guild, activity, self.player, self.active_character, "Player level up")
            await manage_player_roles(self.discord_guild, self.member, self.player, "Level up")

            await interaction.channel.send(embed=LevelUpEmbed(self.member, self.active_character))

        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(CharacterSettingsUI, interaction)

    async def _before_send(self):
        if self.active_character.level+1 > self.guild.max_level:
            self.level_character.disabled = True
        else:
            self.level_character.disabled = False
        pass

    async def get_content(self) -> Mapping:
        return {"embed": CharacterEmbed(self.member, self.active_character, self.bot.compendium), "content": ""}
    
class _EditCharacterClass(CharacterSettings):
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
            await interaction.channel.send(embed=ErrorEmbed(description=f"Character only has one class"), delete_after=5)
        else:
            self.active_character.classes.pop(self.active_character.classes.index(self.active_class))
            self.active_class.active = False
            async with self.bot.db.acquire() as conn:
                await conn.execute(upsert_class_query(self.active_class))
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
        return {"embed": CharacterEmbed(self.member, self.active_character, self.bot.compendium), "content": ""}
    
class _EditCharacterShips(CharacterSettings):

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
        owners = ", ".join([f"{char.name} ( {self.discord_guild.get_member(char.player_id).mention} )" for char in self.active_ship.owners])
        conf = await confirm(interaction, f"Are you sure you want to inactivate `{self.active_ship.get_formatted_starship(self.bot.compendium)}` for {owners}? (Reply with yes/no)", True)

        if conf is None:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Timed out waiting for a response or invalid response."), delete_after=5)
            await self.refresh_content(interaction)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Ok, cancelling"), delete_after=5)
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
        return {"embed": CharacterEmbed(self.member, self.active_character, self.bot.compendium), "content": ""}
    
class _EditStarship(CharacterSettings):
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
        return {"embed": StarshipEmbed(self.bot, self.member, self.active_ship), "content": ""}
    
class _EditStarshipOwners(CharacterSettings):
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
            await interaction.channel.send(embed=ErrorEmbed(description=f"Select someone to add"), delete_after=5)
        elif self.owner_character is None:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Select a character to add"), delete_after=5)
        elif self.owner_character.id in self.active_ship.character_id:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Character is already an owner of this ship"), delete_after=5)
        else:
            self.active_ship.character_id.append(self.owner_character.id)
            self.active_ship.owners.append(self.owner_character)
            await upsert_starship(self.bot, self.active_ship)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Player", row=3)
    async def remove_owner(self, _: discord.ui.Button, interaction: discord.Interaction):
        if len(self.active_ship.character_id) == 1:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Can't remove the last owner. Either add someone first or delete the ship"), delete_after=5)
        elif self.owner_member is None:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Select someone to remove"), delete_after=5)
        elif self.owner_character is None:
            self.owner_character = next((ch for ch in self.owner_player.characters if ch.id in self.active_ship.character_id), None)

        if self.owner_character is None:
            await interaction.channel.send(embed=ErrorEmbed(description=f"Select a character to remove"), delete_after=5)
        else:
            self.active_ship.character_id.remove(self.owner_character.id)
            self.active_ship.owners = [owner for owner in self.active_ship.owners if owner.id != self.owner_character.id]
            if self.owner_member == self.member:
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
        return {"embed": StarshipEmbed(self.bot, self.member, self.active_ship), "content": ""}

    
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
        self.add_item(InputText(label="Chain Codes", style=discord.InputTextStyle.short, required=False, placeholder="Chain Codes", max_length=7, value=str(self.new_cc)))

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
            await interaction.channel.send(embed=ErrorEmbed(description="\n".join(err_str)), delete_after=5)

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
            await interaction.channel.send(embed=ErrorEmbed(description="\n".join(err_str)), delete_after=5)

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
            await interaction.channel.send(embed=ErrorEmbed(description="\n".join(err_str)), delete_after=5)

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
            await interaction.channel.send(embed=ErrorEmbed(description="\n".join(err_str)), delete_after=5)

        await interaction.response.defer()
        self.stop()
        

# View specific helpers
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
