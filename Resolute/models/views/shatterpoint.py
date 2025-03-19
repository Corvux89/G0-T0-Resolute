import asyncio
from typing import Mapping

import discord

from Resolute.bot import G0T0Bot
from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.helpers import confirm
from Resolute.models.categories.categories import CodeConversion, Faction
from Resolute.models.embeds import ErrorEmbed, PaginatedEmbed, PlayerEmbed
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.enum import AdjustOperator
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player
from Resolute.models.objects.shatterpoint import (
    Shatterpoint,
    ShatterpointPlayer,
    ShatterpointRenown,
)
from Resolute.models.views.base import InteractiveView


class ShatterpointSettings(InteractiveView):
    """
    ShatterpointSettings is a view that manages the settings for a Shatterpoint instance.
    Attributes:
        __menu_copy_attrs__ (tuple): A tuple containing attribute names to be copied.
        bot (G0T0Bot): The bot instance.
        shatterpoint (Shatterpoint): The Shatterpoint instance.
    Methods:
        commit(): Commits the current settings to the Shatterpoint instance if it is not busy.
        get_content() -> Mapping: Returns the content to be displayed in the view.
    """

    __menu_copy_attrs__ = ("bot", "shatterpoint")
    bot: G0T0Bot
    shatterpoint: Shatterpoint

    async def commit(self):
        if not self.shatterpoint.busy_member:
            await self.shatterpoint.upsert()
            self.shatterpoint = await Shatterpoint.get_shatterpoint(
                self.bot, self.shatterpoint.guild_id
            )

    async def get_content(self) -> Mapping:
        if hasattr(self, "player") and self.player:
            self.player = next(
                (
                    p
                    for p in self.shatterpoint.players
                    if p.player_id == self.player.player_id
                ),
                None,
            )

        active_players: list[ShatterpointPlayer] = list(
            filter(lambda p: p.active, self.shatterpoint.players)
        )
        override_players: list[ShatterpointPlayer] = list(
            filter(lambda p: not p.update, self.shatterpoint.players)
        )

        embed = PlayerEmbed(
            self.owner, title=f"Summary for shatterpoint: {self.shatterpoint.name}"
        )
        embed.set_thumbnail(url=THUMBNAIL)

        paginated_embed = PaginatedEmbed(embed)

        paginated_embed.description = (
            f"**Base Chain Codes**: {self.shatterpoint.base_cc:,}\n"
            f"**Total Participants**: {len(active_players):,}"
        )

        if hasattr(self, "player") and self.player:
            char_str = "\n".join(
                [f"{ZWSP3}{c.name}" for c in self.player.player_characters]
            )

            paginated_embed.add_field(
                name=f"Information for {self.player.member.display_name}",
                value=(
                    f"**CC**: {self.player.cc:,}\n"
                    f"**# Scraped Posts**: {self.player.num_messages}\n"
                    "**Characters**:\n"
                    f"{char_str}"
                ),
            )

        if self.shatterpoint.renown:
            paginated_embed.add_field(
                name="Renown",
                value="\n".join(
                    [
                        f"{ZWSP3}**{r.faction.value}**: {r.renown}"
                        for r in self.shatterpoint.renown
                        if r.renown > 0
                    ]
                ),
            )

        paginated_embed.add_field(
            name="Scraped Channels",
            value="\n".join(
                [f"{ZWSP3}{c.mention}" for c in self.shatterpoint.channels]
            ),
        )

        if override_players:
            paginated_embed.add_field(
                name="Manual Overrides (CC, Renown)",
                value="\n".join(
                    [
                        f"{ZWSP3}{player.member.mention if player.member else f'Unkown Member {player.player_id}'} ({player.cc:,}, {player.renown_override if player.renown_override else 'NA'})"
                        for player in override_players
                    ]
                ),
            )

        if hasattr(self, "player") or hasattr(self, "operator"):
            paginated_embed.add_field(
                name="All active players (Cc, # posts, # characters)",
                value="\n".join(
                    [
                        f"{ZWSP3}{player.member.mention if player.member else f'Unkown Member {player.player_id}'} ({player.cc:,}, {player.num_messages:,}, {len(player.characters)})"
                        for player in active_players
                    ]
                ),
            )

        return {"embeds": paginated_embed.embeds}


