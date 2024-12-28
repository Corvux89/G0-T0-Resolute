from discord import Embed, Color

from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player, RPPost

class PlayerOverviewEmbed(Embed):
    def __init__(self, player: Player, guild: PlayerGuild, compendium: Compendium):
        super().__init__(title=f"Information for {player.member.display_name}")
        self.set_thumbnail(url=player.member.display_avatar.url)
        self.color = player.member.color

        self.description = (f"**Chain Codes**: {player.cc:,}")

        # Guild Handicap
        if guild.handicap_cc > 0 and player.handicap_amount < guild.handicap_cc:
            self.description += f"\n**Booster enabled. All CC Rewards Doubled**"

        activity_limit = max(compendium.activity_points[0].values(), key=lambda act: act.points)
        
        # Diversion Limits
        self.add_field(name="Weekly Limits: ",
                       value=f"{ZWSP3}Diversion Chain Codes: {player.div_cc:,}/{guild.div_limit:,}\n"
                             f"{ZWSP3}Weekly Activity: {player.activity_points}/{activity_limit.points}, Level {player.activity_level}",
                       inline=False)
        
        # Starter Quests
        if player.characters and player.highest_level_character.level < 3:
            self.add_field(name="First Steps Quests:",
                           value=f"{ZWSP3}Level {player.highest_level_character.level} RPs: "
                                 f"{min(player.completed_rps, player.needed_rps)}/{player.needed_rps}\n"
                                 f"{ZWSP3}Level {player.highest_level_character.level} Arena Phases: "
                                 f"{min(player.completed_arenas, player.needed_arenas)}/{player.needed_arenas}",
                                 inline=False)
        
        # Character List
        if player.characters:
            val_str = ""
            for character in player.characters:
                class_str = f", ".join([f"{c.get_formatted_class()}" for c in character.classes])

                val_str += (f"[{character.level}] {character.name}{f' - {character.faction.value}' if character.faction else ''}\n"
                            f"{ZWSP3}{character.species.value} // {class_str}\n\n")

            self.add_field(name=f"Character Information",value=val_str,inline=False)

class RPPostEmbed(Embed):
    def __init__(self, player: Player, posts: list[RPPost]):
        super().__init__(
            title="Roleplay Request",
            color=Color.random()
        )

        self.set_thumbnail(url=player.member.avatar.url)

        for post in posts:
            self.add_field(name=f"{post.character.name}",
                           value=f"{post.note}",
                           inline=False)
            
        self.set_footer(text=f"{player.member.id}")