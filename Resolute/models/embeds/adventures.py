from discord import Embed, ApplicationContext, Color, Interaction

from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.players import Player

class AdventuresEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, player: Player, phrases: list[str]):
        super().__init__(title=f"Adventure Information for {player.member.display_name}",
                         color=Color.dark_grey())
        
        self.set_thumbnail(url=player.member.display_avatar.url)
        
        guild = ctx.guild if ctx.guild else player.member.guild

        dm_str = adventure_str = "\n".join([f"{ZWSP3}{adventure.name} ({guild.get_role(adventure.role_id).mention})" for adventure in player.adventures if player.id in adventure.dms]) if len(player.adventures)>0 else None

        if dm_str is not None:
            self.add_field(name=f"DM'ing Adventures",
                           value=dm_str,
                           inline=False)


        for character in player.characters:
            adventure_str = "\n".join([f"{ZWSP3}{adventure.name} ({guild.get_role(adventure.role_id).mention})" for adventure in player.adventures if character.id in adventure.characters]) if len(player.adventures)>0 else "None"
            class_str = ",".join([f" {c.get_formatted_class()}" for c in character.classes])
            self.add_field(name=f"{character.name} - Level {character.level} [{class_str}]",
                           value=adventure_str or "None",
                           inline=False)
        
        if phrases:
            for p in phrases:
                out_str = p.split("|")
                self.add_field(name=out_str[0],
                               value=f"{out_str[1] if len(out_str) > 1 else ''}",
                               inline=False)
                
class AdventureSettingsEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | Interaction, adventure: Adventure):
        super().__init__(title=f"{adventure.name}",
                         color=Color.random())
        self.set_thumbnail(url=THUMBNAIL)
        
        self.description = f"**Adventure Role**: {ctx.guild.get_role(adventure.role_id).mention}\n"\
                           f"**CC Earned to date**: {adventure.cc}"
        
        if len(adventure.factions) > 0:
            self.description += f"\n**Factions**:\n" + "\n".join([f"{ZWSP3}{f.value}" for f in adventure.factions])
        
        self.add_field(name=f"DM{'s' if len(adventure.dms) > 1 else ''}",
                       value="\n".join([f"{ZWSP3}- {ctx.guild.get_member(dm).mention}" for dm in adventure.dms]),
                       inline=False)
        
        if adventure.player_characters:
            self.add_field(name="Players",
                           value="\n".join([f"{ZWSP3}- {character.name} ({ctx.guild.get_member(character.player_id).mention})" for character in adventure.player_characters]),
                           inline=False)
            
class AdventureRewardEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | Interaction, adventure: Adventure, cc: int):
        super().__init__(
            title=f"Adventure Rewards",
            description=f"**Adventure**: {adventure.name}\n"
                        f"**CC Earned**: {cc:,}\n"
                        f"**CC Earned to date**: {adventure.cc:,}\n",
            color=Color.random()
        )
        self.set_thumbnail(url=THUMBNAIL)
        self.set_footer(text=f"Logged by {ctx.user.name}",
                        icon_url=ctx.user.display_avatar.url)


        self.add_field(name=f"DM{'s' if len(adventure.dms) > 1 else ''}",
                       value="\n".join([f"{ZWSP3}- {ctx.guild.get_member(dm).mention}" for dm in adventure.dms]),
                       inline=False)
        
        if adventure.player_characters:
            self.add_field(name="Players",
                           value="\n".join([f"{ZWSP3}- {character.name} ({ctx.guild.get_member(character.player_id).mention})" for character in adventure.player_characters]),
                           inline=False)
