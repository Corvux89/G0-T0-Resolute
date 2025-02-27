import discord

from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.players import Player


class AdventuresEmbed(discord.Embed):
    def __init__(self, player: Player, phrases: list[str]):
        super().__init__(
            title=f"Adventure Information for {player.member.display_name}",
            color=discord.Color.dark_grey(),
        )

        self.set_thumbnail(url=player.member.display_avatar.url)

        dm_str = adventure_str = (
            "\n".join(
                [
                    f"{ZWSP3}{adventure.name} ({adventure.role.mention})"
                    for adventure in player.adventures
                    if player.id in adventure.dms
                ]
            )
            if len(player.adventures) > 0
            else None
        )

        if dm_str is not None:
            self.add_field(name=f"DM'ing Adventures", value=dm_str, inline=False)

        for character in player.characters:
            adventure_str = (
                "\n".join(
                    [
                        f"{ZWSP3}{adventure.name} ({adventure.role.mention})"
                        for adventure in player.adventures
                        if character.id in adventure.characters
                    ]
                )
                if len(player.adventures) > 0
                else "None"
            )
            class_str = ",".join(
                [f" {c.get_formatted_class()}" for c in character.classes]
            )
            self.add_field(
                name=f"{character.name} - Level {character.level} [{class_str}]",
                value=adventure_str or "None",
                inline=False,
            )

        if phrases:
            for p in phrases:
                out_str = p.split("|")
                self.add_field(
                    name=out_str[0],
                    value=f"{out_str[1] if len(out_str) > 1 else ''}",
                    inline=False,
                )


class AdventureSettingsEmbed(discord.Embed):
    def __init__(
        self,
        ctx: discord.ApplicationContext | discord.Interaction,
        adventure: Adventure,
    ):
        super().__init__(title=f"{adventure.name}", color=discord.Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.description = (
            f"**Adventure Role**: {adventure.role.mention}\n"
            f"**CC Earned to date**: {adventure.cc}"
        )

        if len(adventure.factions) > 0:
            self.description += f"\n**Factions**:\n" + "\n".join(
                [f"{ZWSP3}{f.value}" for f in adventure.factions]
            )

        self.add_field(
            name=f"DM{'s' if len(adventure.dms) > 1 else ''}",
            value="\n".join(
                [
                    f"{ZWSP3}- {ctx.guild.get_member(dm).mention}"
                    for dm in adventure.dms
                    if ctx.guild.get_member(dm)
                ]
            ),
            inline=False,
        )

        if adventure._player_characters:
            self.add_field(
                name="Players",
                value="\n".join(
                    [
                        f"{ZWSP3}- {character.name} ({ctx.guild.get_member(character.player_id).mention})"
                        for character in adventure._player_characters
                        if ctx.guild.get_member(character.player_id)
                    ]
                ),
                inline=False,
            )


class AdventureRewardEmbed(discord.Embed):
    def __init__(
        self,
        ctx: discord.ApplicationContext | discord.Interaction,
        adventure: Adventure,
        cc: int,
    ):
        super().__init__(
            title=f"Adventure Rewards",
            description=f"**Adventure**: {adventure.name}\n"
            f"**CC Earned**: {cc:,}\n"
            f"**CC Earned to date**: {adventure.cc:,}\n",
            color=discord.Color.random(),
        )
        self.set_thumbnail(url=THUMBNAIL)
        self.set_footer(
            text=f"Logged by {ctx.user.name}", icon_url=ctx.user.display_avatar.url
        )

        self.add_field(
            name=f"DM{'s' if len(adventure.dms) > 1 else ''}",
            value="\n".join(
                [
                    f"{ZWSP3}- {ctx.guild.get_member(dm).mention}"
                    for dm in adventure.dms
                    if ctx.guild.get_member(dm)
                ]
            ),
            inline=False,
        )

        if adventure._player_characters:
            self.add_field(
                name="Players",
                value="\n".join(
                    [
                        f"{ZWSP3}- {character.name} ({ctx.guild.get_member(character.player_id).mention})"
                        for character in adventure._player_characters
                        if ctx.guild.get_member(character.player_id)
                    ]
                ),
                inline=False,
            )
