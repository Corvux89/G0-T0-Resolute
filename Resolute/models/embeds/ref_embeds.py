from typing import Dict, List

import discord
from discord import Embed, Color, ApplicationContext, Guild

from ProphetBot.constants import THUMBNAIL
from ProphetBot.models.db_objects import GlobalEvent, GlobalPlayer


class RpDashboardEmbed(Embed):

    def __init__(self, channel_statuses: Dict[str, List[str]], category_name: str):
        super(RpDashboardEmbed, self).__init__(
            color=Color.dark_grey(),
            title=f"Channel Statuses - {category_name}",
            timestamp=discord.utils.utcnow()
        )
        if len(channel_statuses["Magewright"]) > 0:
            self.add_field(
                name="<:pencil:989284061786808380> -- Awaiting Magewright",
                value="\n".join(channel_statuses["Magewright"]),
                inline=False
            )
        self.add_field(
            name="<:white_check_mark:983576747381518396> -- Available",
            value="\n".join(channel_statuses["Available"]) or "\u200B",
            inline=False
        )
        self.add_field(
            name="<:x:983576786447245312> -- Unavailable",
            value="\n".join(channel_statuses["In Use"]) or "\u200B",
            inline=False
        )
        self.set_footer(text="Last Updated")


class ShopDashboardEmbed(Embed):
    def __init__(self, g: discord.Guild, shop_dict: Dict):
        super(ShopDashboardEmbed, self).__init__(
            color=Color.dark_grey(),
            title=f"Open Establishments",
            description="<channel> | <owner> (seeks remaining)/(total seeks)",
            timestamp=discord.utils.utcnow()
        )

        for key in shop_dict:
            if len(shop_dict[key]) > 0:
                value=""
                for shop in shop_dict[key]:
                    channel = "Channel Not Found" if g.get_channel(shop.channel_id) is None else g.get_channel(shop.channel_id).mention
                    owner = f"{shop.owner_id} Not Found" if g.get_member(shop.owner_id) is None else g.get_member(shop.owner_id).mention

                    value +=f"\u200b {channel} | {owner} (**{shop.seeks_remaining}** / {shop.network + 1})\n"

                self.add_field(
                    name=f"**{key} Shops**",
                    value=value,
                    inline=False
                )
            else:
                self.add_field(
                    name=f"**{key} Shops**",
                    value="None",
                    inline=False
                )



class GlobalEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, g_event: GlobalEvent, players: List[GlobalPlayer],
                 gblist: bool = False):
        super().__init__(title=f"Global - Log Preview",
                         colour=Color.random())

        names = g_event.get_channel_names(ctx.bot)

        active_players = []
        override_players = []
        modified_players = dict()
        host_players = []

        self.set_thumbnail(
            url=THUMBNAIL
        )

        if g_event.combat:
            for p in players:
                if p.active:
                    active_players.append(p)
                    if not p.update:
                        override_players.append(p)
                    if p.host:
                        host_players.append(p)

            self.add_field(name=f"**Information for combat global {g_event.name}**",
                           value=f"\n *Base gold:* {g_event.base_gold} \n *Base xp:* {g_event.base_xp} \n *# "
                                 f"Players:* {len(active_players)}",
                           inline=False)
        else:
            for p in players:
                if p.active:
                    active_players.append(p)
                    for mod in ctx.bot.compendium.c_global_modifier[0].values():
                        if mod.id != g_event.base_mod.id and (p.host is None or p.host.value != "Hosting Only"):
                            if mod.id == p.modifier.id:
                                if mod.value in modified_players:
                                    modified_players[mod.value].append(p)
                                    break
                                else:
                                    modified_players[mod.value] = [p]
                                    break

                    if not p.update:
                        override_players.append(p)
                    if p.host:
                        host_players.append(p)

            self.add_field(name=f"**Information for {g_event.name}**",
                           value=f"\n *Base gold:* {g_event.base_gold} \n *Base xp:* {g_event.base_xp} \n *Base "
                                 f"mod:* {g_event.base_mod.value} \n *# Players:* {len(active_players)}",
                           inline=False)

        if names:
            self.add_field(name="**Scraped Channels**",
                           value="\n".join([f"\u200b # {c}" for c in names]),
                           inline=False)
        else:
            self.add_field(name="**Scraped Channels**",
                           value="None",
                           inline=False)

        for m in modified_players.keys():
            self.add_field(name=f"**{m} Effort Overrides**",
                           value="\n".join([f"\u200b {p.get_name(ctx)}" for p in modified_players[m]]),
                           inline=False)

        if override_players:
            self.add_field(name="**Manual Overrides (gold, xp)**",
                           value="\n".join([f"\u200b {p.get_name(ctx)} ({p.gold}, {p.xp})" for p in override_players]),
                           inline=False)
        if host_players:
            self.add_field(name="**Hosts**",
                           value="\n".join([f"\u200b {p.get_name(ctx)} - {p.host.value}" for p in host_players]),
                           inline=False)

        if gblist:
            # Need to break this up to avoid field character limit
            chunk_size = 20
            chunk_players = [active_players[i:i + chunk_size] for i in range(0, len(active_players), chunk_size)]

            for player_list in chunk_players:
                self.add_field(name="**All active players (gold, xp, # posts)**",
                               value="\n".join(f"\u200b {p.get_name(ctx)} ({p.gold}, {p.xp}, {p.num_messages})" for p in
                                               player_list),
                               inline=False)


class GuildProgress(Embed):
    def __init__(self, name: str):
        super().__init__(title=f"{name} Server Level Progress",
                         color=Color.random(),
                         timestamp=discord.utils.utcnow())

