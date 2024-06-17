from discord import Embed, Member

from Resolute.compendium import Compendium
from Resolute.constants import ZWSP3
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player

class PlayerOverviewEmbed(Embed):
    def __init__(self, player: Player, guild: PlayerGuild, compendium: Compendium):
        super().__init__(title=f"Information for {player.member.display_name}")
        self.set_thumbnail(url=player.member.display_avatar.url)
        self.color = player.member.color

        self.description = f"**Chain Codes**: {player.cc:,}"

        # Guild Handicap
        if guild.handicap_cc > 0 and player.handicap_amount < guild.handicap_cc:
            self.description += f"\n**Booster enabled. All CC Rewards Doubled**"
        
        # Diversion Limits
        self.add_field(name="Weekly Limits: ",
                       value=f"{ZWSP3}Diversion Chain Codes: {player.div_cc:,}/{guild.div_limit:,}",
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
            for character in player.characters:
                starship_str = ""

                if character.starships:
                    starship_str = f"{ZWSP3}**Starships**:\n" + "\n".join([f"{ZWSP3*2}{s.get_formatted_starship(compendium)}" for s in character.starships]) 

                class_str = "\n".join([f" {c.get_formatted_class()}" for c in character.classes])

                self.add_field(name=f"Character: {character.name}",
                               value=f"{ZWSP3}**Class{'es' if len(character.classes) > 1 else ''}**: {class_str}\n"
                                     f"{ZWSP3}**Species**: {character.species.value}\n"
                                     f"{ZWSP3}**Level**: {character.level}\n"
                                     f"{ZWSP3}**Credits**: {character.credits:,}\n"
                                     f"{starship_str}",
                                inline=False)