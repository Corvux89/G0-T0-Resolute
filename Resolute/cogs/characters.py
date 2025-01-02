import logging
import re

import discord
from discord import ApplicationContext, Option, SlashCommandGroup
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers import (get_cached_application, get_guild,
                              get_level_up_application,
                              get_new_character_application, get_player,
                              get_webhook_character,
                              update_activity_points)
from Resolute.helpers.general_helpers import split_content
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.objects.exceptions import (ApplicationNotFound,
                                                CharacterNotFound,
                                                G0T0Error)
from Resolute.models.views.applications import (CharacterSelectUI,
                                                LevelUpRequestModal,
                                                NewCharacterRequestUI)
from Resolute.models.views.character_view import (CharacterGetUI,
                                                  CharacterManageUI,
                                                  CharacterSettingsUI, RPPostUI)

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Character(bot))


class Character(commands.Cog):
    # TODO: Character Reroll Renown Conversion
    bot: G0T0Bot
    character_admin_commands = SlashCommandGroup("character_admin", "Character administration commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Characters\' loaded')    

    @commands.command(
        name="say",
        guild_only=True
    )
    async def character_say(self, ctx: ApplicationContext):

        content = ctx.message.content

        content = content.replace(f">say ", "")
        await ctx.message.delete()

        if content == "" or content == ">say":
            return
        
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id)
        g = await get_guild(self.bot, ctx.guild.id)
        character = None

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        if match := re.match(r"^(['\"])(.*?)\1", content):
            search = match.group(2)
            character = next((c for c in player.characters if search.lower() in c.name.lower()), None)
            if character:
                content = re.sub(r"^(['\"])(.*?)\1\s*", "", content, count=1)
            
        if not character:
            character = await get_webhook_character(self.bot, player, ctx.channel)

        chunks = split_content(content)
        for chunk in chunks:
            await player.send_webhook_message(self.bot, ctx, character, chunk)

            if not g.is_dev_channel(ctx.channel):
                await player.update_post_stats(self.bot, character, ctx.message, content=chunk)

                if len(chunk) >= ACTIVITY_POINT_MINIMUM:
                    await update_activity_points(self.bot, player, g)

                
    @character_admin_commands.command(
        name="manage",
        description="Manage a players character(s)"
    )
    async def character_manage(self, ctx: ApplicationContext,
                               member: Option(discord.SlashCommandOptionType(6), description="Player", required=True)):
        
        player = await get_player(self.bot, member.id, ctx.guild.id)
        g = await get_guild(self.bot, ctx.guild.id)
        

        ui = CharacterManageUI.new(self.bot, ctx.author, player, g)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="get",
        description="Displays character information for a player's character"
    )
    async def character_get(self, ctx: ApplicationContext,
                            member: Option(discord.SlashCommandOptionType(6), description="Player to get the information of",
                                           required=False)):
        await ctx.defer()

        member = member or ctx.author
        player = await get_player(self.bot, member.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if len(player.characters) == 0:
            return await ctx.respond(embed=PlayerOverviewEmbed(player, g, self.bot.compendium))


        ui = CharacterGetUI.new(self.bot, ctx.author, player, g)
        await ui.send_to(ctx)
        await ctx.delete()
    
    @commands.slash_command(
            name="settings",
            description="Character settings",
            guild_only=True
    )
    async def character_settings(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        ui = CharacterSettingsUI.new(self.bot, ctx.author, player, g)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
            name="rp_request",
            description="RP Board Request",
    )
    async def rp_request(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if not player.characters:
            raise CharacterNotFound(player.member)
        
        ui = RPPostUI.new(self.bot, ctx.author, player)
        await ui.send_to(ctx)
        await ctx.delete()
        

    @commands.slash_command(
        name="level_request",
        description="Level Request"
    )
    async def character_level_request(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if not player.characters:
            raise CharacterNotFound(player.member)
        elif len(player.characters) == 1:
            if player.characters[0].level >= g.max_level:
                raise G0T0Error("Character is already at max level for the server")
            modal = LevelUpRequestModal(g, player.characters[0])
            return await ctx.send_modal(modal)
        else:
            ui = CharacterSelectUI.new(self.bot, ctx.author, player, True)
            await ui.send_to(ctx)
            await ctx.delete()

    @commands.slash_command(
        name="new_character_request",
        description="New Character Request"
    )
    async def new_character_request(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None, False, ctx)
        application_text = await get_cached_application(self.bot.db, player.id)
        application = None

        if application_text:
            application = await get_new_character_application(self.bot, application_text)

        if player.characters:
            ui = CharacterSelectUI.new(self.bot, ctx.author, player, False, application)
        else:
            ui = NewCharacterRequestUI.new(self.bot, ctx.author, player, False, application)

        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="edit_application",
        description="Edit an application"
    )
    async def edit_application(self, ctx: ApplicationContext,
                               application_id: Option(str, description="Application ID", required=False)):
        guild = await get_guild(self.bot, ctx.guild.id)
        
        if guild.application_channel:
            if application_id:
                try:
                    message = await guild.application_channel.fetch_message(int(application_id))
                except ValueError:
                    raise G0T0Error("Invalid application identifier")
                except discord.errors.NotFound:
                    raise ApplicationNotFound()
            else:
                try:
                    message = await guild.application_channel.fetch_message(ctx.channel.id)
                except:
                    raise ApplicationNotFound()
        

        emoji = [x.emoji.name if hasattr(x.emoji, 'name') else x.emoji for x in message.reactions]
        if '✅' in emoji or 'greencheck' in emoji:
            raise G0T0Error("Application is already approved. Cannot edit at this time")
        elif '❌' in emoji:
            raise G0T0Error("Application marked as invalid and cannot me modified")
        
        appliation_text = message.content
        player_match = re.search(r"^\*\*Player:\*\* (.+)", appliation_text, re.MULTILINE)
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)
        type_match = re.search(r"^\*\*(.*?)\*\*\s\|", appliation_text, re.MULTILINE)
        type = type_match.group(1).strip().replace('*', '') if type_match else None

        if player_match and str(ctx.author.id) in player_match.group(1):
            if type and type in ["New Character", "Reroll", "Free Reroll"]:
                application = await get_new_character_application(self.bot, None, message)

                if player.characters:
                    ui = CharacterSelectUI.new(self.bot, ctx.author, player, False, application, True)
                else:
                    ui = NewCharacterRequestUI.new(self.bot, ctx.author, player, False, application)
                
                await ui.send_to(ctx)
                await ctx.delete()

            elif type and type == "Level Up":
                application = await get_level_up_application(self.bot, None, message)

                if not player.characters:
                    raise CharacterNotFound(player.member)
                elif len(player.characters) == 1:
                    modal = LevelUpRequestModal(guild, player.characters[0], application)
                    return await ctx.send_modal(modal)
                else:
                    ui = CharacterSelectUI.new(self.bot, ctx.author, player, True, application, True)
                    await ui.send_to(ctx)
                    await ctx.delete()
            
            else:
                raise G0T0Error("Unsure what type of application this is")
        else:
            raise G0T0Error("Not your application")
