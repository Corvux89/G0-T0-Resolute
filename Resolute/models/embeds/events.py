from discord import Embed, Member

from Resolute.bot import G0T0Bot
from Resolute.constants import ZWSP3
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.arenas import Arena
from Resolute.models.objects.players import Player

class MemberLeaveEmbed(Embed):
    def __init__(self, player: Player, adventures: list[Adventure] = [], arenas: list[Arena] = []):
        super().__init__(title=f"{str(player.member)} ( {f'`{player.member.nick}`' if player.member.nick else 'No nickname'}) has left the server")
                
        dm_str = "\n".join([f"{ZWSP3}{adventure.name} ( {player.member.guild.get_role(adventure.role_id).mention} )" for adventure in adventures if player.id in adventure.dms]) if len(adventures)>0 else None

        if dm_str is not None:
            self.add_field(name=f"DM'ing Adventures",
                           value=dm_str,
                           inline=False)

        host_str = "\n".join([f"{ZWSP3}{player.member.guild.get_channel(arena.channel_id).mention}" for arena in arenas if player.id == arena.host_id]) if len(arenas)>0 else None

        if host_str is not None:
            self.add_field(name=f"Hosting Arenas",
                           value=host_str,
                           inline=False)


        for character in player.characters:
            class_str = ",".join([f" {c.get_formatted_class()}" for c in character.classes])
            adventures = [a for a in adventures if character.id in a.characters]
            arenas = [a for a in arenas if character.id in a.characters]
            f_str = f"{ZWSP3}**Adventures ({len(adventures)})**:\n"
            f_str += "\n".join([f"{ZWSP3*2}{adventure.name} ( DM{'s' if len(adventure.dms) > 1 else ''}: {', '.join([f'{player.member.guild.get_member(dm).mention}' for dm in adventure.dms])} )" for adventure in adventures]) if len(adventures)>0 else f"{ZWSP3*2} None"

            f_str+= f"\n\n{ZWSP3}**Arenas ({len(arenas)})**:\n"
            f_str += "\n".join([f"{ZWSP3*2}{player.member.guild.get_channel(arena.channel_id)}" for arena in arenas]) if len(arenas)>0 else f"{ZWSP3*2} None"


            self.add_field(name=f"Character: {character.name} - Level {character.level} [{class_str}]",
                           value=f_str,
                           inline=False)
            