class ShatterpointSettingsUI(ShatterpointSettings):
    """
    A user interface class for managing Shatterpoint settings in a Discord bot.
    Methods
    -------
    new(cls, bot: G0T0Bot, owner: Member, shatterpoint: Shatterpoint = None)
        Creates a new instance of ShatterpointSettingsUI.
    shatterpoint_settings(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Shatterpoint Settings" button click event to modify Shatterpoint settings.
    shatterpoint_manage(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Manage" button click event to defer to the Shatterpoint management interface.
    shatterpoint_commit(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Commit" button click event to log the global Shatterpoint settings.
    shatterpoint_reset(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the "Reset" button click event to reset the Shatterpoint settings without logging.
    exit(self, *_)
        Handles the "Exit" button click event to exit the Shatterpoint settings interface.
    """

    @classmethod
    def new(
        cls, bot: G0T0Bot, owner: discord.Member, shatterpoint: Shatterpoint = None
    ):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.shatterpoint = shatterpoint or Shatterpoint(
            bot.db, guild_id=owner.guild.id
        )

        return inst

    @discord.ui.button(
        label="Shatterpoint Settings", style=discord.ButtonStyle.primary, row=1
    )
    async def shatterpoint_settings(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)

        modal = ShatterpointSettingsModal(self.shatterpoint)
        await self.prompt_modal(interaction, modal)

        for player in self.shatterpoint.players:
            if player.active and player.update:
                player.cc = self.shatterpoint.base_cc
                await player.upsert()

        await self.refresh_content(interaction)

    @discord.ui.button(label="Manage", style=discord.ButtonStyle.primary, row=1)
    async def shatterpoint_manage(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_ShatterpointManage, interaction)

    @discord.ui.button(label="Commit", style=discord.ButtonStyle.green, row=1)
    async def shatterpoint_commit(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)

        conf = await confirm(
            interaction,
            "Are you sure you want to log this global? (Reply with yes/no)",
            True,
            self.bot,
        )

        if conf is None:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Timed out waiting for a response or invalid response"
                ),
                delete_after=5,
            )
        elif not conf:
            await interaction.channel.send(
                embed=ErrorEmbed("Ok, cancelling"), delete_after=5
            )
        else:
            active_players: list[ShatterpointPlayer] = list(
                filter(lambda p: p.active, self.shatterpoint.players)
            )
            for p in active_players:
                player = await Player.get_player(self.bot, p.player_id, p.guild_id)

                await DBLog.create(
                    self.bot,
                    interaction,
                    player,
                    self.owner,
                    "GLOBAL",
                    notes=self.shatterpoint.name,
                    cc=p.cc,
                    silent=True,
                )

                # Character Rewards
                for c in p.characters:
                    character = next(
                        (ch for ch in player.characters if ch.id == c), None
                    )
                    conversion: CodeConversion = self.bot.compendium.get_object(
                        CodeConversion, character.level
                    )
                    credits = p.cc * conversion.value
                    await DBLog.create(
                        self.bot,
                        interaction,
                        player,
                        self.owner,
                        "GLOBAL",
                        character=character,
                        notes=self.shatterpoint.name,
                        credits=credits,
                        silent=True,
                    )

                    for renown in self.shatterpoint.renown:
                        await DBLog.create(
                            self.bot,
                            interaction,
                            player,
                            self.owner,
                            "RENOWN",
                            character=character,
                            notes=self.shatterpoint.name,
                            faction=renown.faction,
                            renown=(
                                p.renown_override
                                if p.renown_override
                                else renown.renown
                            ),
                            silent=True,
                        )

            await self.shatterpoint.delete()
            embed = discord.Embed(
                title=f"Shatterpoint: {self.shatterpoint.name} - has been logged",
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="# Players", value=f"{len(active_players):,}", inline=False
            )

            embed.add_field(
                name="# Characters",
                value=f"{sum(len(player.characters) for player in active_players)}",
                inline=False,
            )

            await interaction.channel.send(embed=embed)
            await self.on_timeout()

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red, row=2)
    async def shatterpoint_reset(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)

        conf = await confirm(
            interaction,
            "Are you sure you want to reset this global without logging? (Reply yes/no)",
            True,
            self.bot,
        )

        if conf is None:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Timed out waiting for a response or invalid response"
                ),
                delete_after=5,
            )
        elif not conf:
            await interaction.channel.send(
                embed=ErrorEmbed("Ok, cancelling"), delete_after=5
            )
        else:
            await self.shatterpoint.delete()
            self.shatterpoint = Shatterpoint(self.bot.db, guild_id=interaction.guild.id)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=2)
    async def exit(self, *_):
        await self.on_timeout()


