from discord import Embed, Member

from Resolute.compendium import Compendium
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.players import Player

class PlayerOverviewEmbed(Embed):
    def __init__(self, player: Player, member: Member, guild: PlayerGuild, compendium: Compendium):
        super().__init__(title=f"Information for {member.display_name}")
        self.set_thumbnail(url=member.display_avatar.url)
        self.color = member.color

        self.description = f"**Chain Codes**: {player.cc:,}"

        # Guild Handicap
        if guild.handicap_cc > 0 and player.handicap_amount < guild.handicap_cc:
            self.description += f"\n**Booster enabled. All CC Rewards Coubled**"
        
        # Diversion Limits
        self.add_field(name="Weekly Limits: ",
                       value=f"\u200b \u200b \u200b Diversion Chain Codes: {player.div_cc:,}/{guild.div_limit:,}",
                       inline=False)
        
        # Starter Quests
        if player.characters and player.highest_level_character.level < 3:
            self.add_field(name="First Steps Quests:",
                           value=f"\u200b \u200b \u200b Level {player.highest_level_character.level} RPs: "
                                 f"{min(player.completed_rps, player.needed_rps)}/{player.needed_rps}\n"
                                 f"\u200b \u200b \u200b Level {player.highest_level_character.level} Arena Phases: "
                                 f"{min(player.completed_arenas, player.needed_arenas)}/{player.needed_arenas}",
                                 inline=False)
        
        # Character List
        if player.characters:
            for character in player.characters:
                starship_str = ""

                if character.starships:
                    starship_str = "\u200b \u200b \u200b **Starships**:\n" + "\n".join([f"\u200b \u200b \u200b \u200b \u200b \u200b {s.get_formatted_starship(compendium)}" for s in character.starships]) 

                class_str = "\n".join([f" {c.get_formatted_class()}" for c in character.classes])

                self.add_field(name=f"Character: {character.name}",
                               value=f"\u200b \u200b \u200b **Class{'es' if len(character.classes) > 1 else ''}**: {class_str}\n"
                                     f"\u200b \u200b \u200b **Species**: {character.species.value}\n"
                                     f"\u200b \u200b \u200b **Level**: {character.level}\n"
                                     f"\u200b \u200b \u200b **Credits**: {character.credits:,}\n"
                                     f"{starship_str}",
                                inline=False)