import logging
from timeit import default_timer as timer
from typing import List

from discord import SlashCommandGroup, Option, ApplicationContext, Member, Embed, Color
from discord.ext import commands
from Resolute.bot import G0T0Bot
from Resolute.constants import THUMBNAIL
from Resolute.helpers.guilds import get_guild
from Resolute.helpers.players import get_player
from Resolute.models.embeds.players import PlayerOverviewEmbed
from Resolute.models.views.character_view import CharacterSettingsUI

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Character(bot))


class Character(commands.Cog):
    bot: G0T0Bot
    character_admin_commands = SlashCommandGroup("character_admin", "Character administration commands")

    def __init__(self, bot):
        self.bot = bot
        log.info(f'Cog \'Characters\' loaded')

    @character_admin_commands.command(
        name="manage",
        description="Manage a players character(s)"
    )
    async def character_manage(self, ctx: ApplicationContext,
                               member: Option(Member, description="Player", required=True)):
        
        player = await get_player(self.bot, member.id, ctx.guild.id)
        g = await get_guild(self.bot.db, ctx.guild.id)
        

        ui = CharacterSettingsUI.new(self.bot, ctx.author, member, player, g, ctx.guild)
        await ui.send_to(ctx)
        await ctx.delete()

    @commands.slash_command(
        name="get",
        description="Displays character information for a player's character"
    )
    async def character_get(self, ctx: ApplicationContext,
                            member: Option(Member, description="Player to get the information of",
                                           required=False)):
        await ctx.defer()

        member = member or ctx.author
        g = await get_guild(self.bot.db, ctx.guild.id)
        player = await get_player(self.bot, member.id, ctx.guild.id)

        return await ctx.respond(embed=PlayerOverviewEmbed(player, member, g, self.bot.compendium))

    #     base_str = ship_name[:4]

    #     if len(base_str) < 4:
    #         base_str += "".join(random.choices(string.ascii_letters, k=(4 - len(base_str))))

    #     base_str = binascii.hexlify(bytes(base_str, encoding='utf-8'))
    #     base_str = base_str.decode("utf-8")

    #     c_starship.transponder = f"{c_starship.starship.get_size(ctx.bot.compendium).value[:1]}{c_starship.starship.value[:1]}{str(time.time())[:5]}_{base_str}_BD:{c_starship.id}"

    #     async with ctx.bot.db.acquire() as conn:
    #         await conn.execute(update_starship(c_starship))

    #     embed = Embed(title="Update successful!",
    #                   description=f"{character.name} new starship:\n{c_starship.get_formatted_starship(ctx.bot.compendium)}",
    #                   color=Color.random())
    #     embed.set_thumbnail(url=player.display_avatar.url)

    #     return await ctx.respond(embed=embed)

  
    # @character_admin_commands.command(
    #     name="remove_ship",
    #     description="Inactivates a ship"
    # )
    # async def character_upgrade_ship(self, ctx: ApplicationContext,
    #                                  transponder_code: Option(str, description="Ship transponder", required=True)):
    #     await ctx.defer()

    #     c_ship: CharacterStarship = await get_player_starship_from_transponder(ctx.bot, transponder_code)

    #     if c_ship is None:
    #         return await ctx.respond(embed=ErrorEmbed(description="Ship not found"), ephemeral=True)

    #     players = []
    #     for c in c_ship.character_id:
    #         character: PlayerCharacter = await get_character_from_char_id(ctx.bot, c)
    #         if character is None:
    #             log.error(f"STARSHIP: Error with {c_ship.transponder} owner ID {c} not found on server")
    #         elif character.guild_id != ctx.guild_id:
    #             return await ctx.respond(embed=ErrorEmbed(description=f"Invalid ship/players"))
    #         else:
    #             players.append(character)

    #     if len(players) == 0:
    #         return await ctx.respond(embed=ErrorEmbed(
    #             description=f"No active owners found for this ship."),
    #             ephemeral=True)
    #     elif len(players) == 1:
    #         p_str = players[0].get_member_mention(ctx)
    #     else:
    #         p_str = '{}, and {}'.format(', '.join([f'{p.get_member_mention(ctx)}' for p in players[:-1]]),players[-1].get_member_mention(ctx))

    #     conf = await confirm(ctx, f"Are you sure you want to inactivate `{c_ship.name} (Tier {c_ship.tier})` for "
    #                               f"{p_str}? "
    #                               f"(Reply with yes/no)", True)

    #     if conf is None:
    #         return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
    #     elif not conf:
    #         return await ctx.respond(f'Ok, cancelling.', delete_after=10)

    #     c_ship.active = False

    #     async with ctx.bot.db.acquire() as conn:
    #         await conn.execute(update_starship(c_ship))

    #     embed = Embed(title="Removal successful!",
    #                   description=f"{character.name} removed starship:\n{c_ship.get_formatted_starship(ctx.bot.compendium)}",
    #                   color=Color.random())
    #     embed.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

    #     return await ctx.respond(embed=embed)

    # @character_admin_commands.command(
    #     name="modify_ship_captain",
    #     description="Adds/removes a captain to a ship"
    # )
    # async def character_add_ship_captain(self, ctx: ApplicationContext,
    #                                      transponder_code: Option(str, description="Ship transponder", required=True),
    #                                      player: Option(Member,description="Player to add/remove", required=True),
    #                                      mod_type: Option(str, description="Modification type",
    #                                                       choices=["Add", "Remove"], default="Add", required=False)):

    #     await ctx.defer()

    #     c_ship: CharacterStarship = await get_player_starship_from_transponder(ctx.bot, transponder_code)

    #     if c_ship is None:
    #         return await ctx.respond(embed=ErrorEmbed(description="Ship not found"), ephemeral=True)

    #     character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

    #     if character is None:
    #         return await ctx.respond(
    #             embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
    #             ephemeral=True)

    #     if mod_type.lower() == 'add':
    #         if character.id in c_ship.character_id:
    #             return await ctx.respond(embed=ErrorEmbed(description=f"Player already listed as a ship owner"),
    #                                ephemeral=True)
    #         else:
    #             c_ship.character_id.append(character.id)
    #     elif mod_type.lower() == 'remove':
    #         if character.id not in c_ship.character_id:
    #             return await ctx.respond(embed=ErrorEmbed(description=f"Player not listed as a ship owner"),
    #                                ephemeral=True)
    #         else:
    #             c_ship.character_id.remove(character.id)
    #     else:
    #         return await ctx.respond(embed=ErrorEmbed(description=f"I don't know what you want. Either add or remove them..."),
    #                            ephemeral=True)

    #     async with ctx.bot.db.acquire() as conn:
    #         await conn.execute(update_starship(c_ship))

    #     players = []
    #     for c in c_ship.character_id:
    #         character: PlayerCharacter = await get_character_from_char_id(ctx.bot, c)
    #         if character is None:
    #             log.error(f"STARSHIP: Error with {c_ship.transponder} owner ID {c} not found on server")
    #         elif character.guild_id != ctx.guild_id:
    #             return await ctx.respond(embed=ErrorEmbed(description=f"Invalid ship/players"))
    #         else:
    #             players.append(character)

    #     if len(players) == 0:
    #         return await ctx.respond(embed=ErrorEmbed(
    #             description=f"No active owners found for this ship."),
    #             ephemeral=True)

    #     embed = Embed(title="Update successful!",
    #                   description=f"Updated starship:\n{c_ship.get_formatted_starship(ctx.bot.compendium)}",
    #                   color=Color.random())
    #     embed.set_thumbnail(url=THUMBNAIL)
    #     embed.add_field(name="Owners",
    #                     value=f"\n".join([f"\u200b \u200b \u200b {c.get_member_mention(ctx)}" for c in players]))

    #     return await ctx.respond(embed=embed)
        

    # @commands.slash_command(
    #     name="level_request",
    #     description="Level Request"
    # )
    # async def character_level_request(self, ctx:ApplicationContext):
    #     if character := await get_character(ctx.bot, ctx.author.id, ctx.guild_id):
    #         modal = LevelUpRequestView(ctx.author, character, LevelUpApplication())
    #         return await ctx.send_modal(modal)
    #     else:
    #         return await ctx.respond(f"You do not have a character to level up", ephemeral=True)

    # @commands.slash_command(
    #     name="new_character_request",
    #     description="New Character Request"
    # )
    # async def new_character_request(self, ctx:ApplicationContext,
    #                                 free_reroll: Option(bool, description="Free reroll application", required=False,
    #                                                     default=False)):
    #     character: PlayerCharacter = await get_character(ctx.bot, ctx.author.id, ctx.guild_id)
    #     app_text = await get_cached_application(ctx.bot, ctx.author.id)

    #     if app_text and get_application_type(app_text) == "New":
    #         application = get_new_character_application(None, app_text)
    #     else:
    #         application = NewCharacterApplication(freroll = free_reroll)

    #     ui = NewCharacterRequestUI.new(ctx.bot, ctx.author, character, application.freeroll, application)

    #     await ui.send_to(ctx)
    #     await ctx.delete()

    # @commands.slash_command(
    #     name="edit_application",
    #     description="Edit an application"
    # )
    # async def edit_application(self, ctx: ApplicationContext,
    #                        application_id: Option(str, description="Application ID", required=False)):
        
    #     if app_channel := discord.utils.get(ctx.guild.channels, name="character-apps"):
    #         if application_id:
    #             try:
    #                 message = await app_channel.fetch_message(int(application_id))
    #             except ValueError:
    #                 return await ctx.respond("Invalid application identifier", ephemeral=True)
    #             except discord.errors.NotFound:
    #                 return await ctx.respond("Application not found", ephemeral=True)
    #         else:
    #             try:
    #                 message = await app_channel.fetch_message(int(ctx.channel_id))
    #                 test = "here"
    #             except:
    #                 return await ctx.respond("Application not found", ephemeral=True)

    #     emoji = [x.emoji.name if hasattr(x.emoji, 'name') else x.emoji for x in message.reactions]
    #     if '✅' in emoji or 'greencheck' in emoji:
    #         return await ctx.respond("Application is already approved. Cannot edit at this time", ephemeral=True)
    #     elif '❌' in emoji:
    #         return await ctx.respond("Application marked as invalid and cannot me modified", ephemeral=True)

    #     app_text = message.content
    #     player_match = re.search(r"\*\*Player:\*\* (.+)", app_text)
    #     character: PlayerCharacter = await get_character(ctx.bot, ctx.author.id, ctx.guild_id)
    #     app_type = get_application_type(app_text)

    #     if player_match and str(ctx.author.id) in player_match.group(1):
    #         if app_type == "New":
    #             application: NewCharacterApplication = get_new_character_application(message)
    #             ui = NewCharacterRequestUI.new(ctx.bot, ctx.author, character,application.freeroll, application)
    #             await ui.send_to(ctx)
    #             return await ctx.delete()
    #         elif app_type == "Level":
    #             application: LevelUpApplication = get_level_up_application(message)
    #             modal = LevelUpRequestView(ctx.author, character, application)
    #             return await ctx.send_modal(modal)
    #         else:
    #             return await ctx.respond("Unsure what type of application this is", ephemeral=True)
    #     else:
    #         return await ctx.respond("Not your application", ephemeral=True)

    #     return await ctx.respond("Something went wrong", ephemeral=True)

