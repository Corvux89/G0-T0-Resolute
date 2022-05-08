from typing import Dict, Any, List

import discord
from discord import Embed, Color, ApplicationContext
from discord.types.embed import EmbedField

from ProphetBot.constants import MAX_PHASES
from ProphetBot.models.sheets_objects import LogEntry, Character


def linebreak() -> Dict[str, Any]:
    return {
        'name': discord.utils.escape_markdown('___________________________________________'),
        'value': '\u200B',
        'inline': False
    }


class LogEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, log_entry: LogEntry):
        player = log_entry.character.get_member(ctx)
        description = f"**Player:** {player.mention}\n"
        if log_entry.outcome:
            description += f"**Item/Reason:** {log_entry.outcome}\n"
        if log_entry.gp is not None:
            description += f"**Gold:** {log_entry.gp}\n"
        if log_entry.xp is not None:
            description += f"**Experience:** {log_entry.xp}"

        super().__init__(
            title=f"{log_entry.activity.value} Logged - {log_entry.character.name}",
            description=description,
            color=Color.random()
        )
        self.set_thumbnail(url=player.display_avatar.url)
        self.set_footer(text=f"Logged by {log_entry.author}", icon_url=ctx.author.display_avatar.url)


class ErrorEmbed(Embed):

    def __init__(self, *args, **kwargs):
        kwargs['title'] = "Error:"
        kwargs['color'] = Color.brand_red()
        super().__init__(**kwargs)


class ArenaStatusEmbed(Embed):

    def __init__(self, host: Character, tier: int, completed_phases: int, players: List[Character] = None):
        super().__init__(title=f"Arena Status",
                         description=f"**Tier:** {tier}\n"
                                     f"**Completed Phases**: {completed_phases} / {MAX_PHASES[tier]}",
                         color=Color.random())
        self.set_thumbnail(url="https://cdn.discordapp.com/emojis/712399492560978000.webp?size=96&quality=lossless")
        if completed_phases == 0:
            self.description += "\n\nUse the button below to join!"
        if completed_phases >= MAX_PHASES[tier] / 2:
            self.description += "\nBonus active!"

        self.add_field(name="**Host:**", value=f"\u200b -{host.mention()}", inline=False)
        if players is not None:
            self.add_field(name="**Players:**",
                           value="\n".join([f"\u200b -{p.mention()}" for p in players]),
                           inline=False)