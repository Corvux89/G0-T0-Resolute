import logging

import discord
from discord import ApplicationContext, Option, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers import (get_adventure_from_category,
                              get_adventure_from_role,
                              get_faction_autocomplete, get_guild, get_player,
                              get_player_adventures, get_webhook,
                              update_activity_points, update_dm)
from Resolute.helpers.general_helpers import split_content
from Resolute.models.embeds.adventures import AdventuresEmbed
from Resolute.models.objects.adventures import (Adventure,
                                                upsert_adventure_query)
from Resolute.models.objects.exceptions import (AdventureNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.views.adventures import AdventureSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Adventures(bot))

class Adventures(commands.Cog):
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    adventure_commands = SlashCommandGroup("adventure", "Adventure commands", guild_only=True)

    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Adventures\' loaded')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "db") and ctx.guild:
            if adventure := await get_adventure_from_category(self.bot, ctx.channel.category.id):
                if ctx.author.id in adventure.dms and (npc := next((npc for npc in adventure.npcs if npc.key == ctx.invoked_with), None)):
                    guild = await get_guild(self.bot, ctx.guild.id)
                    player = await get_player(self.bot, ctx.author.id, ctx.guild.id)
                    content = ctx.message.content.replace(f'>{npc.key}', '')
                    await player.update_command_count(self.bot, "npc")
                    webhook = await get_webhook(ctx.channel)
                    chunks = split_content(content)

                    for chunk in chunks:
                        if isinstance(ctx.channel, discord.Thread):
                            await webhook.send(username=npc.name,
                                                avatar_url=npc.avatar_url if npc.avatar_url else None,
                                                content=chunk,
                                                thread=ctx.channel)
                        else:
                            await webhook.send(username=npc.name,
                                            avatar_url=npc.avatar_url if npc.avatar_url else None,
                                            content=chunk)
                            
                        if not guild.is_dev_channel(ctx.channel):
                            await player.update_post_stats(self.bot, npc, ctx.message, content=chunk)

                            if len(chunk)>=ACTIVITY_POINT_MINIMUM:
                                await update_activity_points(self.bot, player, guild)

                    await ctx.message.delete()

    @commands.slash_command(
        name="adventures",
        description="Shows active adventures for a player"
    )
    async def adventure_get(self, ctx: ApplicationContext,
                            member: Option(discord.SlashCommandOptionType(6), description="Player to get the information of", required=False),
                            phrase: Option(str, description="Additional question/phrase to add", required=False),
                            phrase2: Option(str, description="Additional question/phrase to add", required=False)):
        await ctx.defer()

        if member is None:
            member = ctx.author

        player = await get_player(self.bot, member.id, ctx.guild.id if ctx.guild else None)
        
        if not player.characters:
            raise CharacterNotFound(member)
        
        adventures = await get_player_adventures(self.bot, player)
        
        phrases = [p for p in [phrase, phrase2] if p]

        return await ctx.respond(embed=AdventuresEmbed(ctx, player, adventures, phrases))


    @adventure_commands.command(
        name="create",
        description="Creates a new adventure"
    )
    async def adventure_create(self, ctx: ApplicationContext,
                               adventure_name: Option(str, description="The name of the adventure as it should show up"
                                                                       "in the category and channel names",
                                                      required=True),
                               role_name: Option(str, description="The name of the Role to be created for adventure"
                                                                  "participants", required=True),
                               dm: Option(discord.SlashCommandOptionType(6), description="The DM of the adventure.", required=True),
                               faction1: Option(str, description="First faction this adventure is for", autocomplete=get_faction_autocomplete, required=True),
                               faction2: Option(str, description="Second faction this adventure is for", autocomplete=get_faction_autocomplete, required=True)):
        await ctx.defer()

        # Create the role
        if discord.utils.get(ctx.guild.roles, name=role_name):
            raise G0T0Error(f"Role `@{role_name}` already exists")
        else:
            g = await get_guild(self.bot, ctx.guild.id)
            adventure_role = await ctx.guild.create_role(name=role_name, mentionable=True,
                                                         reason=f"Created by {ctx.author.nick} for adventure"
                                                                f"{adventure_name}")
            
            # Setup role permissions
            category_permissions = dict()

            category_permissions[adventure_role] = discord.PermissionOverwrite(view_channel=True, 
                                                                               send_messages=True)

            if bots_role := discord.utils.get(ctx.guild.roles, name="Bots"):
                category_permissions[bots_role] = discord.PermissionOverwrite(view_channel=True,
                                                                              send_messages=True)

            if goto_role := discord.utils.get(ctx.guild.roles, name="G0-T0 Resolute"):
                category_permissions[goto_role] = discord.PermissionOverwrite(view_channel=True,
                                                                              send_messages=True,
                                                                              manage_messages=True,
                                                                              manage_channels=True)

            category_permissions[ctx.guild.default_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False
            )

            # Add DM to the role and let them manage messages in their channels
            category_permissions = await update_dm(dm, category_permissions, adventure_role, adventure_name)

            # Copy Overwrites
            ic_overwrites = category_permissions.copy()
            ooc_overwrites = category_permissions.copy()

            # Setup the questers
            if g.quest_role:
                ic_overwrites[g.quest_role] = discord.PermissionOverwrite(
                    view_channel=True
                )

                ooc_overwrites[g.quest_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

            new_adventure_category = await ctx.guild.create_category_channel(
                name=adventure_name,
                overwrites=category_permissions,
                reason=f"Creating category for {adventure_name}"
            )

            ic_channel = await ctx.guild.create_text_channel(
                name=adventure_name,
                category=new_adventure_category,
                overwrites=ic_overwrites,
                position=0,
                reason=f"Creating adventure {adventure_name} IC Room"
            )

            ooc_channel = await ctx.guild.create_text_channel(
                name=f"{adventure_name}-ooc",
                category=new_adventure_category,
                overwrites=ooc_overwrites,
                position=1,
                reason=f"Creating adventure {adventure_name} OOC Room"
            )

            adventure = Adventure(guild_id=ctx.guild.id,name=adventure_name, role_id=adventure_role.id, dms=[dm.id],
                                  category_channel_id=new_adventure_category.id, cc=0)
            
            async with self.bot.db.acquire() as conn:
                await conn.execute(upsert_adventure_query(adventure))

            await ooc_channel.send(f"Adventure {adventure.name} successfully created!\n"
                                   f"Role: {adventure_role.mention}\n"
                                   f"IC Room: {ic_channel.mention}\n"
                                   f"OOC Room: {ooc_channel.mention}\n\n"
                                   f"{dm.mention} - Please ensure your permissions are correct in these rooms! "
                                   f"If so, you can start adding players with `/adventure manage`")

            await ctx.delete()

    @adventure_create.error
    async def create_error(self, ctx, error):
        if isinstance(error, discord.Forbidden):
            raise G0T0Error(f"Bot isn't allowed to do that for some reason")
        elif isinstance(error, discord.HTTPException):
            raise G0T0Error(f"Error createing new role")
        elif isinstance(error, discord.InvalidArgument):
            raise G0T0Error(f"Invalid Argument: {error}")

    @adventure_commands.command(
        name="manage",
        description="Manage an adventure. Either run in the adventure channel or specify a role/category"
    )
    async def adventure_manage(self, ctx: ApplicationContext,
                               role: Option(discord.Role, description="Role of the adventure", required=False),
                               channel_category: Option(discord.CategoryChannel, description="Adventure Channel Category", required=False)):
        if role:
            adventure = await get_adventure_from_role(self.bot, role.id)
        elif channel_category:
            adventure = await get_adventure_from_category(self.bot, channel_category.id)
        else:
            adventure = await get_adventure_from_category(self.bot, ctx.channel.category.id)

        if adventure is None:
            raise AdventureNotFound()
        
        ui = AdventureSettingsUI.new(self.bot, ctx.author, adventure)
        await ui.send_to(ctx)
        await ctx.delete()