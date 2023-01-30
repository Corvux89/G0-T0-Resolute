import calendar
from typing import List

import discord
from d20 import RollResult
from discord import Embed, Member, ApplicationContext, Color

from ProphetBot.constants import THUMBNAIL
from ProphetBot.models.db_objects import PlayerCharacter, PlayerCharacterClass, DBLog, LevelCaps, Arena, Adventure, \
    PlayerGuild, Shop
from ProphetBot.models.db_objects.item_objects import ItemBlacksmith, ItemWondrous, ItemConsumable, ItemScroll


class NewCharacterEmbed(Embed):
    def __init__(self, character: PlayerCharacter, player: Member, char_class: PlayerCharacterClass,
                 log: DBLog, ctx: ApplicationContext):
        super().__init__(title=f"Character Created - {character.name}",
                         description=f"**Player:** {player.mention}\n"
                                     f"**Race:** {character.get_formatted_race()}\n"
                                     f"**Class:** {char_class.get_formatted_class()}\n"
                                     f"**Starting Gold:** {character.gold}\n"
                                     f"**Starting Level:** {character.get_level()}\n",
                         color=discord.Color.random())
        self.set_thumbnail(url=player.display_avatar.url)
        self.set_footer(text=f"Created by: {ctx.author} - Log #: {log.id}",
                        icon_url=ctx.author.display_avatar.url)


class CharacterGetEmbed(Embed):
    def __init__(self, character: PlayerCharacter, char_class: List[PlayerCharacterClass],
                 cap: LevelCaps, ctx: ApplicationContext):
        super().__init__(title=f"Character Info - {character.name}")

        self.description = f"**Class:**" if len(char_class) == 1 else f"**Classes:**"
        self.description += f"\n".join([f" {c.get_formatted_class()}" for c in char_class])
        self.description += f"\n**Race: ** {character.get_formatted_race()}\n" \
                            f"**Faction:** {character.faction.value}\n" \
                            f"**Level:** {character.get_level()}\n" \
                            f"**Experience:** {character.xp}\n" \
                            f"**Wealth:** {character.gold} gp\n"

        faction_role = character.faction.get_faction_role(ctx)
        self.color = faction_role.color if faction_role else Color.dark_grey()
        self.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        self.add_field(name="Weekly Limits: ",
                       value=f"\u200b \u200b \u200b Diversion GP: {character.div_gold}/{cap.max_gold}\n"
                             f"\u200b \u200b \u200b Diversion XP: {character.div_xp}/{cap.max_xp}",
                       inline=False)

        if character.get_level() < 3:
            pretty_completed_rps = character.completed_rps \
                if character.completed_rps <= character.needed_rps else character.needed_rps
            pretty_completed_arenas = character.completed_arenas \
                if character.completed_arenas <= character.needed_arenas else character.needed_arenas
            self.add_field(name="First Steps Quests:",
                           value=f"\u200b \u200b \u200b Level {character.get_level()} RPs: "
                                 f"{pretty_completed_rps}/{character.needed_rps}\n"
                                 f"\u200b \u200b \u200b Level {character.get_level()} Arenas: "
                                 f"{pretty_completed_arenas}/{character.needed_arenas}")


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
                    f"**Gold:** {log.gold}\n" \
                    f"**XP:** {log.xp}\n" \
                    f"**Server XP:** {log.server_xp}\n" \
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
            if log_entry.gold is not None and log_entry.gold != 0:
                description += f"**Gold:** {log_entry.gold}\n"
            if log_entry.xp is not None and log_entry.xp != 0:
                description += f"**Experience:** {log_entry.xp}\n"
            if log_entry.server_xp is not None and log_entry.server_xp > 0:
                description += f"**Server Experience Contributed:** {log_entry.server_xp}\n"
        if hasattr(log_entry, "notes") and log_entry.notes is not None:
            description += f"**Notes:** {log_entry.notes}\n"

        self.description = description
        self.set_thumbnail(url=player.display_avatar.url)
        self.set_footer(text=f"Logged by {ctx.author} - ID: {log_entry.id}",
                        icon_url=ctx.author.display_avatar.url)  # TODO: Something wrong here


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


class AdventureEPEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, adventure: Adventure, ep: int):
        super().__init__(
            title="Adventure Rewards",
            description=f"**Adventure:** {adventure.name}\n"
                        f"**Adventure Tier:** {adventure.tier.id}\n"
                        f"**EP Earned:** {ep}\n"
                        f"**EP Earned to date:** {adventure.ep}\n"
                        f"*Note: Rewards are 1/2 of your diversion caps for each EP*\n",
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
        self.set_footer(text=f"Logged by {ctx.author.name}#{ctx.author.discriminator}",
                        icon_url=ctx.author.display_avatar.url)


class AdventureStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, adventure: Adventure):
        super().__init__(
            title=f"Adventure Status - {adventure.name}",
            description=f"**Adventure Role:** {adventure.get_adventure_role(ctx).mention}\n"
                        f"**Adventure Tier:** {adventure.tier.id}\n"
                        f"**EP Earned to date:** {adventure.ep}\n",
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
                        f"**Tier:** {adventure.tier.id}\n"
                        f"**Total EP:** {adventure.ep}\n"
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
        self.set_footer(text=f"Logged by {ctx.author.name}#{ctx.author.discriminator}",
                        icon_url=ctx.author.display_avatar.url)


class GuildEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, g: PlayerGuild):
        super().__init__(title=f'Server Settings for {ctx.guild.name}',
                         colour=Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.add_field(name="**Settings**",
                       value=f"**Max Level:** {g.max_level}\n"
                             f"**Max Rerolls:** {g.max_reroll}\n"
                             f"**XP Adjust:** {g.xp_adjust}",
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
                                     f"**Server XP:** {g.server_xp}\n"
                                     f"**Week XP:** {g.week_xp}\n"
                                     f"**Total XP:** {g.total_xp()}\n"
                                     f"**# Weeks:** {g.weeks}\n")

        self.set_thumbnail(url=THUMBNAIL)

        in_count = 0 if inactive is None else len(inactive)

        self.description +=f"\n **XP Goal: ** {g.get_xp_goal(total, inactive)} (*{g.get_xp_percent(total, inactive)}%*)\n" \
                           f"**XP Adjust:** {g.xp_adjust}\n"

        self.description += f"\n**Total Characters:** {total}\n" \
                            f"**Inactive Characters:** {in_count}\n" \
                            f"*Inactive defined by no logs in past 30 days*"

        if g.reset_hour is not None:
            self.add_field(name="**Reset Schedule**",
                           value=f"**Approx Next Run:** <t:{g.get_next_reset()}>\n"
                                 f"**Last Reset: ** <t:{g.get_last_reset()}>", inline=False)

        if display_inact and inactive is not None:
            self.add_field(name="Inactive Characters",
                           value="\n".join([f"\u200b - {p.get_member_mention(ctx)}" for p in inactive]), inline=False)

class BlacksmithItemEmbed(Embed):
    def __init__(self, item: ItemBlacksmith):
        super().__init__(title=f"{item.name}",
                         color=Color.random(),
                         description=f"**Type:** {item.sub_type.value}\n"
                                     f"**Rarity:** {item.rarity.value}\n"
                                     f"**Cost:** {item.display_cost()} gp\n"
                                     f"**Shop:** Blacksmith\n")

        if item.attunement:
            self.description += f"**Attunement Required:** Yes\n"
        else:
            self.description += f"**Attunement Required:** No\n"

        if item.seeking_only:
            self.description += f"**Seeking:** Yes\n"
        else:
            self.description += f"**Seeking:** No\n"

        if item.notes is not None:
            self.add_field(name="Notes", value=item.notes, inline=False)

        self.set_footer(text=f"Source: {item.source} | id: {item.id}")


class MagicItemEmbed(Embed):
    def __init__(self, item: ItemWondrous):
        super().__init__(title=f"{item.name}",
                         color=Color.random(),
                         description=f"**Rarity:** {item.rarity.value}\n"
                                     f"**Cost:** {item.cost} gp\n"
                                     f"**Shop:** Magic Items\n")

        if item.attunement:
            self.description += f"**Attunement Required:** Yes\n"
        else:
            self.description += f"**Attunement Required:** No\n"

        if item.seeking_only:
            self.description += f"**Seeking:** Yes\n"
        else:
            self.description += f"**Seeking:** No\n"

        if item.notes is not None:
            self.add_field(name="Notes", value=item.notes, inline=False)

        self.set_footer(text=f"Source: {item.source} | id: {item.id}")


class ConsumableItemEmbed(Embed):
    def __init__(self, item: ItemConsumable):
        super().__init__(title=f"{item.name}",
                         color=Color.random(),
                         description=f"**Type:** {item.sub_type.value}\n"
                                     f"**Rarity:** {item.rarity.value}\n"
                                     f"**Cost:** {item.cost} gp\n"
                                     f"**Shop:** Consumables\n")

        if item.attunement:
            self.description += f"**Attunement Required:** Yes\n"
        else:
            self.description += f"**Attunement Required:** No\n"

        if item.seeking_only:
            self.description += f"**Seeking:** Yes\n"
        else:
            self.description += f"**Seeking:** No\n"

        if item.notes is not None:
            self.add_field(name="Notes", value=item.notes, inline=False)

        self.set_footer(text=f"Source: {item.source} | id: {item.id}")


class ScrollItemEmbed(Embed):
    def __init__(self, item: ItemScroll):
        super().__init__(title=f"{item.display_name()}",
                         color=Color.random(),
                         description=f"**Type:** Scroll\n"
                                     f"**Rarity:** {item.rarity.value}\n"
                                     f"**Cost:** {item.cost} gp\n"
                                     f"**School:** {item.school.value}\n"
                                     f"**Shop:** Consumables\n")

        if len(item.classes) > 0:
            self.description += f"**Classes:** "
            self.description += ", ".join([f"{c.value}" for c in item.classes])

        if item.notes is not None:
            self.add_field(name="Notes", value=item.notes, inline=False)

        self.set_footer(text=f"Source: {item.source} | id: {item.id}")


class NewShopEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, shop: Shop):
        super().__init__(title=f"New Shop - {shop.name}",
                         color=Color.random(),
                         description=f"**Owner:** {shop.get_owner(ctx).mention}\n"
                                     f"**Shop Type:** {shop.type.value}")

        self.set_thumbnail(url=shop.get_owner(ctx).display_avatar.url)
        self.set_footer(text=f"Created by {ctx.author}",
                        icon_url=ctx.author.display_avatar.url)


class ShopEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, shop: Shop):
        super().__init__(title=f"{shop.name}",
                         color=Color.random(),
                         description=f"**Owner:** {shop.get_owner(ctx).mention}\n"
                                     f"**Shop Type:** {shop.type.value}\n"
                                     f"**Shelf Upgrades:** {shop.shelf}\n"
                                     f"**Network Upgrades:** {shop.network}\n"
                                     f"**Mastery Upgrades:** {shop.mastery}\n"
                                     f"**Max Cost:** {shop.max_cost}\n\n"
                                     f"**Seek Roll:** `{shop.seek_roll}`\n"
                                     f"**Seeks:** {shop.seeks_remaining} / {shop.network + 1}")

        self.set_thumbnail(url=shop.get_owner(ctx).display_avatar.url)

class ShopSeekEmbed(Embed):
    def __init__(self, shop: Shop, roll: RollResult, dc: int | None, phrase: str | None):
        super().__init__(title=f"{shop.name}",
                         color=Color.random())

        if phrase is not None:
            self.title += f" - {phrase}"
        else:
            self.title += f" - Seeking"

        if dc is not None:
            result = "**Success!**" if roll.total >= dc else "*Failure*"
            self.add_field(name=f"DC {dc}",
                           value=f"{str(roll)}\n\n"
                                 f"{result}")
        else:
            self.description=f"{str(roll)}"

        self.set_footer(text=f"{shop.seeks_remaining} / {shop.network + 1} seeks remaining")


class AdventuresEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, character: PlayerCharacter, class_ary: List[PlayerCharacterClass],
                 adventures: List, phrase: str | None = None):
        super().__init__(title=f"Adventure Info - {character.name}")

        faction_role = character.faction.get_faction_role(ctx)
        self.color = faction_role.color if faction_role else Color.dark_grey()
        self.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        self.description = f'**Class:**' if len(class_ary) == 1 else f'**Classes:**'
        self.description+= f"\n".join([f" {c.get_formatted_class()}" for c in class_ary])
        self.description+=f'\n**Level:** {character.get_level()}'



        if len(adventures['player']) > 0:
            value = "\n".join([f'\u200b - {a.get_adventure_role(ctx).mention}' for a in adventures['player']])
        else:
            value = "None"

        self.add_field(name=f"Player ({len(adventures['player'])})", value=value, inline=False)

        if len(adventures['dm'])>0:
            self.add_field(name=f"DM ({len(adventures['dm'])})",
                           value="\n".join([f'\u200b - {a.get_adventure_role(ctx).mention}' for a in adventures['dm']]),
                           inline=False)

        if phrase is not None:
            outString = phrase.split("|")
            if len(outString)>1:
                self.add_field(name=outString[0], value=outString[1], inline=False)
            else:
                self.add_field(name=outString[0], value="", inline=False)



