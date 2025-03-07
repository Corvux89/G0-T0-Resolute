from __future__ import annotations
from typing import TYPE_CHECKING

import discord

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
        self.set_author(name=member.display_name, icon_url=member.display_avatar.url)


class CharacterEmbed(PlayerEmbed):
    def __init__(self, player: Player, character: PlayerCharacter, *args, **kwargs):
        super().__init__(player.member, *args, **kwargs)
        self.set_thumbnail(
            url=(
                player.member.display_avatar.url
                if not character.avatar_url
                else character.avatar_url
            )
        )
