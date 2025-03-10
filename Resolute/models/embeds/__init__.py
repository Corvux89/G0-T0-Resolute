from __future__ import annotations
from typing import TYPE_CHECKING

import discord

from Resolute.helpers.general_helpers import chunk_text

if TYPE_CHECKING:
    from Resolute.models.objects.players import Player
    from Resolute.models.objects.characters import PlayerCharacter


class ErrorEmbed(discord.Embed):
    def __init__(self, description, *args, **kwargs):
        kwargs["title"] = "Error:"
        kwargs["color"] = discord.Color.brand_red()
        kwargs["description"] = kwargs.get("description", description)
        super().__init__(**kwargs)


class PlayerEmbed(discord.Embed):
    def __init__(self, member: discord.Member, *args, **kwargs):
        super().__init__(**kwargs)
        self.color = member.color
        self.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )


class CharacterEmbed(PlayerEmbed):
    def __init__(self, player: Player, character: PlayerCharacter, *args, **kwargs):
        super().__init__(player.member, *args, **kwargs)
        self.set_thumbnail(
            url=(
                player.member.display_avatar.url
                if player.member.display_avatar
                else character.avatar_url if character.avatar_url else None
            )
        )


class PaginatedEmbed(discord.Embed):
    EMBED_MAX = 6000
    EMBED_FIELD_MAX = 1024
    EMBED_DESC_MAX = 4096
    EMBED_TITLE_MAX = 256
    CONTINUATION_FIELD_TITLE = "** **"

    def __init__(
        self, first_embed: discord.Embed = None, copy_kwargs=("color",), **kwargs
    ):
        self._current_field_name = ""
        self._current_field_inline = False
        self._current_field = []
        self._field_count = 0

        self._footer_url = None
        self._footer_text = None

        if not first_embed:
            first_embed = discord.Embed(**kwargs)

        self._embed_count = len(first_embed)
        self._default_embed_options = {
            c: getattr(first_embed, c) for c in copy_kwargs if hasattr(first_embed, c)
        }
        self._default_embed_options.update(kwargs)
        self._embeds = [first_embed]

    @property
    def _current(self):
        return self._embeds[-1]

    def add_title(self, value):
        if (
            len(value) > self.EMBED_TITLE_MAX
            or len(value) + self._embed_count > self.EMBED_MAX
        ):
            raise ValueError("The current embed cannot fit this title.")

        self._current.title = value
        self._embed_count += len(value)

    def add_description(self, value):
        if (
            len(value) > self.EMBED_DESC_MAX
            or len(value) + self._embed_count > self.EMBED_MAX
        ):
            raise ValueError("The current embed cannot fit this description.")

        self._current.description = value
        self._embed_count += len(value)

    def add_field(self, name="", value="", inline=False):
        if len(name) > self.EMBED_FIELD_MAX:
            raise ValueError("This value is too large to store in an embed field")

        if self._current_field:
            self.close_field()

        self._current_field_name = name
        self._current_field_inline = inline
        self.extend_field(value)

    def extend_field(self, value):
        if not value:
            return
        chunks = chunk_text(value, max_chunk_size=self.EMBED_FIELD_MAX - 1)

        if self._field_count + len(chunks[0]) + 1 > self.EMBED_FIELD_MAX:
            self.close_field()
            self._current_field_name = self.CONTINUATION_FIELD_TITLE

        for i, chunk in enumerate(chunks):
            self._field_count += len(value) + 1
            self._current_field.append(chunk)
            if i < len(chunks) - 1:
                self.close_field()
                self._current_field_name = self.CONTINUATION_FIELD_TITLE

    def close_field(self):
        value = "\n".join(self._current_field)

        if (
            self._embed_count + len(value) + len(self._current_field_name)
            > self.EMBED_MAX
        ):
            self.close_embed()

        self._current.add_field(
            name=self._current_field_name,
            value=value,
            inline=self._current_field_inline,
        )
        self._embed_count += len(value) + len(self._current_field_name)

        self._current_field_name = ""
        self._current_field_inline = False
        self._current_field = []
        self._field_count = 0

    def close_embed(self):
        self._embeds.append(discord.Embed(**self._default_embed_options))
        self._embed_count = 0

    def set_footer(self, icon_url=None, value=None):
        self._footer_url = icon_url
        self._footer_text = value

    def close_footer(self):
        current_count = self._embed_count
        kwargs = {}
        if self._footer_url:
            current_count += len(self._footer_url)
            kwargs["icon_url"] = self._footer_url
        if self._footer_text:
            current_count += len(self._footer_text)
            kwargs["text"] = self._footer_text
        if current_count > self.EMBED_MAX:
            self.close_embed()

        if kwargs:
            self._current.set_footer(**kwargs)

    def close_embed(self):
        self._embeds.append(discord.Embed(**self._default_embed_options))
        self._embed_count = 0

    def __len__(self):
        total = sum(len(e) for e in self._embeds)
        return total + self._embed_count

    @property
    def embeds(self):
        if self._field_count:
            self.close_field()
        self.close_footer()
        return self._embeds

    async def send_to(self, destination, **kwargs):
        for embed in self.embeds:
            await destination.send(embed=embed, **kwargs)

    def __repr__(self):
        return (
            f"<EmbedPaginator _current_field_name={self._current_field_name} _field_count={self._field_count} "
            f"_embed_count={self._embed_count}>"
        )
