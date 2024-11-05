import discord

from Resolute.models.objects.npc import NPC

class NPCEmbed(discord.Embed):
    def __init__(self, npcs: list[NPC] = [], primary_npc: NPC = None):
        super().__init__(title=f"Manage NPCs",
                         color=discord.Color.random())
        
        npc = primary_npc if primary_npc else npcs[0]

        self.set_thumbnail(url=npc.avatar_url if npc and npc.avatar_url else None)

        npc_list = "\n".join([f"`{n.key}`: {n.name}{'*' if n.avatar_url else ''}" for n in npcs])

        self.add_field(name="Available NPCs (* = Has avatar)",
                       value=npc_list,
                       inline=False)
        
        
