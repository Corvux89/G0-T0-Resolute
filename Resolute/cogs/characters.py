import binascii
import datetime
import logging
import random
import string
import time
from timeit import default_timer as timer
from typing import List

from discord import SlashCommandGroup, Option, ApplicationContext, Member, Embed, Color
from discord.ext import commands
from Resolute.bot import G0T0Bot
from Resolute.constants import THUMBNAIL
from Resolute.helpers import manage_player_roles, get_character_quests, get_character, get_player_character_class, \
    create_logs, get_level_cap, get_or_create_guild, confirm, is_admin, get_player_starships, \
    get_player_starship_from_transponder, get_character_from_char_id, get_discord_player
from Resolute.helpers.autocomplete_helpers import *
from Resolute.models.db_objects import PlayerCharacter, PlayerCharacterClass, DBLog, LevelCaps, PlayerGuild, \
    CharacterStarship, DiscordPlayer
from Resolute.models.embeds import ErrorEmbed, NewCharacterEmbed, CharacterGetEmbed
from Resolute.models.schemas import CharacterSchema, CharacterStarshipSchema
from Resolute.queries import insert_new_character, insert_new_class, update_character, update_class, \
    insert_new_starship, update_starship

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
        name="create",
        description="Create a character"
    )
    async def character_create(self, ctx: ApplicationContext,
                               player: Option(Member, description="Character's player", required=True),
                               name: Option(str, description="Character's name", required=True),
                               character_class: Option(str, description="Character's initial class",
                                                       autocomplete=character_class_autocomplete,
                                                       required=True),
                               character_species: Option(str, description="Character's species",
                                                         autocomplete=character_species_autocomplete,
                                                         required=True),
                               credits: Option(int, description="Unspent starting credits", min=0, max=99999,
                                               required=True),
                               character_archetype: Option(str, description="Character's archetype",
                                                           autocomplete=character_archetype_autocomplete,
                                                           required=False),
                               cc: Option(int, description="Any starting Chain Codes", min=0, max=99999, required=False,
                                          default=0),
                               level: Option(int, description="Starting level for higher-level character", min_value=1,
                                             max_value=20, default=1)):
        """
        Creates a new character for a player

        :param ctx: Context
        :param player: Member
        :param name: Name of the PlayerCharacter
        :param character_class: CharacterClass
        :param character_species: CharacterSpecies
        :param gold: Starting gold
        :param character_subrace: CharacterSubrace
        :param character_subclass: CharacterArchetype
        :param level: Starting level if starting higher than 1
        """
        start = timer()
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is not None:
            return await ctx.respond(embed=ErrorEmbed(description=f"Player {player.mention} already has a character. "
                                                                  f"Have a council member archive the old character "
                                                                  f"before creating a new one."), ephemeral=True)

        # Resolve inputs
        c_class = ctx.bot.compendium.get_object("c_character_class", character_class)
        c_species = ctx.bot.compendium.get_object("c_character_species", character_species)
        c_archetype = ctx.bot.compendium.get_object("c_character_archetype", character_archetype)

        # Create new object
        character = PlayerCharacter(player_id=player.id, guild_id=ctx.guild.id, name=name, species=c_species,
                                    cc=cc, credits=credits, div_cc=0, level=level, token=0,
                                    active=True, reroll=False)

        async with self.bot.db.acquire() as conn:
            results = await conn.execute(insert_new_character(character))
            row = await results.first()

        if row is None:
            log.error(f"CHARACTERS: Error writing character to DB for {ctx.guild.name} [ {ctx.guild_id} ]")
            return await ctx.respond(embed=ErrorEmbed(
                description=f"Something went wrong creating the character."),
                ephemeral=True)

        character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)

        player_class = PlayerCharacterClass(character_id=character.id, primary_class=c_class,
                                            archetype=c_archetype, active=True)

        async with self.bot.db.acquire() as conn:
            await conn.execute(insert_new_class(player_class))

        act = ctx.bot.compendium.get_object("c_activity", "BONUS")

        log_entry: DBLog = await create_logs(ctx, character, act, "Initial Log")

        await manage_player_roles(ctx, player, character, "Character created")
        end = timer()
        log.info(f"Time to create character: [ {end - start:.2f} ]s")
        return await ctx.respond(embed=NewCharacterEmbed(character, player, player_class, log_entry, ctx))

    @commands.slash_command(
        name="get",
        description="Displays character information for a player's character"
    )
    async def character_get(self, ctx: ApplicationContext,
                            player: Option(Member, description="Player to get the information of",
                                           required=False)):
        """
        Gets and creates an embed of character information

        :param ctx: Context
        :param player: Member
        """
        await ctx.defer()

        if player is None:
            player = ctx.author

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)
        p: DiscordPlayer = await  get_discord_player(ctx.bot, player.id, ctx.guild_id)
        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)
        handicap_active = True if g.handicap_cc and  p.handicap_amount < g.handicap_cc else False

        if character is None:
            return await ctx.respond(embed=ErrorEmbed(
                description=f"No character information found for {player.mention}"),
                ephemeral=True)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)
        ship_ary: List[CharacterStarship] = await get_player_starships(ctx.bot, character.id)

        caps: LevelCaps = get_level_cap(character, g, ctx.bot.compendium)

        if character.level < 3:
            character = await get_character_quests(ctx.bot, character)

        await ctx.respond(embed=CharacterGetEmbed(character, class_ary, caps, ctx, g, ship_ary, handicap_active ))

    @character_admin_commands.command(
        name="level",
        description="Manually levels a character that has completed their Level 1 or Level 2 quests"
    )
    async def character_level(self, ctx: ApplicationContext,
                              player: Option(Member, description="Player receiving the level bump", required=True)):
        """
        Manually levels a character once they've completed entry quests

        :param ctx: Context
        :param player: Member
        """

        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)
        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        if character.level < 3:
            character = await get_character_quests(ctx.bot, character)

            if character.needed_rps > character.completed_rps or character.needed_arenas > character.completed_arenas:
                return await ctx.respond(embed=ErrorEmbed(
                    description=f"{player.mention} has not completed their requirements to level up.\n"
                                f"Completed RPs: {character.completed_rps}/{character.needed_rps}\n"
                                f"Completed Arena Phases: {character.completed_arenas}/{character.needed_arenas}"),
                    ephemeral=True)
        elif character.level >= 9 and character.token < 1:
            return await ctx.respond(embed=ErrorEmbed(description="Player doesn't have the necessary leveling token"))
        elif character.level + 1 > g.max_level:
            return await ctx.respond(embed=ErrorEmbed(description="Player level cannot exceed server max level."))

        log.info(f"Leveling up character [ {character.id} ] with player id [ {player.id} ]. "
                 f"New level: [ {character.level + 1} ]")

        character.level += 1

        act = ctx.bot.compendium.get_object("c_activity", "LEVEL")
        if character.level >= 10:
            await create_logs(ctx, character, act, "Player level up", 0, 0, -1)
        else:
            await create_logs(ctx, character, act, "Player level up", 0, 0)

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_character(character))

        await manage_player_roles(ctx, player, character, "Level up")

        embed = Embed(title="Level up successful!",
                      description=f"{player.mention} is now level {character.level}",
                      color=Color.random())
        embed.set_thumbnail(url=player.display_avatar.url)

        await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="species",
        description="Set a characters species"
    )
    async def character_race(self, ctx: ApplicationContext,
                             player: Option(Member, description="Player to set the species for", required=True),
                             character_species: Option(str, description="Character's race",
                                                       autocomplete=character_species_autocomplete,
                                                       required=True)):
        """
        Sets a characters race/subrace

        :param ctx: Context
        :param player: Member
        :param character_species: CharacterSpecies
        :param character_subrace: CharacterSubrace
        """

        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        c_species = ctx.bot.compendium.get_object("c_character_species", character_species)

        character.species = c_species

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_character(character))

        embed = Embed(title="Update successful!",
                      description=f"{character.name}'s species updated to {character.species.value}",
                      color=Color.random())
        embed.set_thumbnail(url=player.display_avatar.url)

        await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="archetype",
        description="Sets the archetype for a given player and class"
    )
    async def character_subclass(self, ctx: ApplicationContext,
                                 player: Option(Member, description="Player to set the class/archetype for",
                                                required=True),
                                 character_class: Option(str, description="Character's class to modify",
                                                         autocomplete=character_class_autocomplete,
                                                         required=True),
                                 character_archetype: Option(str, description="Character's archetype",
                                                             autocomplete=character_archetype_autocomplete,
                                                             required=False)):
        """
        Given a player and class, will update the subclass

        :param ctx: Context
        :param player: Member
        :param character_class: CharacterClass
        :param character_archetype: CharacterArchetype
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        c_class = ctx.bot.compendium.get_object("c_character_class", character_class)
        c_archetype = ctx.bot.compendium.get_object("c_character_archetype", character_archetype)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)

        for c in class_ary:
            if c.primary_class.id == c_class.id:
                c.archetype = c_archetype

                async with ctx.bot.db.acquire() as conn:
                    await conn.execute(update_class(c))

                embed = Embed(title="Update successful!",
                              description=f"{character.name} is class(es) updated to",
                              color=Color.random())
                embed.description += f"\n".join([f" {c.get_formatted_class()}" for c in class_ary])
                embed.set_thumbnail(url=player.display_avatar.url)

                return await ctx.respond(embed=embed)

        await ctx.respond(embed=ErrorEmbed(description=f"{character.name} doesn't have a {c_class.value} class"))

    @character_admin_commands.command(
        name="add_multiclass",
        description="Adds a multiclass to a player"
    )
    async def character_multiclass_add(self, ctx: ApplicationContext,
                                       player: Option(Member, description="Player to set the class/archetype for",
                                                      required=True),
                                       character_class: Option(str, description="Character's class to modify",
                                                               autocomplete=character_class_autocomplete,
                                                               required=True),
                                       character_archetype: Option(str, description="Character's archetype",
                                                                   autocomplete=character_archetype_autocomplete,
                                                                   required=False)):
        """
        Adds a new class to a player

        :param ctx: Context
        :param player: Member
        :param character_class: CharacterClass
        :param character_archetype: CharacterArchetype
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        c_class = ctx.bot.compendium.get_object("c_character_class", character_class)
        c_archetype = ctx.bot.compendium.get_object("c_character_archetype", character_archetype)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)

        if c_class.id in list(c.primary_class.id for c in class_ary):
            return await ctx.respond(
                embed=ErrorEmbed(description=f"Character already has class {c_class.value}"),
                ephemeral=True)
        elif len(class_ary) + 1 > character.level:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"Can't add more classes than the player has levels"),
                ephemeral=True)
        else:
            new_class = PlayerCharacterClass(character_id=character.id, primary_class=c_class, archetype=c_archetype,
                                             active=True)

            async with ctx.bot.db.acquire() as conn:
                await conn.execute(insert_new_class(new_class))

            class_ary.append(new_class)

            embed = Embed(title="Update successful!",
                          description=f"{character.name} classes updated to",
                          color=Color.random())
            embed.description += f"\n".join([f" {c.get_formatted_class()}" for c in class_ary])
            embed.set_thumbnail(url=player.display_avatar.url)

            return await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="remove_multiclass",
        description="Removes a class from a player"
    )
    async def character_multiclass_remove(self, ctx: ApplicationContext,
                                          player: Option(Member, description="Player to set the class/archetype for",
                                                         required=True),
                                          character_class: Option(str, description="Character's class to modify",
                                                                  autocomplete=character_class_autocomplete,
                                                                  required=True)):
        """
        Removes a multiclass from a player

        :param ctx: Context
        :param player: Member
        :param character_class: CharacterClass
        """
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        c_class = ctx.bot.compendium.get_object("c_character_class", character_class)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)

        if len(class_ary) == 1:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"Character only has one class."),
                ephemeral=True)
        elif c_class.id not in list(c.primary_class.id for c in class_ary):
            return await ctx.respond(
                embed=ErrorEmbed(description=f"Character doesn't have class {c_class.value}"),
                ephemeral=True)
        else:
            for char_class in class_ary:

                if char_class.primary_class.id == c_class.id:
                    char_class.active = False
                    class_ary.remove(char_class)
                    async with ctx.bot.db.acquire() as conn:
                        await conn.execute(update_class(char_class))

            embed = Embed(title="Update successful!",
                          description=f"{character.name} classes updated to",
                          color=Color.random())
            embed.description += f"\n".join([f" {c.get_formatted_class()}" for c in class_ary])
            embed.set_thumbnail(url=player.display_avatar.url)

            return await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="inactivate",
        description="Marks a character as inactive on the server."
    )
    @commands.check(is_admin)
    async def character_inactivate(self, ctx: ApplicationContext,
                                   player: Option(Member, description="Player to inactivate character for.",
                                                  required=True)):
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        conf = await confirm(ctx, f"Are you sure you want to inactivate `{character.name}` for {player.mention}? "
                                  f"(Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not conf:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)

        character.active = False

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_character(character))

        await ctx.respond(f"Character inactivated")


    @character_admin_commands.command(
        name="add_ship",
        description="Adds a starship to a player"
    )
    async def character_add_ship(self, ctx: ApplicationContext,
                                 player: Option(Member, description="Starship Owner", required=True),
                                 ship_size: Option(str, description="Ship Size", required=True,
                                                   autocomplete=starship_size_autocomplete),
                                 ship_role: Option(str, description="Ship Role", required=True,
                                                   autocomplete=starship_role_autocomplete),
                                 ship_name: Option(str, description="Ship Name", required=True),
                                 tier: Option(int, description="Ship Tier", required=False, default=0,
                                              min_value=0, max_value=5)):
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        s_role = ctx.bot.compendium.get_object("c_starship_role", ship_role)
        s_size = ctx.bot.compendium.get_object("c_starship_size", ship_size)

        if s_role is None:
            return await ctx.respond(embed=ErrorEmbed(description="Invalid starship model"), ephemeral=True)
        elif s_role.size != s_size.id:
            return await ctx.respond(embed=ErrorEmbed(description="Invalid role for starship size"), ephemeral=True)

        c_starship: CharacterStarship = CharacterStarship(character_id=[character.id], name=ship_name, starship=s_role,
                                                          tier=tier)

        async with ctx.bot.db.acquire() as conn:
            results = await conn.execute(insert_new_starship(c_starship))
            row = await results.first()

        if row is None:
            log.error(f"CHARACTERS: Error writing Starship to DB for {ctx.guild.name} [ {ctx.guild_id} ]")
            return await ctx.respond(embed=ErrorEmbed(
                description=f"Something went wrong creating the starship."),
                ephemeral=True)

        c_starship: CharacterStarship = CharacterStarshipSchema(ctx.bot.compendium).load(row)

        base_str = ship_name[:4]

        if len(base_str) < 4:
            base_str += "".join(random.choices(string.ascii_letters, k=(4 - len(base_str))))

        base_str = binascii.hexlify(bytes(base_str, encoding='utf-8'))
        base_str = base_str.decode("utf-8")

        c_starship.transponder = f"{c_starship.starship.get_size(ctx.bot.compendium).value[:1]}{c_starship.starship.value[:1]}{str(time.time())[:5]}_{base_str}_BD:{c_starship.id}"

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_starship(c_starship))

        embed = Embed(title="Update successful!",
                      description=f"{character.name} new starship:\n{c_starship.get_formatted_starship(ctx.bot.compendium)}",
                      color=Color.random())
        embed.set_thumbnail(url=player.display_avatar.url)

        return await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="upgrade_ship",
        description="Upgrades a ship tier"
    )
    async def character_upgrade_ship(self, ctx: ApplicationContext,
                                     transponder_code: Option(str, description="Ship transponder", required=True),
                                     tier: Option(int, description="New tier for the ship", required=True,
                                                  min_value=0, max_value=5)):
        await ctx.defer()

        c_ship: CharacterStarship = await get_player_starship_from_transponder(ctx.bot, transponder_code)

        if c_ship is None:
            return await ctx.respond(embed=ErrorEmbed(description="Ship not found"), ephemeral=True)

        players = []
        for c in c_ship.character_id:
            character: PlayerCharacter = await get_character_from_char_id(ctx.bot, c)
            if character is None:
                log.error(f"STARSHIP: Error with {c_ship.transponder} owner ID {c} not found on server")
            elif character.guild_id != ctx.guild_id:
                return ctx.respond(embed=ErrorEmbed(description=f"Invalid ship/players"))
            else:
                players.append(character)


        if len(players) == 0:
            return await ctx.respond(embed=ErrorEmbed(
                description=f"No active owners found for this ship."),
            ephemeral=True)

        c_ship.tier = tier

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_starship(c_ship))

        embed = Embed(title="Update successful!",
                      description=f"Updated starship:\n{c_ship.get_formatted_starship(ctx.bot.compendium)}",
                      color=Color.random())
        embed.set_thumbnail(url=THUMBNAIL)
        embed.add_field(name="Owners",
                        value=f"\n".join([f"\u200b \u200b \u200b {c.get_member_mention(ctx)}" for c in players]))

        return await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="remove_ship",
        description="Inactivates a ship"
    )
    async def character_upgrade_ship(self, ctx: ApplicationContext,
                                     transponder_code: Option(str, description="Ship transponder", required=True)):
        await ctx.defer()

        c_ship: CharacterStarship = await get_player_starship_from_transponder(ctx.bot, transponder_code)

        if c_ship is None:
            return await ctx.respond(embed=ErrorEmbed(description="Ship not found"), ephemeral=True)

        players = []
        for c in c_ship.character_id:
            character: PlayerCharacter = await get_character_from_char_id(ctx.bot, c)
            if character is None:
                log.error(f"STARSHIP: Error with {c_ship.transponder} owner ID {c} not found on server")
            elif character.guild_id != ctx.guild_id:
                return await ctx.respond(embed=ErrorEmbed(description=f"Invalid ship/players"))
            else:
                players.append(character)

        if len(players) == 0:
            return await ctx.respond(embed=ErrorEmbed(
                description=f"No active owners found for this ship."),
                ephemeral=True)
        elif len(players) == 1:
            p_str = players[0].get_member_mention(ctx)
        else:
            p_str = '{}, and {}'.format(', '.join([f'{p.get_member_mention(ctx)}' for p in players[:-1]]),players[-1].get_member_mention(ctx))

        conf = await confirm(ctx, f"Are you sure you want to inactivate `{c_ship.name} (Tier {c_ship.tier})` for "
                                  f"{p_str}? "
                                  f"(Reply with yes/no)", True)

        if conf is None:
            return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
        elif not conf:
            return await ctx.respond(f'Ok, cancelling.', delete_after=10)

        c_ship.active = False

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_starship(c_ship))

        embed = Embed(title="Removal successful!",
                      description=f"{character.name} removed starship:\n{c_ship.get_formatted_starship(ctx.bot.compendium)}",
                      color=Color.random())
        embed.set_thumbnail(url=character.get_member(ctx).display_avatar.url)

        return await ctx.respond(embed=embed)

    @character_admin_commands.command(
        name="modify_ship_captain",
        description="Adds/removes a captain to a ship"
    )
    async def character_add_ship_captain(self, ctx: ApplicationContext,
                                         transponder_code: Option(str, description="Ship transponder", required=True),
                                         player: Option(Member,description="Player to add/remove", required=True),
                                         mod_type: Option(str, description="Modification type",
                                                          choices=["Add", "Remove"], default="Add", required=False)):

        await ctx.defer()

        c_ship: CharacterStarship = await get_player_starship_from_transponder(ctx.bot, transponder_code)

        if c_ship is None:
            return await ctx.respond(embed=ErrorEmbed(description="Ship not found"), ephemeral=True)

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        if mod_type.lower() == 'add':
            if character.id in c_ship.character_id:
                return await ctx.respond(embed=ErrorEmbed(description=f"Player already listed as a ship owner"),
                                   ephemeral=True)
            else:
                c_ship.character_id.append(character.id)
        elif mod_type.lower() == 'remove':
            if character.id not in c_ship.character_id:
                return await ctx.respond(embed=ErrorEmbed(description=f"Player not listed as a ship owner"),
                                   ephemeral=True)
            else:
                c_ship.character_id.remove(character.id)
        else:
            return await ctx.respond(embed=ErrorEmbed(description=f"I don't know what you want. Either add or remove them..."),
                               ephemeral=True)

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_starship(c_ship))

        players = []
        for c in c_ship.character_id:
            character: PlayerCharacter = await get_character_from_char_id(ctx.bot, c)
            if character is None:
                log.error(f"STARSHIP: Error with {c_ship.transponder} owner ID {c} not found on server")
            elif character.guild_id != ctx.guild_id:
                return await ctx.respond(embed=ErrorEmbed(description=f"Invalid ship/players"))
            else:
                players.append(character)

        if len(players) == 0:
            return await ctx.respond(embed=ErrorEmbed(
                description=f"No active owners found for this ship."),
                ephemeral=True)

        embed = Embed(title="Update successful!",
                      description=f"Updated starship:\n{c_ship.get_formatted_starship(ctx.bot.compendium)}",
                      color=Color.random())
        embed.set_thumbnail(url=THUMBNAIL)
        embed.add_field(name="Owners",
                        value=f"\n".join([f"\u200b \u200b \u200b {c.get_member_mention(ctx)}" for c in players]))

        return await ctx.respond(embed=embed)
        


    @character_admin_commands.command(
        name="reroll",
        description="Reroll's a character"
    )
    async def character_reroll(self, ctx: ApplicationContext,
                               player: Option(Member, description="Player rerolling.", required=True),
                               name: Option(str, description="Character's name", required=True),
                               character_class: Option(str, description="Character's initial class",
                                                       autocomplete=character_class_autocomplete,
                                                       required=True),
                               character_species: Option(str, description="Character's race",
                                                         autocomplete=character_species_autocomplete,
                                                         required=True),
                               credits: Option(int, description="New credit amount. If unspecified will copy old gold",
                                            min=0, max=99999, required=False),
                               cc: Option(int, description="New chain code amount. If unspecified will copy old CC",
                                          min=0, max=999999, required=False),
                               character_archetype: Option(str, description="Character's archetype",
                                                          autocomplete=character_archetype_autocomplete,
                                                          required=False),
                               level: Option(int, description="Level for the new character. Default is their old level",
                                             min_value=1, max_value=20, required=False)):
        start = timer()
        await ctx.defer()

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)
        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        if character is None:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
                ephemeral=True)

        # Resolve inputs
        c_class = ctx.bot.compendium.get_object("c_character_class", character_class)
        c_species = ctx.bot.compendium.get_object("c_character_species", character_species)
        c_archetype = ctx.bot.compendium.get_object("c_character_archetype", character_archetype)

        if not c_class:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No information found for class {character_class}"),
                ephemeral=True)
        elif not c_species:
            return await ctx.respond(
                embed=ErrorEmbed(description=f"No information found for species {character_species}"),
                ephemeral=True)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)
        ship_ary: List[CharacterStarship] = await get_player_starships(ctx.bot, character.id)

        new_character = PlayerCharacter(player_id=player.id, guild_id=ctx.guild_id, name=name, species=c_species,
                                        cc=character.cc if not cc else cc,
                                        credits=character.credits if not credits else credits,
                                        div_cc=character.div_cc, level=character.level if not level else level,
                                        token=0, reroll=True, active=True)

        # Update old character:
        character.active = False

        async with self.bot.db.acquire() as conn:
            await conn.execute(update_character(character))
            results = await conn.execute(insert_new_character(new_character))
            row = await results.first()

        if row is None:
            log.error(f"CHARACTERS: Error writing character to DB for {ctx.guild.name} [ {ctx.guild_id} ]")
            return await ctx.respond(embed=ErrorEmbed(
                description=f"Something went wrong creating the character."),
                ephemeral=True)

        new_character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)

        # Character Class
        new_class = PlayerCharacterClass(character_id=new_character.id, primary_class=c_class,
                                         archetype=c_archetype, active=True)
        for c in class_ary:
            c.active = False

        async  with self.bot.db.acquire() as conn:
            for c in class_ary:
                await conn.execute(update_class(c))

            await conn.execute(insert_new_class(new_class))

        # Starships
        if ship_ary:
            for s in ship_ary:
                s.active = False

            async with self.bot.db.acquire() as conn:
                for s in ship_ary:
                    await conn.execute(update_starship(s))

        # Inital Log
        act = ctx.bot.compendium.get_object("c_activity", "BONUS")

        log_entry: DBLog = await create_logs(ctx, new_character, act, "Inital log for character reroll")

        end = timer()
        log.info(f'Time to reroll character": [ {end - start:.2f} ]s')

        return await ctx.respond(embed=NewCharacterEmbed(new_character, player, new_class, log_entry, ctx))
    #
    #
    #
    #
    #
    #
    # # @character_admin_commands.command(
    # #     name="resurrect",
    # #     description="Logs a resurrection for a character"
    # # )
    # async def character_resurrect(self, ctx: ApplicationContext,
    #                               player: Option(Member, description="Player being resurrected", required=True),
    #                               cost: Option(int, description="Any cost associated to be deducted", required=False,
    #                               min_value=0, default=0)):
    #
    #     await ctx.defer()
    #
    #     character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)
    #
    #     if character is None:
    #         return await ctx.respond(
    #             embed=ErrorEmbed(description=f"No character information found for {player.mention}"),
    #             ephemeral=True)
    #
    #     if character.gold < cost:
    #         return await ctx.respond(embed=ErrorEmbed(description=f"{player.mention} cannot afford the {cost}gp cost"))
    #
    #     xp = -1000 if character.xp - 1000 >= 0 else 0
    #
    #     act = ctx.bot.compendium.get_object("c_activity", "BONUS")
    #
    #     log_entry = await create_logs(ctx, character, act, "Character Resurrection", cost, xp)
    #
    #     embed = Embed(title=f"Resurrection of {character.name} successful!",
    #                   color=Color.random())
    #     embed.set_thumbnail(url=player.display_avatar.url)
    #     embed.set_footer(text=f"Logged by {ctx.author} - ID: {log_entry.id}",
    #                     icon_url=ctx.author.display_avatar.url)
    #
    #     await ctx.respond(embed=embed)
