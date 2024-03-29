import calendar
from typing import List

import discord
from d20 import RollResult
from discord import Embed, Member, ApplicationContext, Color

from Resolute.constants import THUMBNAIL
from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, DBLog, LevelCaps, Arena, Adventure, \
    PlayerGuild, CharacterStarship


class NewCharacterEmbed(Embed):
    def __init__(self, character: PlayerCharacter, player: Member, char_class: PlayerCharacterClass,
                 log: DBLog, ctx: ApplicationContext):
        super().__init__(title=f"Character Created - {character.name}",
                         description=f"**Player:** {player.mention}\n"
                                     f"**Species:** {character.species.value}\n"
                                     f"**Class:** {char_class.get_formatted_class()}\n"
                                     f"**Starting Credits:** {character.credits:,}\n"
                                     f"**Starting Chain Code:** {character.cc:,}\n"
                                     f"**Starting Level:** {character.level}\n",
                         color=discord.Color.random())
        self.set_thumbnail(url=player.display_avatar.url)
        self.set_footer(text=f"Created by: {ctx.author.name} - Log #: {log.id}",
                        icon_url=ctx.author.display_avatar.url)


class CharacterGetEmbed(Embed):
    def __init__(self, character: PlayerCharacter, char_class: List[PlayerCharacterClass],
                 cap: LevelCaps, ctx: ApplicationContext, g: PlayerGuild, char_ships: List[CharacterStarship] | None,
                 handicap_active: bool):
        super().__init__(title=f"Character Info - {character.name}")

        self.description = f"**Class:**" if len(char_class) == 1 else f"**Classes:**"
        self.description += f"\n".join([f" {c.get_formatted_class()}" for c in char_class])
        self.description += f"\n**Species: ** {character.species.value}\n" \
                            f"**Level:** {character.level}\n" \
                            f"**Credits:** {character.credits:,}\n" \
                            f"**Chain Codes:** {character.cc:,} \n" \

        if handicap_active:
            self.description += f"\n**Booster enabled. All CC Rewards doubled!**"

        self.color = character.get_member(ctx).color
        self.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        self.add_field(name="Weekly Limits: ",
                       value=f"\u200b \u200b \u200b Diversion Chain Codes: {character.div_cc:,}/{cap.max_cc:,}",
                       inline=False)

        if character.level < 3:
            pretty_completed_rps = character.completed_rps \
                if character.completed_rps <= character.needed_rps else character.needed_rps
            pretty_completed_arenas = character.completed_arenas \
                if character.completed_arenas <= character.needed_arenas else character.needed_arenas
            self.add_field(name="First Steps Quests:",
                           value=f"\u200b \u200b \u200b Level {character.level} RPs: "
                                 f"{pretty_completed_rps}/{character.needed_rps}\n"
                                 f"\u200b \u200b \u200b Level {character.level} Arena Phases: "
                                 f"{pretty_completed_arenas}/{character.needed_arenas}", inline=False)

        if char_ships and len(char_ships) > 0:
            self.add_field(name="Starships: ",
                           value=f"\n".join([f"\u200b \u200b \u200b {s.get_formatted_starship(ctx.bot.compendium)}" for s in char_ships]),
                           inline=False)


class HxLogEmbed(Embed):
    def __init__(self, log_ary: [DBLog], character: PlayerCharacter, ctx: ApplicationContext):
        super().__init__(title=f"Character Logs - {character.name}",
                         colour=discord.Colour.random())

        self.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        if len(log_ary) < 1:
            self.description = f"No logs for this week"

        for log in log_ary:
            log_time = log.created_ts
            unix_timestamp = calendar.timegm(log_time.utctimetuple())
            author = log.get_author(ctx).mention if log.get_author(ctx) is not None else "`Not found`"

            value = f"**Author:** {author}\n" \
                    f"**Activity:** {log.activity.value}\n" \
                    f"**Chain Codes:** {log.cc:,}\n" \
                    f"**Credits:** {log.credits:,}\n" \
                    f"**Invalidated?:** {log.invalid}\n"

            if log.notes is not None:
                value += f"**Notes:** {log.notes}"

            self.add_field(name=f"Log # {log.id} - <t:{unix_timestamp}>", value=value, inline=False)


class DBLogEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, log_entry: DBLog, character: PlayerCharacter,
                 show_amounts: bool = True):
        super().__init__(title=f"{log_entry.activity.value} Logged - {character.name}",
                         color=Color.random())

        player = character.get_member(ctx)
        description = f"**Player:** {player.mention}\n"
        if show_amounts:
            if log_entry.cc is not None and log_entry.cc != 0:
                description += f"**Chain Codes:** {log_entry.cc:,}\n"
            if log_entry.credits is not None and log_entry.credits != 0:
                description += f"**Credits:** {log_entry.credits:,}\n"
        if hasattr(log_entry, "notes") and log_entry.notes is not None:
            description += f"**Notes:** {log_entry.notes}\n"

        self.description = description
        self.set_thumbnail(url=player.display_avatar.url)
        self.set_footer(text=f"Logged by {ctx.author.name} - ID: {log_entry.id}",
                        icon_url=ctx.author.display_avatar.url)


class ArenaPhaseEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, arena: Arena, result: str):
        rewards = f"{arena.get_host(ctx).mention}: 'HOST'\n"
        bonus = (arena.completed_phases > arena.tier.max_phases / 2) and result == 'WIN'
        arena_role = arena.get_role(ctx)
        players = list(set(filter(lambda p: p.id != arena.host_id, arena_role.members)))

        for player in players:
            rewards += f"{player.mention}: '{result}'"
            rewards += ', `BONUS`\n' if bonus else '\n'

        super().__init__(
            title=f"Phase {arena.completed_phases} Complete!",
            description=f"Complete phases: **{arena.completed_phases} / {arena.tier.max_phases}**",
            color=discord.Color.random()
        )

        self.set_thumbnail(url=THUMBNAIL)

        self.add_field(name="The following rewards have been applied:", value=rewards, inline=False)

class StarshipArenaPhaseEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, arena: Arena, result: str):
        rewards = f"{arena.get_host(ctx).mention}: 'HOST'\n"
        # bonus = (arena.completed_phases > arena.tier.max_phases / 2) and result == 'WIN'
        arena_role = arena.get_role(ctx)
        players = list(set(filter(lambda p: p.id != arena.host_id, arena_role.members)))

        for player in players:
            rewards += f"{player.mention}: '{result}'\n"
            # rewards += ', `BONUS`\n' if bonus else '\n'

        super().__init__(
            title=f"Phase {arena.completed_phases} Complete!",
            description=f"Complete phases: **{arena.completed_phases} / 1**",
            color=discord.Color.random()
        )

        self.set_thumbnail(url=THUMBNAIL)

        self.add_field(name="The following rewards have been applied:", value=rewards, inline=False)


class ArenaStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | discord.Interaction, arena: Arena):
        super().__init__(title=f"Arena Status",
                         description=f"**Tier** {arena.tier.id}\n"
                                     f"**Completed Phases:** {arena.completed_phases} / {arena.tier.max_phases}",
                         color=Color.random())

        self.set_thumbnail(url=THUMBNAIL)

        if arena.completed_phases == 0:
            self.description += "\n\nUse the button below to join!"
        elif arena.completed_phases >= arena.tier.max_phases / 2:
            self.description += "\nBonus active!"

        self.add_field(name="**Host:**", value=f"\u200b - {arena.get_host(ctx).mention}",
                       inline=False)

        players = list(set(filter(lambda p: p.id != arena.host_id,
                                  arena.get_role(ctx).members)))

        if len(players) > 0:
            self.add_field(name="**Players:**",
                           value="\n".join([f"\u200b -{p.mention}" for p in players]),
                           inline=False)

class StarshipArenaStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | discord.Interaction, arena: Arena):
        super().__init__(title=f"Starship Arena Status",
                         description=f"**Completed Phases:** {arena.completed_phases} / 1",
                         color=Color.random())

        self.set_thumbnail(url=THUMBNAIL)

        if arena.completed_phases == 0:
            self.description += "\n\nUse the button below to join!"

        self.add_field(name="**Host:**", value=f"\u200b - {arena.get_host(ctx).mention}",
                       inline=False)

        players = list(set(filter(lambda p: p.id != arena.host_id,
                                  arena.get_role(ctx).members)))

        if len(players) > 0:
            self.add_field(name="**Players:**",
                           value="\n".join([f"\u200b -{p.mention}" for p in players]),
                           inline=False)


class AdventureRewardEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, adventure: Adventure, cc: int):
        super().__init__(
            title="Adventure Rewards",
            description=f"**Adventure:** {adventure.name}\n"
                        f"**CC Earned:** {cc:,}\n"
                        f"**CC Earned to date:** {adventure.cc:,}\n",
            color=Color.random()
        )

        dms = list(set(filter(lambda p: p.id in adventure.dms, adventure.get_adventure_role(ctx).members)))
        players = list(set(filter(lambda p: p.id not in adventure.dms, adventure.get_adventure_role(ctx).members)))

        if len(dms) > 0:
            self.add_field(
                name="DM(s)",
                value="\n".join([f"\u200b - {p.mention}" for p in dms]),
                inline=False
            )
        if len(players) > 0:
            self.add_field(
                name="Players",
                value="\n".join([f"\u200b - {p.mention}" for p in players]),
                inline=False
            )

        self.set_thumbnail(url=THUMBNAIL)
        self.set_footer(text=f"Logged by {ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url)


class AdventureStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, adventure: Adventure):
        super().__init__(
            title=f"Adventure Status - {adventure.name}",
            description=f"**Adventure Role:** {adventure.get_adventure_role(ctx).mention}\n"
                        f"**CC Earned to date:** {adventure.cc}\n",
            color=Color.random()
        )

        dms = list(set(filter(lambda p: p.id in adventure.dms, adventure.get_adventure_role(ctx).members)))
        players = list(set(filter(lambda p: p.id not in adventure.dms, adventure.get_adventure_role(ctx).members)))

        if len(dms) > 0:
            self.add_field(
                name="DM(s)",
                value="\n".join([f"\u200b - {p.mention}" for p in dms]),
                inline=False
            )
        if len(players) > 0:
            self.add_field(
                name="Players",
                value="\n".join([f"\u200b - {p.mention}" for p in players]),
                inline=False
            )

        self.set_thumbnail(url=THUMBNAIL)


class AdventureCloseEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, adventure: Adventure):
        super().__init__(
            title="Adventure Complete!",
            description=f"**Adventure:** {adventure.name}\n"
                        f"**Total CC:** {adventure.cc:,}\n"
        )
        self.add_field(
            name="DM(s)",
            value="\n".join([f"\u200b - {p.mention}" for p in list(set(filter(lambda p: p.id in adventure.dms,
                                                                              adventure.get_adventure_role(
                                                                                  ctx).members)))]),
            inline=False
        )

        self.add_field(
            name="Players",
            value="\n".join([f"\u200b - {p.mention}" for p in list(set(filter(lambda p: p.id not in adventure.dms,
                                                                              adventure.get_adventure_role(
                                                                                  ctx).members)))]),
            inline=False
        )

        self.set_thumbnail(url=THUMBNAIL)
        self.set_footer(text=f"Logged by {ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url)


class GuildEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, g: PlayerGuild):
        super().__init__(title=f'Server Settings for {ctx.guild.name}',
                         colour=Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.add_field(name="**Settings**",
                       value=f"**Max Level:** {g.max_level}\n"
                             f"**Max Rerolls:** {g.max_reroll}\n"
                             f"**Handicap Amount:** {g.handicap_cc}",
                       inline=False)

        if g.reset_hour is not None:
            self.add_field(name="**Reset Schedule**",
                           value=f"**Approx Next Run:** <t:{g.get_next_reset()}>\n"
                                 f"**Last Reset: ** <t:{g.get_last_reset()}>")


class GuildStatus(Embed):
    def __init__(self, ctx: ApplicationContext, g: PlayerGuild, total: int, inactive: List[PlayerCharacter] | None,
                 display_inact: bool):
        super().__init__(title=f"Server Info - {ctx.guild.name}",
                         color=Color.random(),
                         description=f"**Max Level:** {g.max_level}\n"
                                     f"**\# Weeks:** {g.weeks}\n"
                                     f"**Handicap CC Amount:** {g.handicap_cc}")

        self.set_thumbnail(url=THUMBNAIL)

        in_count = 0 if inactive is None else len(inactive)

        self.description += f"\n**Total Characters:** {total}\n" \
                            f"**Inactive Characters:** {in_count}\n" \
                            f"*Inactive defined by no logs in past 30 days*"

        if g.reset_hour is not None:
            self.add_field(name="**Reset Schedule**",
                           value=f"**Approx Next Run:** <t:{g.get_next_reset()}>\n"
                                 f"**Last Reset: ** <t:{g.get_last_reset()}>", inline=False)

        if display_inact and inactive is not None:
            for i in range(0, len(inactive), 10):
                self.add_field(name="Inactive Characters",
                               value="\n".join([f"\u200b - {p.get_member_mention(ctx)}" for p in inactive[i:i+10]]),
                               inline=False)
            # out_list = "\n".join([f"\u200b - {p.get_member_mention(ctx)}" for p in inactive])
            # self.add_field(name="Inactive Characters",
            #                value="\n".join([f"\u200b - {p.get_member_mention(ctx)}" for p in inactive]), inline=False)


class AdventuresEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, character: PlayerCharacter, class_ary: List[PlayerCharacterClass],
                 adventures: List, phrases: list[str] | None = None):
        super().__init__(title=f"Adventure Info - {character.name}")

        self.color = Color.dark_grey()
        self.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        self.description = f'**Class:**' if len(class_ary) == 1 else f'**Classes:**'
        self.description+= f"\n".join([f" {c.get_formatted_class()}" for c in class_ary])
        self.description+=f'\n**Level:** {character.level}'



        if len(adventures['player']) > 0:
            value = "\n".join([f'\u200b - {a.get_adventure_role(ctx).mention}' for a in adventures['player']])
        else:
            value = "None"

        self.add_field(name=f"Player ({len(adventures['player'])})", value=value, inline=False)

        if len(adventures['dm'])>0:
            self.add_field(name=f"DM ({len(adventures['dm'])})",
                           value="\n".join([f'\u200b - {a.get_adventure_role(ctx).mention}' for a in adventures['dm']]),
                           inline=False)

        if len(phrases) >0:
            for p in phrases:
                outString = p.split("|")
                if len(outString)>1:
                    self.add_field(name=outString[0], value=outString[1], inline=False)
                else:
                    self.add_field(name=outString[0], value="", inline=False)



