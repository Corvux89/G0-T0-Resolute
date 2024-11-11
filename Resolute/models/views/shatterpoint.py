from typing import Mapping

import discord
from discord.ui import InputText, Modal

from Resolute.bot import G0T0Bot
from Resolute.helpers import (confirm, create_log, delete_players,
                              delete_shatterpoint, get_all_guild_characters,
                              get_char_name_from_message, get_guild,
                              get_player, get_shatterpoint,
                              upsert_shatterpoint, upsert_shatterpoint_player)
from Resolute.helpers.shatterpoint import delete_renown, upsert_shatterpoint_renown
from Resolute.models.categories.categories import CodeConversion, Faction
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.shatterpoint import (ShatterpointEmbed,
                                                 ShatterpointLogEmbed)
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.players import Player
from Resolute.models.objects.shatterpoint import (Shatterpoint,
                                                  ShatterpointPlayer, ShatterpointRenown)
from Resolute.models.views.base import InteractiveView


class ShatterpointSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "shatterpoint")
    bot: G0T0Bot
    shatterpoint: Shatterpoint

    async def commit(self):
        self.shatterpoint = await upsert_shatterpoint(self.bot, self.shatterpoint)

    async def get_content(self) -> Mapping:
        return {"embed": ShatterpointEmbed(self.bot, self.shatterpoint)}

class ShatterpointSettingsUI(ShatterpointSettings):
    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, shatterpoint: Shatterpoint = None):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.shatterpoint = shatterpoint or Shatterpoint(guild_id=owner.guild.id)

        return inst

    @discord.ui.button(label="Shatterpoint Settings", style=discord.ButtonStyle.primary, row=1)
    async def shatterpoint_settings(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ShatterpointSettingsModal(self.shatterpoint)
        await self.prompt_modal(interaction, modal)

        for player in self.shatterpoint.players:
            if player.active and player.update:
                player.cc = self.shatterpoint.base_cc
                await upsert_shatterpoint_player(self.bot, player)

        await self.refresh_content(interaction) 

    @discord.ui.button(label="Manage", style=discord.ButtonStyle.primary, row=1)
    async def shatterpoint_manage(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)

    @discord.ui.button(label="Commit", style=discord.ButtonStyle.green, row=1)
    async def shatterpoint_commit(self, _: discord.ui.Button, interaction: discord.Interaction):
        conf = await confirm(interaction, "Are you sure you want to log this global? (Reply with yes/no)", True, self.bot)

        if conf is None:
            await interaction.channel.send(embed=ErrorEmbed("Timed out waiting for a response or invalid response"), delete_after=5)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed("Ok, cancelling"), delete_after=5)
        else:
            for p in self.shatterpoint.players:
                player = await get_player(self.bot, p.player_id, interaction.guild.id)
                await create_log(self.bot, self.owner, "GLOBAL", player, 
                                 notes=self.shatterpoint.name, 
                                 cc=p.cc)
                
                # Character Rewards
                for c in p.characters:
                    character = next((ch for ch in player.characters if ch.id == c), None)
                    conversion: CodeConversion = self.bot.compendium.get_object(CodeConversion, character.level)
                    credits = p.cc * conversion.value

                    await create_log(self.bot, self.owner, "GLOBAL", player,
                                     character=character,
                                     notes=self.shatterpoint.name,
                                     credits=credits)
                    
                    for renown in self.shatterpoint.renown:
                        await create_log(self.bot, self.owner, "RENOWN", player,
                                         character=character,
                                         notes=self.shatterpoint.name,
                                         faction=renown.faction,
                                         renown=renown.renown)

            await delete_shatterpoint(self.bot, interaction.guild.id)
            await delete_players(self.bot, interaction.guild.id)
            await delete_renown(self.bot, interaction.guild.id)
            await interaction.channel.send(embed=ShatterpointLogEmbed(self.shatterpoint))
            await self.on_timeout()

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red, row=2)
    async def shatterpoint_reset(self, _: discord.ui.Button, interaction: discord.Interaction):
        conf = await confirm(interaction, "Are you sure you want to reset this global without logging? (Reply yes/no)", True, self.bot)

        if conf is None:
            await interaction.channel.send(embed=ErrorEmbed("Timed out waiting for a response or invalid response"), delete_after=5)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed("Ok, cancelling"), delete_after=5)
        else:
            self.shatterpoint = Shatterpoint(guild_id=interaction.guild.id)
            await delete_players(self.bot, interaction.guild.id)
        
        await self.refresh_content(interaction)


    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=2)
    async def exit(self, *_):
        await self.on_timeout()