class _ShatterpointManage(ShatterpointSettings):
    channel: discord.TextChannel = None

    @discord.ui.channel_select(
        placeholder="Channel to scrape",
        channel_types=[
            discord.ChannelType(0),
            discord.ChannelType(11),
            discord.ChannelType(15),
        ],
    )
    async def channel_select(
        self, chan: discord.ui.Select, interaction: discord.Interaction
    ):
        self.channel = chan.values[0]
        await self.refresh_content(interaction)

    @discord.ui.button(label="Scrape Channel", style=discord.ButtonStyle.primary, row=2)
    async def channel_scrape(
        self, _: discord.ui.Select, interaction: discord.Interaction
    ):
        if not self.channel:
            return await interaction.channel.send(
                embed=ErrorEmbed("Select a channel to scrape first"), delete_after=5
            )
        elif self.shatterpoint.busy_member:
            return await interaction.channel.send(
                embed=ErrorEmbed(
                    "Already scraping a channel. Please wait for it to finish first"
                ),
                delete_after=5,
            )
        else:
            guild: PlayerGuild = await PlayerGuild.get_player_guild(
                self.bot, interaction.guild.id
            )
            self.shatterpoint.busy_member = interaction.user
            await self.shatterpoint.upsert()
            asyncio.create_task(
                self.shatterpoint.scrape_channel(
                    self.bot, self.channel, guild, interaction.user
                )
            )
            await interaction.channel.send(
                "Scraping done in background process. Please rerun the command when finished. You will not be able to modify Shatterpoint settings at this time.",
                delete_after=5,
            )
        await self.on_timeout()

    @discord.ui.button(label="Players", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_players(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_ShatterpointPlayerManage, interaction)

    @discord.ui.button(label="Renown", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_renown(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        await self.defer_to(_ShatterpointRenownManage, interaction)

    @discord.ui.button(label="Mass Adjust", style=discord.ButtonStyle.primary, row=2)
    async def shatterpoint_adjust(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)
        await self.defer_to(_ShatterpointMassAdjust, interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(ShatterpointSettingsUI, interaction)


class _ShatterpointPlayerManage(ShatterpointSettings):
    player: ShatterpointPlayer = None
    bot_player: Player = None
    character: PlayerCharacter = None

    async def _before_send(self):
        self.player_remove.disabled = (
            False
            if self.player and self.player.player_id and self.player.active
            else True
        )

        self.remove_item(self.character_select)

        if self.player:
            char_list = [
                discord.SelectOption(
                    label=c.name,
                    value=f"{c.id}",
                    default=(
                        True if self.character and c.id == self.character.id else False
                    ),
                )
                for c in self.bot_player.characters
            ]

            if char_list:
                self.character_select.options = char_list
                self.add_item(self.character_select)

        self.character_add.disabled = False if self.character else True
        self.character_remove.disabled = False if self.character else True
        self.player_settings.disabled = False if self.player else True

    @discord.ui.user_select(placeholder="Select a player", row=1)
    async def player_select(
        self, m: discord.ui.Select, interaction: discord.Interaction
    ):
        member = m.values[0]
        player = next(
            (x for x in self.shatterpoint.players if x.player_id == member.id),
            ShatterpointPlayer(
                self.bot.db,
                guild_id=self.shatterpoint.guild_id,
                player_id=member.id,
                cc=self.shatterpoint.base_cc,
            ),
        )
        self.player = player
        self.bot_player = await Player.get_player(
            self.bot, self.player.player_id, self.player.guild_id
        )
        self.character = None
        await self.refresh_content(interaction)

    @discord.ui.select(
        placeholder="Select a character", row=2, custom_id="character_select"
    )
    async def character_select(
        self, c: discord.ui.Select, interaction: discord.Interaction
    ):
        char = int(c.values[0])

        self.character = next(
            (c for c in self.bot_player.characters if c.id == char), None
        )
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Player Settings", style=discord.ButtonStyle.primary, row=3
    )
    async def player_settings(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)

        modal = ShatterpointPlayerSettingsModal(
            self.shatterpoint, self.player, interaction.guild
        )
        await self.prompt_modal(interaction, modal)

        if (
            self.player.cc == self.shatterpoint.base_cc
            and not self.player.renown_override
        ):
            self.player.update = True
        else:
            self.player.update = False

        self.player.active = True

        await self.player.upsert()

        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Player", style=discord.ButtonStyle.red, row=3)
    async def player_remove(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if not self.player.active:
            return await interaction.channel.send(
                embed=ErrorEmbed("Player already isn't in the global"), delete_after=5
            )
        elif self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)
        else:
            self.player.active = False
            await self.player.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add Character", style=discord.ButtonStyle.primary, row=4)
    async def character_add(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)

        if self.character.id not in self.player.characters:
            self.player.characters.append(self.character.id)
            await self.player.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove Character", style=discord.ButtonStyle.red, row=4)
    async def character_remove(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.shatterpoint.busy_member:
            await interaction.channel.send(
                embed=ErrorEmbed(
                    "Shatterpoint modification in progress. Please wait for it to finish first"
                ),
                delete_after=5,
            )
            return await self.refresh_content(interaction)
        if self.character.id in self.player.characters:
            self.player.characters.remove(self.character.id)
            await self.player.upsert()
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=4)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)


class _ShatterpointMassAdjust(ShatterpointSettings):
    operator: AdjustOperator = None

    @discord.ui.select(placeholder="Select an operator", row=1)
    async def select_operator(
        self, op: discord.ui.Select, interaction: discord.Interaction
    ):
        self.operator = AdjustOperator[op.values[0]]
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Adjustment Settings", style=discord.ButtonStyle.primary, row=2
    )
    async def adjust_settings(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if not self.operator:
            return await interaction.channel.send(
                embed=ErrorEmbed("Please select an operator first"), delete_after=5
            )
        modal = ShatterpointMassAdjustModal(self.shatterpoint, self.operator)
        await self.prompt_modal(interaction, modal)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)

    async def _before_send(self):
        op_list = [
            discord.SelectOption(
                label=f"{o.value}",
                value=f"{o.name}",
                default=True if self.operator == o else False,
            )
            for o in AdjustOperator
        ]
        self.select_operator.options = op_list


class _ShatterpointRenownManage(ShatterpointSettings):
    faction: Faction = None

    async def _before_send(self):
        faction_list = []

        for faction in self.bot.compendium.faction[0].values():
            faction_list.append(
                discord.SelectOption(
                    label=f"{faction.value}",
                    value=f"{faction.id}",
                    default=(
                        True
                        if self.faction and self.faction.id == faction.id
                        else False
                    ),
                )
            )

        self.select_faction.options = faction_list

    @discord.ui.select(placeholder="Select a faction", row=1)
    async def select_faction(
        self, fac: discord.ui.Select, interaction: discord.Interaction
    ):
        self.faction = self.bot.compendium.get_object(Faction, int(fac.values[0]))
        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Add/Remove Renown", style=discord.ButtonStyle.primary, row=2
    )
    async def modify_renown(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        renown = next(
            (r for r in self.shatterpoint.renown if r.faction.id == self.faction.id),
            ShatterpointRenown(
                self.bot.db, guild_id=self.shatterpoint.guild_id, faction=self.faction
            ),
        )

        modal = ShatterpointRenownModal(renown)

        await self.prompt_modal(interaction, modal)
        await renown.upsert()

        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_ShatterpointManage, interaction)


