import discord

from Resolute.constants import ZWSP3
from Resolute.models.objects.characters import PlayerCharacter, PlayerCharacterClass
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.players import Player


class NewCharacterSetupEmbed(discord.Embed):
    def __init__(
        self,
        player: Player,
        new_character: PlayerCharacter,
        newClass: PlayerCharacterClass,
        starting_credits: int = 0,
        cc_credit: int = 0,
    ):
        super().__init__(title=f"Information for {player.member.display_name}")
        self.set_thumbnail(url=player.member.display_avatar.url)
        self.color = player.member.color

        self.description = (
            f"**Name**: {new_character.name if new_character.name else ''}\n"
            f"**Level**: {new_character.level}{f' (*Too high for server. Max server level is `{player.guild.max_level}`*)' if new_character.level > player.guild.max_level else ''}\n"
            f"**Species**: {new_character.species.value if hasattr(new_character.species, 'value') else ''}\n"
            f"**Class**: {newClass.get_formatted_class() if hasattr(newClass, 'primary_class') else ''}\n"
            f"**Starting Credits**: {starting_credits:,}\n"
        )

        if cc_credit != 0:
            self.description += f"**CC Adjustment**: {cc_credit}{f''' (*This would put the player at {player.cc + cc_credit:,} CC*)''' if player.cc + cc_credit < 0 else ''}\n"


class NewcharacterEmbed(discord.Embed):
    def __init__(self, log: DBLog):
        super().__init__(title=f"Character Created - {log.character.name}")

        self.description = (
            f"**Player**: {log.player.member.mention}\n"
            f"**Level**: {log.character.level}\n"
            f"**Species**: {log.character.species.value}\n"
            f"**Class**: {log.character.classes[0].get_formatted_class()}\n"
            f"**Starting Credits**: {log.credits:,}\n"
            f"{f'**CC Adjustment**: {log.cc:,}' if log.cc != 0 and log.cc != None else ''}"
        )

        self.color = discord.Color.random()
        self.set_thumbnail(url=log.player.member.display_avatar.url)
        self.set_footer(
            text=f"Created by: {log.author.member.name} - Log #: {log.id}",
            icon_url=log.author.member.display_avatar.url,
        )


class CharacterEmbed(discord.Embed):
    def __init__(self, player: Player, character: PlayerCharacter):
        super().__init__(title=f"Character Info - [{character.level}] {character.name}")
        self.color = player.member.color
        self.set_thumbnail(
            url=(
                player.member.display_avatar.url
                if not character.avatar_url
                else character.avatar_url
            )
        )

        class_str = f"\n{ZWSP3*2}".join(
            [f"{c.get_formatted_class()}" for c in character.classes]
        )
        class_str = (
            f"\n{ZWSP3*2}{class_str}" if len(character.classes) > 1 else class_str
        )

        self.description = (
            f"**Player**: {player.member.mention}\n"
            f"**Faction**: {character.faction.value if character.faction else '*None*'}\n"
            f"**Total Renown**: {character.total_renown}\n"
            f"**Species**: {character.species.value}\n"
            f"**Credits**: {character.credits:,}\n"
            f"**Class{'es' if len(character.classes) > 1 else ''}**: {class_str}\n"
        )

        if character.renown:
            self.add_field(
                name="Renown Breakdown",
                value="\n".join(
                    [
                        f"{ZWSP3}**{r.faction.value}**: {r.renown}"
                        for r in character.renown
                    ]
                ),
                inline=True,
            )


class LevelUpEmbed(discord.Embed):
    def __init__(self, player: Player, character: PlayerCharacter):
        super().__init__(title="Level up successful!", color=discord.Color.random())
        self.set_thumbnail(url=player.member.display_avatar.url)
        self.description = (
            f"{character.name} ({player.member.mention}) is now level {character.level}"
        )


class CharacterSettingsEmbed(discord.Embed):
    def __init__(self, player: Player, character: PlayerCharacter):
        super().__init__(title=f"Settings for {player.member.display_name}")
        self.set_thumbnail(
            url=(
                player.member.display_avatar.url
                if not character.avatar_url
                else character.avatar_url
            )
        )
        self.color = player.member.color

        self.description = (
            f"**Character**: {character.name}{f' (*{character.nickname}*)' if character.nickname else ''}\n"
            f"**Faction**: {character.faction.value if character.faction else '*None*'}\n"
            f"**Global Character**: {'True' if character.primary_character else 'False'}"
        )

        if player.guild.calendar and character.dob:
            self.description += (
                f"\n**Birthday**: {character.formatted_dob(player.guild)}\n"
                f"**Age**: {character.age(player.guild)}"
            )

        self.add_field(
            name="Active RP Channels",
            value="\n".join(
                [
                    player.member.guild.get_channel(c).mention
                    for c in character.channels
                    if player.member.guild.get_channel(c)
                ]
            ),
        )
