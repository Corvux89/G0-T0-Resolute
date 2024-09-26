from discord import Embed, ApplicationContext, Interaction, Color
from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.models.objects.arenas import Arena

class ArenaStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | Interaction, arena: Arena):
        super().__init__(title="Arena Status", color=Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.description = f"**Tier**: {arena.tier.id}\n"\
                           f"**Completed Phases**: {arena.completed_phases} / {arena.tier.max_phases}"
        
        if arena.completed_phases == 0:
            self.description += f"\n\nUse the button below to join!"
        elif arena.completed_phases >= arena.tier.max_phases / 2:
            self.description += f"\nBonus active!"

        self.add_field(name=f"**Host**:",
                       value=f"{ZWSP3}- {ctx.guild.get_member(arena.host_id).mention}",
                       inline=False)
        
        if arena.player_characters:
            self.add_field(name="**Players**:",
                        value="\n".join([f"{ZWSP3}- {c.name}{'*inactive*' if not c.active else ''} ({ctx.guild.get_member(c.player_id).mention})" for c in arena.player_characters]),
                        inline=False)
            
class ArenaPhaseEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, arena: Arena, result: str):
        super().__init__(
            title=f"Phase {arena.completed_phases} Complete!",
            description=f"Complete phases: **{arena.completed_phases} / {arena.tier.max_phases}**",
            color=Color.random()
        )

        self.set_thumbnail(url=THUMBNAIL)

        bonus = (arena.completed_phases > arena.tier.max_phases / 2) and result == "WIN"

        field_str = [f"{ctx.guild.get_member(arena.host_id).mention or 'Player not found'}: 'HOST'"]

        for character in arena.player_characters:
            text = f"{character.name} ({ctx.guild.get_member(character.player_id).mention or 'Player not found'}): '{result}'{f', `BONUS`' if bonus else ''}"
            field_str.append(text)
        
        self.add_field(name="The following rewards have been applied:",
                       value="\n".join(field_str),
                       inline=False)