import discord

from discord.ui import Modal, InputText
from typing import Mapping

from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import confirm
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player
from Resolute.helpers.shatterpoint import delete_players, delete_shatterpoint, upsert_shatterpoint, upsert_shatterpoint_player
from Resolute.models.categories.categories import Activity
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.shatterpoint import ShatterpointEmbed, ShatterpointLogEmbed
from Resolute.models.objects.shatterpoint import ShatterpointPlayer, Shatterpoint
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
            await interaction.channel.send(embed=ErrorEmbed(description="Timed out waiting for a response or invalid response"), delete_after=5)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed(description="Ok, cancelling"), delete_after=5)
        else:
            activity = self.bot.compendium.get_object(Activity, "GLOBAL")
            g = await get_guild(self.bot, interaction.guild.id)
            for p in self.shatterpoint.players:
                player = await get_player(self.bot, p.player_id, interaction.guild.id)
                await create_log(self.bot, self.owner, g, activity, player, 
                                 notes=self.shatterpoint.name, 
                                 cc=p.cc)
            
            await delete_shatterpoint(self.bot, interaction.guild.id)
            await delete_players(self.bot, interaction.guild.id)
            await interaction.channel.send(embed=ShatterpointLogEmbed(self.shatterpoint))
            await self.on_timeout()

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red, row=2)
    async def shatterpoint_reset(self, _: discord.ui.Button, interaction: discord.Interaction):
        conf = await confirm(interaction, "Are you sure you want to reset this global without logging? (Reply yes/no)", True, self.bot)

        if conf is None:
            await interaction.channel.send(embed=ErrorEmbed(description="Timed out waiting for a response or invalid response"), delete_after=5)
        elif not conf:
            await interaction.channel.send(embed=ErrorEmbed(description="Ok, cancelling"), delete_after=5)
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
            await interaction.channel.send(embed=ErrorEmbed(description="Select a channel to scrape first"), delete_after=5)
        else:
            messages = await self.channel.history(oldest_first=True, limit=600).flatten()
            for message in messages:
                player: ShatterpointPlayer = None
                if not message.author.bot:
                    if player := next((p for p in self.shatterpoint.players if p.player_id == message.author.id), ShatterpointPlayer(guild_id=self.shatterpoint.guild_id,
                                                                                                                                     player_id=message.author.id,
                                                                                                                                     cc=self.shatterpoint.base_cc)):
                        player.num_messages += 1
                        if message.channel.id not in player.channels:
                            player.channels.append(message.channel.id)

                    player = await upsert_shatterpoint_player(self.bot, player)
                    if player.player_id in [p.player_id for p in self.shatterpoint.players]:
                        self.shatterpoint.players.remove(next((p for p in self.shatterpoint.players if p.player_id == player.player_id), None))
                    
                    self.shatterpoint.players.append(player)
                    

            
            if message.channel.id not in self.shatterpoint.channels:
                self.shatterpoint.channels.append(message.channel.id)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Players", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_players(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointPlayerManage, interaction)

    # @discord.ui.button(label="Mass Adjust")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ShatterpointSettingsUI, interaction)

class _ShatterpointPlayerManage(ShatterpointSettings):
    player: ShatterpointPlayer

    @discord.ui.user_select(placeholder="Select a player")
    async def player_select(self, m: discord.ui.Select, interaction: discord.Interaction):
        member = m.values[0]
        player = next((x for x in self.shatterpoint.players if x.player_id == member.id), ShatterpointPlayer(guild_id=self.shatterpoint.guild_id, 
                                                                                                             player_id=member.id, 
                                                                                                             cc=self.shatterpoint.base_cc))
        self.player = player
        await self.refresh_content(interaction)

    @discord.ui.button(label="Player Settings", style=discord.ButtonStyle.primary, row=2)
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

    @discord.ui.button(label="Remove Player", style=discord.ButtonStyle.red, row=2)
    async def player_remove(self, _: discord.ui.Button, interaction: discord.Interaction):
        if not hasattr(self.player, "id") or not self.player.active:
            return await interaction.channel.send(embed=ErrorEmbed(description="Player already isn't in the global"), delete_after=5)
        else:
            self.player.active = False

            self.player = await upsert_shatterpoint_player(self.bot, self.player)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ShatterpointSettingsUI, interaction)

    async def get_content(self) -> Mapping:
        return {"embed": ShatterpointEmbed(self.bot, self.shatterpoint, True)}

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
            await interaction.channel.send(embed=ErrorEmbed(description="CC Amount must be a number"), delete_after=5)
        
        await interaction.response.defer()
        self.stop()

class ShatterpointPlayerSettingsModal(Modal):
    shatterpoint: Shatterpoint
    spPlayer: ShatterpointPlayer

    def __init__(self, shatterpoint: Shatterpoint, spPlayer: ShatterpointPlayer, guild: discord.Guild):
        super().__init__(title=f"{guild.get_member(spPlayer.player_id).mention} Settings")
        self.shatterpoint = shatterpoint
        self.spPlayer = spPlayer

        self.add_item(InputText(label="CC Reward", value=f"{self.spPlayer.cc}"))

    async def callback(self, interaction: discord.Interaction):
        try:
            self.spPlayer.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(embed=ErrorEmbed(description="CC Amount must be a number"), delete_after=5)
    
        await interaction.response.defer()
        self.stop()