class ShatterpointSettingsModal(discord.ui.Modal):
    shatterpoint: Shatterpoint

    def __init__(self, shatterpoint: Shatterpoint):
        super().__init__(title=f"{shatterpoint.name} Settings")

        self.shatterpoint = shatterpoint

        self.add_item(
            discord.ui.InputText(
                label="Name", placeholder="Name", value=self.shatterpoint.name
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Base CC Reward",
                placeholder="Base CC Reward",
                value=f"{self.shatterpoint.base_cc}",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        self.shatterpoint.name = self.children[0].value

        try:
            self.shatterpoint.base_cc = int(self.children[1].value)
        except:
            await interaction.channel.send(
                embed=ErrorEmbed("CC Amount must be a number"), delete_after=5
            )

        await interaction.response.defer()
        self.stop()


class ShatterpointPlayerSettingsModal(discord.ui.Modal):
    shatterpoint: Shatterpoint
    spPlayer: ShatterpointPlayer

    def __init__(
        self,
        shatterpoint: Shatterpoint,
        spPlayer: ShatterpointPlayer,
        guild: discord.Guild,
    ):
        super().__init__(
            title=f"{guild.get_member(spPlayer.player_id).display_name} Settings"
        )
        self.shatterpoint = shatterpoint
        self.spPlayer = spPlayer

        self.add_item(
            discord.ui.InputText(label="CC Reward", value=f"{self.spPlayer.cc}")
        )
        self.add_item(
            discord.ui.InputText(
                label="Renown Reward",
                required=False,
                value=f"{self.spPlayer.renown_override}",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            self.spPlayer.cc = int(self.children[0].value)
        except:
            await interaction.channel.send(
                embed=ErrorEmbed("CC Amount must be a number"), delete_after=5
            )

        self.spPlayer.renown_override = (
            self.children[1].value if self.children[1].value != "" else None
        )

        await interaction.response.defer()
        self.stop()


class ShatterpointRenownModal(discord.ui.Modal):
    renown: ShatterpointRenown

    def __init__(self, renown):
        super().__init__(title=f"Modify Renown")
        self.renown = renown

        self.add_item(
            discord.ui.InputText(
                label="Renown Amount ",
                placeholder="Renown Amount ",
                max_length=4,
                value=self.renown.renown,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            amount = max(0, int(self.children[0].value))
            self.renown.renown = amount
        except:
            await interaction.channel.send(
                embed=ErrorEmbed(f"Renown must be a number!")
            )

        await interaction.response.defer()
        self.stop()


class ShatterpointMassAdjustModal(discord.ui.Modal):
    shatterpoint: Shatterpoint
    operator: AdjustOperator

    def __init__(self, shatterpoint: Shatterpoint, operator: AdjustOperator):
        super().__init__(title="Mass Adjust")
        self.shatterpoint = shatterpoint
        self.operator = operator

        self.add_item(
            discord.ui.InputText(
                label="Post Threshold", placeholder="Post Threshold", max_length=4
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="CC Override",
                required=False,
                placeholder="CC Override",
                max_length=4,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Renown Override",
                required=False,
                placeholder="Renown Override",
                max_length=4,
            )
        )

    async def callback(self, interaction):
        try:
            threshold = max(0, int(self.children[0].value))
            cc = int(self.children[1].value) if self.children[1].value else None
            renown = int(self.children[2].value) if self.children[2].value else None
        except:
            await interaction.channel.send(embed=ErrorEmbed("Values must be a number!"))

        if threshold and (cc or renown):
            for player in self.shatterpoint.players:
                if not player.active:
                    continue

                if (
                    self.operator == AdjustOperator.less
                    and player.num_messages <= threshold
                ):
                    player.cc = cc if cc else player.cc
                    player.renown_override = (
                        renown if renown else player.renown_override
                    )
                    player.update = False
                elif (
                    self.operator == AdjustOperator.greater
                    and player.num_messages >= threshold
                ):
                    player.cc = cc if cc else player.cc
                    player.renown_override = (
                        renown if renown else player.renown_override
                    )
                    player.update = False

                if (
                    len(self.shatterpoint.renown) == 1
                    and player.renown_override == self.shatterpoint.renown[0].renown
                ):
                    player.renown_override = None

                if (
                    player.cc == self.shatterpoint.base_cc
                    and not player.renown_override
                ):
                    player.update = True

                await player.upsert()

        await interaction.response.defer()
        self.stop()
