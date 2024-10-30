import logging
import re
import discord

from discord import SlashCommandGroup, Option, ApplicationContext
from discord.ext import commands

from Resolute.bot import G0T0Bot
from Resolute.helpers.appliations import get_cached_application, get_level_up_application, get_new_character_application
from Resolute.helpers.characters import get_webhook_character
from Resolute.helpers.general_helpers import get_webhook
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.objects.players import upsert_player_query
from Resolute.models.views.applications import CharacterSelectUI, LevelUpRequestModal, NewCharacterRequestUI
from Resolute.models.views.character_view import CharacterManageUI, CharacterSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Character(bot))


class Character(commands.Cog):
    # TODO: Renown in character Manage for admins
    bot: G0T0Bot
    character_admin_commands = SlashCommandGroup("character_admin", "Character administration commands", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Characters\' loaded')    

    @commands.command(
        name="say",
        guild_only=True
    )
    async def character_say(self, ctx: ApplicationContext, char_name: str = None):

        content = ctx.message.content

        content = content.replace(f">say ", "")
        await ctx.message.delete()

        if content == "":
            return
        
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id)
        g = await get_guild(self.bot, ctx.guild.id)

        if not player.characters:
            return await ctx.send(embed=ErrorEmbed("You do not have any characters"), ephemeral=True)

        character = await get_webhook_character(self.bot, player, ctx.channel)
        webhook = await get_webhook(ctx.channel)
        await webhook.send(username=f"[{character.level}] {character.name} // {ctx.author.display_name}",
                        avatar_url=ctx.author.display_avatar.url if not character.avatar_url else character.avatar_url,
                        content=f"{content}")
        await player.update_post_stats(self.bot, character, content)

        # Activity Point Tracking
        player.activity_points += 1
        activity_point = None
        for point in self.bot.compendium.activity_points[0].values():
            if player.activity_points >= point.points:
                activity_point = point
            elif player.activity_points < point.points:
                break
        
        if activity_point and player.activity_level < activity_point.id and (activity := self.bot.compendium.get_activity("ACTIVITY_REWARD")):
            player.activity_level = activity_point.id
            guild = await get_guild(self.bot, ctx.guild.id)
            act_log = await create_log(self.bot, self.bot.user, guild, activity, player, 
                                       notes=f"Activity level {player.activity_level}")
            if guild.market_channel:
                await guild.market_channel.send(embed=LogEmbed(act_log, self.bot.user, player.member), content=f"{ctx.author.mention}")
        else:
            async with self.bot.db.acquire() as conn:
                await conn.execute(upsert_player_query(player))

                
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

        return await ctx.respond(embed=PlayerOverviewEmbed(player, g, self.bot.compendium))
    
    @commands.slash_command(
            name="settings",
            description="Character settings",
            guild_only=True
    )
    async def character_settings(self, ctx: ApplicationContext):
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
        g = await get_guild(self.bot, player.guild_id)

        if not player.characters:
            return await ctx.respond(embed=ErrorEmbed("You do not have any characters"), ephemeral=True)
        
        ui = CharacterSettingsUI.new(self.bot, ctx.author, player, g)
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
            return await ctx.respond(embed=ErrorEmbed("You do not have any characters to level up"), ephemeral=True)
        elif len(player.characters) == 1:
            if player.characters[0].level >= g.max_level:
                return await ctx.respond(embed=ErrorEmbed("Character is already at max level for the server"), ephemeral=True)
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
        player = await get_player(self.bot, ctx.author.id, ctx.guild.id if ctx.guild else None)
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
        
        if guild.character_application_channel:
            if application_id:
                try:
                    message = await guild.character_application_channel.fetch_message(int(application_id))
                except ValueError:
                    return await ctx.respond(embed=ErrorEmbed("Invalid application identifier"), ephemeral=True)
                except discord.errors.NotFound:
                    return await ctx.respond(embed=ErrorEmbed("Application not found"), ephemeral=True)
            else:
                try:
                    message = await guild.character_application_channel.fetch_message(ctx.channel.id)
                except:
                    return await ctx.respond(embed=ErrorEmbed("Application not found"), ephemeral=True)
        

        emoji = [x.emoji.name if hasattr(x.emoji, 'name') else x.emoji for x in message.reactions]
        if '✅' in emoji or 'greencheck' in emoji:
            return await ctx.respond(embed=ErrorEmbed("Application is already approved. Cannot edit at this time"), ephemeral=True)
        elif '❌' in emoji:
            return await ctx.respond(embed=ErrorEmbed("Application marked as invalid and cannot me modified"), ephemeral=True)
        
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
                    return await ctx.respond(embed=ErrorEmbed("You do not have any characters to level up"), ephemeral=True)
                elif len(player.characters) == 1:
                    modal = LevelUpRequestModal(g, player.characters[0], application)
                    return await ctx.send_modal(modal)
                else:
                    ui = CharacterSelectUI.new(self.bot, ctx.author, player, True, application, True)
                    await ui.send_to(ctx)
                    await ctx.delete()
            
            else:
                return await ctx.respond(embed=ErrorEmbed("Unsure what type of application this is"), ephemeral=True)
        else:
            return await ctx.respond(embed=ErrorEmbed("Not your application"), ephemeral=True)
