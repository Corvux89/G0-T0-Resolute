import logging

import discord
import re
from discord import Embed
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers import get_character, get_player_adventures, get_or_create_guild
from Resolute.helpers.ref_helpers import get_cached_application
from Resolute.models.db_objects import PlayerCharacter
from Resolute.queries.ref_queries import delete_player_application

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))

class Events(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Events\' loaded')
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Cleanup Reference Tables
        async with self.bot.db.acquire() as conn:
            await conn.execute(delete_player_application(member.id))


        if exit_channel := discord.utils.get(member.guild.channels, name="exit"):
            character: PlayerCharacter = await get_character(self.bot, member.id, member.guild.id)
            adventures = await get_player_adventures(self.bot, member)

            embed = Embed(title=f'{str(member)}')

            if member.nick is not None:
                embed.title += f" ( `{member.nick}` )"
            else:
                embed.title += f"( No nickname )"

            embed.title += f" has left the server.\n\n"

            if character is None:
                value = "\n".join(f'\u200b - {r.mention}' for r in member.roles if 'everyone' not in r.name)

                embed.add_field(name="Roles", value=value, inline=False)

            else:
                embed.description = f"**Character:** {character.name}\n" \
                                    f"**Level:** {character.level}\n"

            if len(adventures['player']) > 0 or len(adventures['dm']) > 0:
                value = "\n".join([f'\u200b - {a.name}*' for a in adventures['dm']])
                value += "\n".join([f'\u200b - {a.name}' for a in adventures['player']])
                count = len(adventures['player']) + len(adventures['dm'])
            else:
                value = "*None*"
                count = 0
            embed.add_field(name=f"Adventures ({count})", value=value, inline=False)

            arenas = [r for r in member.roles if 'arena' in r.name.lower()]

            if len(arenas) > 0:
                value = "\n".join(f'\u200b - {r.mention}' for r in arenas)
                count = len(arenas)
            else:
                value = "*None*"
                count = 0
            embed.add_field(name=f"Arenas ({count})", value=value, inline=False)

            try:
                await exit_channel.send(embed=embed)
            except Exception as error:
                if isinstance(error, discord.errors.HTTPException):
                    log.error(f"ON_MEMBER_REMOVE: Error sending message to exit channel in "
                              f"{member.guild.name} [ {member.guild.id} ] for {member.name} [ {member.id} ]")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = await get_or_create_guild(self.bot.db, member.guild.id)

        if (entrance_channel := discord.utils.get(member.guild.channels, name="entrance")) and g.greeting:
            message = g.greeting

            pattern = r'{#([^}]*)}'
            channels = re.findall(pattern, message)
            for c in channels:
                ch = discord.utils.get(member.guild.channels, name=c)
                message = message.replace("{#"+c+"}", f"{ch.mention}") if ch else message

            message = message.replace("{user}", f"{member.mention}")

            await entrance_channel.send(message)
