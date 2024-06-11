from discord import Embed, Member

from Resolute.bot import G0T0Bot
from Resolute.models.objects.players import Player

class MemberLeaveEmbed(Embed):
    def __init__(self, bot: G0T0Bot, member: Member, player: Player):
        super().__init__(title=f"{str(member)} ( {f'`{member.nick}`' if member.nick else 'No nickname'}) has left the server")
                
        dm_str = "\n".join([f"\u200b \u200b \u200b {adventure.name} ( {member.guild.get_role(adventure.role_id).mention} )" for adventure in player.adventures if player.id in adventure.dms]) if len(player.adventures)>0 else None

        if dm_str is not None:
            self.add_field(name=f"DM'ing Adventures",
                           value=dm_str,
                           inline=False)

        host_str = "\n".join([f"\u200b \u200b \u200b {member.guild.get_channel(arena.channel_id).mention}" for arena in player.arenas if player.id == arena.host_id]) if len(player.arenas)>0 else None

        if host_str is not None:
            self.add_field(name=f"Hosting Arenas",
                           value=host_str,
                           inline=False)


        for character in player.characters:
            class_str = ",".join([f" {c.get_formatted_class()}" for c in character.classes])
            adventures = [a for a in player.adventures if character.id in a.characters]
            arenas = [a for a in player.arenas if character.id in a.characters]
            f_str = f"\u200b \u200b \u200b **Adventures ({len(adventures)})**:\n"
            f_str += "\n".join([f"\u200b \u200b \u200b \u200b \u200b \u200b {adventure.name} ( DM{'s' if len(adventure.dms) > 1 else ''}: {', '.join([f'{member.guild.get_member(dm).mention}' for dm in adventure.dms])} )" for adventure in adventures]) if len(adventures)>0 else "\u200b \u200b \u200b \u200b \u200b \u200b None"

            f_str+= f"\n\n\u200b \u200b \u200b **Arenas ({len(arenas)})**:\n"
            f_str += "\n".join([f"\u200b \u200b \u200b \u200b \u200b \u200b {member.guild.get_channel(arena.channel_id)}" for arena in arenas]) if len(arenas)>0 else "\u200b \u200b \u200b \u200b \u200b \u200b None"


            self.add_field(name=f"Character: {character.name} - Level {character.level} [{class_str}]",
                           value=f_str,
                           inline=False)
            

