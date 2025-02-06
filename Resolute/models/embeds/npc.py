import discord

from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.objects.NPC import NPC

class NPCEmbed(discord.Embed):
    def __init__(self, guild: PlayerGuild, npcs: list[NPC] = [], primary_npc: NPC = None):
        super().__init__(title=f"Manage NPCs",
                         color=discord.Color.random())
        
        npc = primary_npc if primary_npc else npcs[0] if len(npcs) > 0 else None

        self.set_thumbnail(url=npc.avatar_url if npc and npc.avatar_url else None)
        self.description = (
            f"Avatar for `{npc.key}`: {npc.name}" if npc and npc.avatar_url else ''
            )


        npc_list = "\n".join([f"`{n.key}`: {n.name}{'*' if n.avatar_url else ''}" for n in npcs])

        if npc and len(npc.roles) > 0:
            roles = []
            for rid in npc.roles:
                if role := guild.guild.get_role(rid):
                    roles.append(role.mention)
            self.add_field(name="Available to roles",
                           value="\n".join(roles))

        self.add_field(name="Available NPCs (* = Has avatar)",
                       value=npc_list,
                       inline=False)
        
        
