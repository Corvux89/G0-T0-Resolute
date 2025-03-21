from __future__ import annotations

import discord

from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.models.objects.arenas import Arena


class ArenaStatusEmbed(discord.Embed):
    def __init__(
        self, ctx: discord.ApplicationContext | discord.Interaction, arena: Arena
    ):
        self.arena = arena
        self.ctx = ctx
        super().__init__(
            title=f"{arena.type.value.title()} Arena Status",
            color=discord.Color.random(),
        )
        self.set_thumbnail(url=THUMBNAIL)

        self.description = (
            f"**Tier**: {arena.tier.id}\n"
            f"**Completed Phases**: {arena.completed_phases} / {arena.tier.max_phases}"
        )

        if arena.completed_phases == 0:
            self.description += f"\n\nUse the button below to join!"
        elif arena.completed_phases >= arena.tier.max_phases / 2:
            self.description += f"\nBonus active!"

        self.add_field(
            name=f"**Host**:",
            value=f"{ZWSP3}- {ctx.guild.get_member(arena.host_id).mention}",
            inline=False,
        )

        if arena.player_characters:
            self.add_field(
                name="**Players**:",
                value="\n".join(
                    [
                        f"{ZWSP3}- [{c.level}] {c.name}{' *inactive*' if not c.active else ''} ({ctx.guild.get_member(c.player_id).mention})"
                        for c in arena.player_characters
                    ]
                ),
                inline=False,
            )

    async def update(self):
        try:
            message = await self.ctx.channel.fetch_message(self.arena.pin_message_id)
        except:
            message = None

        if message:
            await message.edit(embed=self)
