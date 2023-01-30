from typing import List

import aiopg.sa
import discord
from discord import ButtonStyle
from discord.ui import Button

from ProphetBot.helpers import get_arena
from ProphetBot.helpers.entity_helpers import add_player_to_arena
from ProphetBot.models.db_objects import Arena, ArenaTier


class ArenaView(discord.ui.View):
    db: aiopg.sa.Engine

    def __init__(self, db: aiopg.sa.Engine):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="Join Arena", custom_id="join_arena", style=ButtonStyle.primary)
    async def view_callback(self, button: Button, interaction: discord.Interaction):
        arena: Arena = await get_arena(interaction.client, interaction.channel_id)

        if arena is None:
            return await interaction.response.send_message(f"Error: No active arena present in this channel.",
                                                           ephemeral=True)
        elif not (channel_role := discord.utils.get(interaction.guild.roles, id=arena.role_id)):
            return await interaction.response.send_message(f"Error: Role @{interaction.channel.name} doesn't exist. "
                                                           f"A Council member may need to create it.", ephemeral=True)
        elif interaction.user.id == arena.host_id:
            return await interaction.response.send_message(f"Error: You're the host.", ephemeral=True)
        elif interaction.user in channel_role.members:
            return await interaction.response.send_message(f"Error: You are already a participant in this arena.",
                                                           ephemeral=True)

        await add_player_to_arena(interaction, interaction.user, arena, self.db, interaction.client.compendium)
