from discord import Embed, Member, Color
from Resolute.bot import G0T0Bot
from Resolute.compendium import Compendium
from Resolute.helpers.characters import get_character
from Resolute.models.objects.players import Player
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.characters import CharacterStarship, PlayerCharacter, PlayerCharacterClass
from Resolute.models.objects.logs import DBLog
                
            
class NewCharacterSetupEmbed(Embed):
    def __init__(self, player: Player, member: Member, guild: PlayerGuild, new_character: PlayerCharacter, newClass: PlayerCharacterClass, 
                 starting_credits: int = 0, cc_credit: int = 0, transfer_ship: bool=False):
        super().__init__(title=f"Information for {member.display_name}")
        self.set_thumbnail(url=member.display_avatar.url)
        self.color = member.color

        self.description = f"**Name**: {new_character.name if new_character.name else ''}\n" \
                           f"**Level**: {new_character.level}{f' (*Too high for server. Max server level is `{guild.max_level}`*)' if new_character.level > guild.max_level else ''}\n" \
                           f"**Species**: {new_character.species.value if hasattr(new_character.species, 'value') else ''}\n" \
                           f"**Class**: {newClass.get_formatted_class() if hasattr(newClass, 'primary_class') else ''}\n"\
                           f"**Starting Credits**: {starting_credits:,}\n" 
                           
        if cc_credit != 0:
            self.description += f"**CC Adjustment**: {cc_credit}{f''' (*This would put the player at {player.cc + cc_credit:,} CC*)''' if player.cc + cc_credit < 0 else ''}\n"
        
        if transfer_ship:
            self.description += f"**Transfer Ship**: True"

class NewcharacterEmbed(Embed):
    def __init__(self, author: Member, member: Member, character: PlayerCharacter, log: DBLog, compendium: Compendium):
        super().__init__(title=f"Character Created - {character.name}")

        self.description = f"**Player**: {member.mention}\n"\
                           f"**Level**: {character.level}\n"\
                           f"**Species**: {character.species.value}\n"\
                           f"**Class**: {character.classes[0].get_formatted_class()}\n"\
                           f"**Starting Credits**: {log.credits:,}\n"\
                           f"{f'**CC Adjustment**: {log.cc:,}' if log.cc != 0 and log.cc != None else ''}"
        
        if len(character.starships) > 0:
            self.add_field(name="Starships: ",
                           value = f"\n".join([f"\u200b \u200b \u200b {s.get_formatted_starship(compendium)}" for s in character.starships]))
        
        self.color = Color.random()
        self.set_thumbnail(url=member.display_avatar.url)
        self.set_footer(text=f"Created by: {author.name} - Log #: {log.id}",
                        icon_url=author.display_avatar.url)
        
class CharacterEmbed(Embed):
    def __init__(self, member: Member, character: PlayerCharacter, compendium: Compendium):
        super().__init__(title=f"Character Info - {character.name}")
        self.color = member.color
        self.set_thumbnail(url=member.display_avatar.url)

        starship_str = ""

        if character.starships:
            starship_str = "\u200b \u200b \u200b **Starships**:\n" + "\n".join([f"\u200b \u200b \u200b \u200b \u200b \u200b {s.get_formatted_starship(compendium)}" for s in character.starships]) 

        class_str = "\n".join([f" {c.get_formatted_class()}" for c in character.classes])

        self.description = f"**Class{'es' if len(character.classes) > 1 else ''}**: {class_str}\n"\
                           f"**Species**: {character.species.value}\n"\
                           f"**Level**: {character.level}\n"\
                           f"**Credits**: {character.credits}\n"\
                           f"{starship_str}"


class StarshipEmbed(Embed):
    def __init__(self, bot: G0T0Bot, member: Member, starship: CharacterStarship):
        super().__init__(title=f"{starship.name} Information")
        self.color = member.color
        self.set_thumbnail(url=member.display_avatar.url)

        self.description = f"**Tier**: {starship.tier}\n"\
                           f"**Size**: {starship.starship.get_size(bot.compendium).value}\n"\
                           f"**Role**: {starship.starship.value}"


        self.add_field(name=f"Owner{'s' if len(starship.character_id) > 1 else ''}",
                       value="\n".join([f"{char.name} ( {member.guild.get_member(char.player_id).mention} )" for char in starship.owners]),
                       inline=False)
        
class LevelUpEmbed(Embed):
    def __init__(self, member: Member, character: PlayerCharacter):
        super().__init__(title=f"{character.name} ({member.mention}) is now level {character.level}",
                         color=Color.random())
        self.set_thumbnail(url=member.display_avatar.url)