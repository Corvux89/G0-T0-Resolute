import discord

from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.helpers import get_webhook
from Resolute.models.embeds import PlayerEmbed
from Resolute.models.objects.players import ArenaPost, Player, RPPost


class PlayerOverviewEmbed(PlayerEmbed):
    def __init__(self, author: discord.Member, player: Player, compendium: Compendium):
        super().__init__(author, title=f"Information for {player.member.display_name}")
        self.set_thumbnail(url=player.member.display_avatar.url)
        self.color = player.member.color

        self.description = f"**Chain Codes**: {player.cc:,}"

        # Guild Handicap
        if (
            player.guild.handicap_cc > 0
            and player.handicap_amount < player.guild.handicap_cc
        ):
            self.description += f"\n**Booster enabled. All CC Rewards Doubled**"

        activity_limit = max(
            compendium.activity_points[0].values(), key=lambda act: act.points
        )

        # Diversion Limits
        self.add_field(
            name="Weekly Limits: ",
            value=f"{ZWSP3}Diversion Chain Codes: {player.div_cc:,}/{player.guild.div_limit:,}\n"
            f"{ZWSP3}Weekly Activity: {player.activity_points}/{activity_limit.points}, Level {player.activity_level}",
            inline=False,
        )

        # Starter Quests
        if player.characters and player.highest_level_character.level < 3:
            self.add_field(
                name="First Steps Quests:",
                value=f"{ZWSP3}Level {player.highest_level_character.level} RPs: "
                f"{min(player.completed_rps, player.needed_rps)}/{player.needed_rps}\n"
                f"{ZWSP3}Level {player.highest_level_character.level} Arena Phases: "
                f"{min(player.completed_arenas, player.needed_arenas)}/{player.needed_arenas}",
                inline=False,
            )

        # Character List
        if player.characters:
            val_str = ""
            for character in player.characters:
                class_str = f", ".join(
                    [f"{c.get_formatted_class()}" for c in character.classes]
                )

                val_str += (
                    f"[{character.level}] {character.name}{f' - {character.faction.value}' if character.faction else ''}\n"
                    f"{ZWSP3}{character.species.value} // {class_str}\n\n"
                )

            self.add_field(name=f"Character Information", value=val_str, inline=False)


class ArenaPostEmbed(PlayerEmbed):
    def __init__(self, post: ArenaPost):
        super().__init__(post.player.member, title=f"{post.type.value} Arena Request")
        self.post = post

        char_str = "\n\n".join(
            [
                f"{ZWSP3}{post.characters.index(c)+1}. {c.inline_class_description()}"
                for c in post.characters
            ]
        )

        self.add_field(name="Character Priority", value=char_str, inline=False)
        self.set_footer(text=f"{post.player.id}")

    async def build(self) -> bool:
        if self.post.player.guild.arena_board_channel:
            webhook = await get_webhook(self.post.player.guild.arena_board_channel)
            if self.post.message:
                await webhook.edit_message(self.post.message.id, embed=self)
                await self.post.message.clear_reactions()
            else:
                await webhook.send(
                    username=self.post.player.member.display_name,
                    avatar_url=self.post.player.member.display_avatar.url,
                    embed=self,
                )
            return True
        return False


class RPPostEmbed(PlayerEmbed):
    def __init__(self, player: Player, posts: list[RPPost]):
        super().__init__(player.member, title="Roleplay Request")
        self.set_footer(text=f"{player.id}")

        for post in posts:
            self.add_field(
                name=f"{post.character.name}", value=f"{post.note}", inline=False
            )
