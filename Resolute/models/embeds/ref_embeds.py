from typing import Dict, List

import discord
from discord import Embed, Color, ApplicationContext

from Resolute.constants import THUMBNAIL
from Resolute.models.db_objects import GlobalEvent, GlobalPlayer


class RpDashboardEmbed(Embed):

    def __init__(self, channel_statuses: Dict[str, List[str]], category_name: str):
        super(RpDashboardEmbed, self).__init__(
            color=Color.dark_grey(),
            title=f"Channel Statuses - {category_name}",
            timestamp=discord.utils.utcnow()
        )
        if len(channel_statuses["Archivist"]) > 0:
            self.add_field(
                name="<:pencil:989284061786808380> -- Awaiting Archivist",
                value="\n".join(channel_statuses["Archivist"]),
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


class GlobalEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, g_event: GlobalEvent, players: List[GlobalPlayer],
                 gblist: bool = False):
        super().__init__(title=f"Global - Log Preview",
                         colour=Color.random())

        names = g_event.get_channel_names(ctx.bot)

        active_players = [p for p in players if p.active]
        override_players = [p for p in players if not p.update]

        self.set_thumbnail(
            url=THUMBNAIL
        )



        self.add_field(name=f"**Information for {g_event.name}**",
                       value=f"\n *Base Chain Codes:* {g_event.base_cc:,} \n*# Players:* {len(active_players)}",
                       inline=False)

        if names:
            self.add_field(name="**Scraped Channels**",
                           value="\n".join([f"\u200b # {c}" for c in names]),
                           inline=False)
        else:
            self.add_field(name="**Scraped Channels**",
                           value="None",
                           inline=False)

        if override_players:
            self.add_field(name="**Manual Overrides (cc)**",
                           value="\n".join([f"\u200b {p.get_name(ctx)} ({p.cc:,})" for p in override_players]),
                           inline=False)

        if gblist:
            # Need to break this up to avoid field character limit
            chunk_size = 20
            chunk_players = [active_players[i:i + chunk_size] for i in range(0, len(active_players), chunk_size)]

            for player_list in chunk_players:
                self.add_field(name="**All active players (gold, xp, # posts)**",
                               value="\n".join(f"\u200b {p.get_name(ctx)} ({p.cc:,}, {p.num_messages})" for p in
                                               player_list),
                               inline=False)

