from __future__ import annotations
from typing import TYPE_CHECKING

import discord

from Resolute.constants import THUMBNAIL
from Resolute.helpers import process_message

if TYPE_CHECKING:
    from Resolute.models.objects.characters import PlayerCharacter
    from Resolute.models.objects.guilds import PlayerGuild


class ResetEmbed(discord.Embed):
    def __init__(self, g: PlayerGuild, **kwargs):
        super().__init__(
            color=discord.Color.random(),
            title=kwargs.get("title", "Weekly Reset"),
            timestamp=discord.utils.utcnow(),
        )

        self.set_thumbnail(url=THUMBNAIL)

        if "reset" in self.title.lower() and g.reset_message:
            self.description = f"{process_message(g.reset_message, g)}"

        if g.calendar and g.server_date:
            self.add_field(
                name="Galactic Date",
                value=f"{g.formatted_server_date}",
                inline=False,
            )

            if (birthdays := kwargs.get("birthdays", [])) and len(birthdays) > 0:
                birthday_str = []
                birthdays: list[PlayerCharacter]

                for character in birthdays:
                    if member := g.guild.get_member(character.player_id):
                        birthday_str.append(
                            f"{character.name} ({member.mention})\n - {character.dob_month(g).display_name}:{character.dob_day(g):02}, {character.age(g)} years"
                        )

                self.add_field(name="Happy Birthday!", value="\n".join(birthday_str))

        if time := kwargs.get("complete_time", 0):
            self.set_footer(text=f"Weekly reset complete in {time:.2f} seconds")