class _ShatterpointManage(ShatterpointSettings):
    channel: discord.TextChannel = None

    @discord.ui.channel_select(placeholder="Channel to scrape", channel_types=[discord.ChannelType(0)])
    async def channel_select(self, chan: discord.ui.Select, interaction: discord.Interaction):
        self.channel = chan.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Scrape Channel", style=discord.ButtonStyle.primary, row=2)
    async def channel_scrape(self, _: discord.ui.Select, interaction: discord.Interaction):


        if not self.channel:
            await interaction.channel.send(embed=ErrorEmbed("Select a channel to scrape first"), delete_after=5)
        else:
            messages = await self.channel.history(oldest_first=True, limit=600).flatten()
            characters = await get_all_guild_characters(self.bot, interaction.guild.id)

            for message in messages:
                player: ShatterpointPlayer = None
                if not message.author.bot:
                    player = next((p for p in self.shatterpoint.players if p.player_id == message.author.id), 
                                  ShatterpointPlayer(guild_id=self.shatterpoint.guild_id,
                                                     player_id=message.author.id,
                                                     cc=self.shatterpoint.base_cc))
                elif (char_name := get_char_name_from_message(message)) and (character := next((c for c in characters if c.name.lower() == char_name.lower()), None)):
                    player = next((p for p in self.shatterpoint.players if p.player_id == character.player_id), 
                                  ShatterpointPlayer(guild_id=self.shatterpoint.guild_id,
                                                     player_id=character.player_id,
                                                     cc=self.shatterpoint.base_cc))
                    if character.id not in player.characters:
                        player.characters.append(character.id)
                        
                if player:
                    player.num_messages +=1 

                    if message.channel.id not in player.channels:
                        player.channels.append(message.channel.id)
                    
                    player = await upsert_shatterpoint_player(self.bot, player)

                    self.shatterpoint = await get_shatterpoint(self.bot, self.shatterpoint.guild_id)
            
            if message.channel.id not in self.shatterpoint.channels:
                self.shatterpoint.channels.append(message.channel.id)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Players", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_players(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointPlayerManage, interaction)

    @discord.ui.button(label="Renown", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_renown(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointRenownManage, interaction)

    # @discord.ui.button(label="Mass Adjust")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ShatterpointSettingsUI, interaction)

class _ShatterpointPlayerManage(ShatterpointSettings):
    player: ShatterpointPlayer = None
    bot_player: Player = None
    character: PlayerCharacter = None

    async def get_content(self) -> Mapping:
        return {"embed": ShatterpointEmbed(self.bot, self.shatterpoint, True, self.player)}
    
    async def _before_send(self):
        self.player_remove.disabled = False if self.player and self.player.id and self.player.active else True
        self.remove_item(self.character_select)

        if self.player:
            char_list = [discord.SelectOption(label=c.name, value=f"{c.id}", default=True if self.character and c.id == self.character.id else False) for c in self.bot_player.characters]

            if len(char_list) > 0:
                self.character_select.options = char_list
                self.add_item(self.character_select)


        self.character_add.disabled = False if self.character else True
        self.character_remove.disabled = False if self.character else True

                

    @discord.ui.user_select(placeholder="Select a player", row=1)
    async def player_select(self, m: discord.ui.Select, interaction: discord.Interaction):
        member = m.values[0]
        player = next((x for x in self.shatterpoint.players if x.player_id == member.id), ShatterpointPlayer(guild_id=self.shatterpoint.guild_id, 
                                                                                                             player_id=member.id, 
                                                                                                             cc=self.shatterpoint.base_cc))
        self.player = player
        self.bot_player = await get_player(self.bot, self.player.player_id, self.player.guild_id)
        self.character = None
        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Select a character", row=2)
    async def character_select(self, c: discord.ui.Select, interaction: discord.Interaction):
        char = int(c.values[0])

        self.character = next((c for c in self.bot_player.characters if c.id == char), None)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Player Settings", style=discord.ButtonStyle.primary, row=3)
    async def player_settings(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = ShatterpointPlayerSettingsModal(self.shatterpoint, self.player, interaction.guild)
        await self.prompt_modal(interaction, modal)

        if self.player.cc == self.shatterpoint.base_cc:
            self.player.update = True
        else:
            self.player.update = False

        self.player.active = True
        
        self.player = await upsert_shatterpoint_player(self.bot, self.player)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Player", style=discord.ButtonStyle.red, row=3)
    async def player_remove(self, _: discord.ui.Button, interaction: discord.Interaction):
        if not hasattr(self.player, "id") or not self.player.active:
            return await interaction.channel.send(embed=ErrorEmbed("Player already isn't in the global"), delete_after=5)
        else:
            self.player.active = False

            self.player = await upsert_shatterpoint_player(self.bot, self.player)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Character", style=discord.ButtonStyle.primary, row=4)
    async def character_add(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.character.id not in self.player.characters:
            self.player.characters.append(self.character.id)
            self.player = await upsert_shatterpoint_player(self.bot, self.player)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Character", style=discord.ButtonStyle.red, row=4)
    async def character_remove(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.character.id in self.player.characters:
            self.player.characters.remove(self.character.id)
            self.player = await upsert_shatterpoint_player(self.bot, self.player)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)

    
class _ShatterpointRenownManage(ShatterpointSettings):
    faction: Faction = None

    async def _before_send(self):
        faction_list = []

        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(discord.SelectOption(label=f"{faction.value}", value=f"{faction.id}", default=True if self.faction and self.faction.id == faction.id else False))

        self.select_faction.options = faction_list

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def select_faction(self, fac: discord.ui.Select, interaction: discord.Interaction):
        self.faction = self.bot.compendium.get_object(Faction, int(fac.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add/Remove Renown", style=discord.ButtonStyle.primary, row=2)
    async def modify_renown(self, _: discord.ui.Button, interaction: discord.Interaction):
        renown = next((r for r in self.shatterpoint.renown if r.faction.id == self.faction.id), 
                      ShatterpointRenown(guild_id=self.shatterpoint.guild_id,
                                         faction=self.faction))
        
        modal = ShatterpointRenownModal(renown)

        response = await self.prompt_modal(interaction, modal)

        await upsert_shatterpoint_renown(self.bot, renown)
        
        await self.refresh_content(interaction)
        
    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)

class ShatterpointSettingsModal(Modal):
    shatterpoint: Shatterpoint

    def __init__(self, shatterpoint: Shatterpoint):
        super().__init__(title=f"{shatterpoint.name} Settings")

        self.shatterpoint = shatterpoint

        self.add_item(InputText(label="Name", placeholder="Name", value=self.shatterpoint.name))
        self.add_item(InputText(label="Base CC Reward", placeholder="Base CC Reward", value=f"{self.shatterpoint.base_cc}"))

    async def callback(self, interaction: discord.Interaction):
        self.shatterpoint.name = self.children[0].value

        try:
            self.shatterpoint.base_cc = int(self.children[1].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed("CC Amount must be a number"), delete_after=5)
        
        await interaction.response.defer()
        self.stop()

class ShatterpointPlayerSettingsModal(Modal):
    shatterpoint: Shatterpoint
    spPlayer: ShatterpointPlayer

    def __init__(self, shatterpoint: Shatterpoint, spPlayer: ShatterpointPlayer, guild: discord.Guild):
        super().__init__(title=f"{guild.get_member(spPlayer.player_id).display_name} Settings")
        self.shatterpoint = shatterpoint
        self.spPlayer = spPlayer

        self.add_item(InputText(label="CC Reward", value=f"{self.spPlayer.cc}"))

    async def callback(self, interaction: discord.Interaction):
        try:
            self.spPlayer.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed("CC Amount must be a number"), delete_after=5)
    
        await interaction.response.defer()
        self.stop()

class ShatterpointRenownModal(Modal):
    renown: ShatterpointRenown

    def __init__(self, renown):
        super().__init__(title=f"Modify Renown")
        self.renown = renown

        self.add_item(InputText(label="Renown Amount ", placeholder="Renown Amount ", max_length=4, value=self.renown.renown))
    
    async def callback(self, interaction: discord.Interaction):
        try:
            amount = max(0, int(self.children[0].value))
            self.renown.renown = amount
        except:
            await interaction.channel.send(embed=ErrorEmbed(f"Renown must be a number!"))

        await interaction.response.defer()
        self.stop()