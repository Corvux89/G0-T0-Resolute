import logging
from datetime import datetime
from math import ceil
from typing import List

import discord
from discord import ApplicationContext, Option, SlashCommandGroup, Role, Member
from discord.ext import commands
from Resolute.bot import G0T0Bot
from Resolute.helpers import update_dm, get_adventure, get_character, get_adventure_from_role, is_admin, \
    get_player_adventures, get_player_character_class, confirm, create_logs, get_or_create_guild
from Resolute.models.db_objects import Adventure, PlayerCharacter, PlayerCharacterClass, Activity, PlayerGuild
from Resolute.models.embeds import AdventureCloseEmbed, ErrorEmbed, AdventureStatusEmbed, AdventuresEmbed, \
    AdventureRewardEmbed
from Resolute.models.schemas import CharacterSchema
from Resolute.queries import insert_new_adventure, update_adventure, get_multiple_characters

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Adventures(bot))

class Adventures(commands.Cog):
    bot: G0T0Bot  # Typing annotation for my IDE's sake
    adventure_commands = SlashCommandGroup("adventure", "Adventure commands")

    def __init__(self, bot):
        # Setting up some objects
        self.bot = bot

        log.info(f'Cog \'Adventures\' loaded')

    @commands.slash_command(
        name="adventures",
        description="Shows active adventures for a player"
    )
    async def adventure_get(self, ctx: ApplicationContext,
                            player: Option(Member, description="Player to get the information of", required=False),
                            phrase: Option(str, description="Additional question/phrase to add", required=False),
                            phrase2: Option(str, description="Additional question/phrase to add", required=False)):
        await ctx.defer()

        if player is None:
            player = ctx.author

        character: PlayerCharacter = await get_character(ctx.bot, player.id, ctx.guild_id)

        if character is None:
            return await ctx.respond(embed=ErrorEmbed(
                description=f"No character information found for {player.mention}"),
                ephemeral=True)

        class_ary: List[PlayerCharacterClass] = await get_player_character_class(ctx.bot, character.id)
        adventures = await get_player_adventures(ctx.bot, player)

        phrases = []
        if phrase:
            phrases.append(phrase)

        if phrase2:
            phrases.append(phrase2)

        return await ctx.respond(embed=AdventuresEmbed(ctx, character, class_ary, adventures, phrases))


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
                               dm: Option(discord.Member, description="The DM of the adventure. "
                                                                      "Multiple DM's can be added via the add_dm "
                                                                      "command", required=True)):
        """
        Creates a channel category and role for the adventure, as well as two private channels.

        :param ctx: Context
        :param adventure_name: The name of the adventure as it should show up in the category channel
        :param role_name: The name of the Role to be created for adventure participants
        :param dm: The DM of the adventure
        """
        await ctx.defer()

        # Create the role
        if discord.utils.get(ctx.guild.roles, name=role_name):
            return await ctx.respond(f"Error: role `@{role_name}` already exists")
        else:
            adventure_role = await ctx.guild.create_role(name=role_name, mentionable=True,
                                                         reason=f"Created by {ctx.author.nick} for adventure"
                                                                f"{adventure_name}")
            log.info(f"ADVENTURE: Role {adventure_role} created")

            # Setup role permissions
            category_permissions = dict()
            category_permissions[adventure_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
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
            ic_overwrites = category_permissions.copy()
            ooc_overwrites = category_permissions.copy()

            # Setup the questers
            if quester_role := discord.utils.get(ctx.guild.roles, name="Quester"):
                ic_overwrites[quester_role] = discord.PermissionOverwrite(
                    view_channel=True
                )
                ooc_overwrites[quester_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

            log.info('ADVENTURE: Done creating category permissions and OOC overwrites')

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

            async with ctx.bot.db.acquire() as conn:
                await conn.execute(insert_new_adventure(adventure))

            await ooc_channel.send(f"Adventure {adventure.name} successfully created!\n"
                                   f"Role: {adventure_role.mention}\n"
                                   f"IC Room: {ic_channel.mention}\n"
                                   f"OOC Room: {ooc_channel.mention}\n\n"
                                   f"{dm.mention} - Please ensure your permissions are correct in these rooms! "
                                   f"If so, you can start adding players with /adventure add")

            await ctx.delete()

    @adventure_create.error
    async def create_error(self, ctx, error):
        if isinstance(error, discord.Forbidden):
            await ctx.send(embed=ErrorEmbed(description='Error: Bot isn\'t allowed to do that (for some reason)'))
        elif isinstance(error, discord.HTTPException):
            await ctx.send(embed=ErrorEmbed(description='Error: Creating new role failed, please try again. '
                                                        'If the problem persists, contact the Council'))
        elif isinstance(error, discord.InvalidArgument):
            await ctx.send(embed=ErrorEmbed(description=f'Error: Invalid Argument {error}'))

    @adventure_commands.command(
        name="dm_add",
        description="Add a DM to an adventure. This command must be run in a channel of the adventure."
    )
    async def adventure_dm_add(self, ctx: ApplicationContext,
                               dm: Option(discord.Member, description="Player to add as a DM", required=True)):
        """
        Adds additional DM's to an existing adventure. This command must be run in a channel of the adventure
        they are being added to.

        :param ctx: Context
        :param dm: The DM to add to the adventure
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(embed=ErrorEmbed(description="No adventure associated with this channel"))
        elif dm.id in adventure.dms:
            return await ctx.respond(embed=ErrorEmbed(description="Error: Player already listed as a "
                                                                  "DM for this adventure"))
        elif ctx.author.id not in adventure.dms and not is_admin(ctx):
            return await ctx.respond(embed=ErrorEmbed(description="Error: You either need to be the DM for this "
                                                                  "adventure or Council to do this."))
        else:
            adventure.dms.append(dm.id)
            adventure_role = adventure.get_adventure_role(ctx)
            if adventure_role not in dm.roles:
                await dm.add_roles(adventure_role, reason=f"Creating adventure {adventure.name}")

            category = ctx.channel.category
            category_permissions = category.overwrites
            category_permissions[dm] = discord.PermissionOverwrite(manage_messages=True)

            await category.edit(overwrites=category_permissions)

            for c in category.channels:
                c_permissions = c.overwrites
                c_permissions[dm] = discord.PermissionOverwrite(manage_messages=True)
                await c.edit(overwrites=c_permissions)

            async with ctx.bot.db.acquire() as conn:
                await conn.execute(update_adventure(adventure))

        await ctx.respond(f"Welcome {dm.mention} to the {adventure.name} DM's")

    @adventure_commands.command(
        name="dm_remove",
        description="Removes a DM from an adventure. This command must be run in a channel of the adventure."
    )
    async def adventure_dm_remove(self, ctx: ApplicationContext,
                                  dm: Option(discord.Member, description="Player to remove as a DM", required=True)):
        """
        Removes a DM from an adventure. This command must be run in a channel of the adventure they are being
        removed from.

        :param ctx: Context
        :param dm: The DM to remove from the adventure
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif dm.id not in adventure.dms:
            return await ctx.respond(f"Error: Player not listed as a DM")
        elif len(adventure.dms) == 1:
            return await ctx.respond(f"Error: Adventure has only 1 DM, please add another before removing")
        elif ctx.author.id not in adventure.dms and not is_admin(ctx):
            return await ctx.respond(embed=ErrorEmbed(f"Error: You need to be the DM for this advernture or "
                                                      f"Council to do this."))
        else:
            adventure.dms.remove(dm.id)
            adventure_role = adventure.get_adventure_role(ctx)

            if adventure_role in dm.roles:
                await dm.remove_roles(adventure_role, reason=f"Removing player as DM from {adventure.name}")

            category = ctx.channel.category
            category_permissions = category.overwrites
            del category_permissions[dm]
            await category.edit(overwrites=category_permissions)

            for c in category.channels:
                c_permissions = c.overwrites
                del c_permissions[dm]
                await c.edit(overwrites=c_permissions)

            async with ctx.bot.db.acquire() as conn:
                await conn.execute(update_adventure(adventure))

        await ctx.respond(f"Removed {dm.mention} from {adventure.name} DM's")

    @adventure_commands.command(
        name="add",
        description="Adds a player to an adventure. This command must be run in a channel of the adventure."
    )
    async def adventure_add(self, ctx: ApplicationContext,
                            player_1: Option(discord.Member, description="Player to be added", required=True),
                            player_2: Option(discord.Member, description="Player to be added", required=False),
                            player_3: Option(discord.Member, description="Player to be added", required=False),
                            player_4: Option(discord.Member, description="Player to be added", required=False),
                            player_5: Option(discord.Member, description="Player to be added", required=False),
                            player_6: Option(discord.Member, description="Player to be added", required=False),
                            player_7: Option(discord.Member, description="Player to be added", required=False),
                            player_8: Option(discord.Member, description="Player to be added", required=False)):
        """
        Add a player or players to an adventure. This command must be run in a channel of the adventure they are being
        added to.

        :param ctx: Context
        :param player_1: Player to add to an adventure
        :param player_2: Player to add to an adventure
        :param player_3: Player to add to an adventure
        :param player_4: Player to add to an adventure
        :param player_5: Player to add to an adventure
        :param player_6: Player to add to an adventure
        :param player_7: Player to add to an adventure
        :param player_8: Player to add to an adventure
        :param calc_tier: Recalculate the tier on command run? Default=True
        """
        await ctx.defer()
        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        players = list(set(filter(
            lambda p: p is not None,
            [player_1, player_2, player_3, player_4, player_5, player_6, player_7, player_8]
        )))

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif ctx.author.id not in adventure.dms:
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            adventure_role = adventure.get_adventure_role(ctx)
            for player in players:
                if adventure_role in player.roles:
                    await ctx.send(f"{player.mention} already in adventure '{adventure.name}'")
                else:
                    await player.add_roles(adventure_role, reason=f"{player.name} added to role {adventure_role.name} by"
                                                                  f" {ctx.author.name}")
                    await ctx.send(f"{player.mention} added to adventure '{adventure.name}'")
        await ctx.delete()

    @adventure_commands.command(
        name="remove",
        description="Removes a player from an adventure. This command must be run in a channel of the adventure."
    )
    async def adventure_remove(self, ctx: ApplicationContext,
                               player: Option(discord.Member, description="Player to be removed", required=True)):
        """
        Removes a player from an adventure. This command must be run in a channel of the adventure they are being
        removed from.

        :param ctx: Context
        :param player: Player to remove from the adventure
        """
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif ctx.author.id not in adventure.dms:
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            adventure_role = adventure.get_adventure_role(ctx)
            if adventure_role not in player.roles:
                return await ctx.respond(f"Error: {player.mention} does not have role '{adventure_role.mention}'")
            else:
                await player.remove_roles(adventure_role,
                                          reason=f"{player.name} removed from role {adventure_role.name}"
                                                 f" by {ctx.author.name}")
        await ctx.delete()

    @adventure_commands.command(
        name="close",
        descripion="Close out an adventure"
    )
    async def adventure_close(self, ctx: ApplicationContext,
                              role: Option(Role, description="Role of the adventure to close", required=False,
                                           default=None),
                              reward: Option(bool, description="Whether to give any adventure close rewards",
                                                required=False, default=True)):
        """
        Marks an adventure as closed, and removes the Role from players

        :param ctx:  Context
        :param role: Role of the adventure
        """

        await ctx.defer()

        g: PlayerGuild = await get_or_create_guild(ctx.bot.db, ctx.guild_id)

        if role is None:
            adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)
            role = adventure.get_adventure_role(ctx)
        else:
            adventure: Adventure = await get_adventure_from_role(ctx.bot, role.id)

        if adventure is None and role is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif adventure is None:
            return await ctx.respond(f"Error: No adventure found for {role.mention}.")
        elif role is None:
            return await ctx.respond(f"Error: No role found for {adventure.name}.")
        elif ctx.author.id not in adventure.dms and not is_admin(ctx):
            return await ctx.respond(f"Error: You are not a DM of this adventure")
        else:
            to_end = await confirm(ctx, "Are you sure you want to end this adventure? (Reply with yes/no)", True)

            if to_end is None:
                return await ctx.respond(f'Timed out waiting for a response or invalid response.', delete_after=10)
            elif not to_end:
                return await ctx.respond(f'Ok, cancelling.', delete_after=10)

            if reward:
                players = [p.id for p in role.members]
                act: Activity = ctx.bot.compendium.get_object("c_activity", "ADVENTURE_END")
                async with ctx.bot.db.acquire() as conn:
                    async for row in await conn.execute(get_multiple_characters(players, ctx.guild.id)):
                        if row is not None:
                            character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)
                            await create_logs(ctx, character, act, adventure.name, 0, 0, adventure)

            adventure_role = adventure.get_adventure_role(ctx)
            adventure.end_ts = datetime.utcnow()

            await ctx.respond(embed=AdventureCloseEmbed(ctx, adventure))

            await adventure_role.delete(reason=f'Closing adventure')

            async with ctx.bot.db.acquire() as conn:
                await conn.execute(update_adventure(adventure))

    @adventure_commands.command(
        name="status",
        description="Adventure status"
    )
    async def adventure_status(self, ctx: ApplicationContext,
                               role: Option(Role, description="Role of the adventure if not ran in an Adventure Channel",
                                            required=False, default=None)):

        await ctx.defer()

        if role is None:
            adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)
        else:
            adventure: Adventure = await get_adventure_from_role(ctx.bot, role.id)

        if adventure is None and role is None:
            return await ctx.respond(f"Error: No adventure associated with this channel")
        elif adventure is None:
            return await ctx.respond(f"Error: No adventure found for {role.mention}.")

        return await ctx.respond(embed=AdventureStatusEmbed(ctx, adventure))

    @adventure_commands.command(
        name="reward",
        description="Grants adventure rewards to the players of a given adventure role"
    )
    async def ep_log(self, ctx: ApplicationContext,
                     cc: Option(int, description="The number of cc to give rewards for")):
        await ctx.defer()

        adventure: Adventure = await get_adventure(ctx.bot, ctx.channel.category_id)

        if adventure is None:
            return await ctx.respond(embed=ErrorEmbed(description="No adventure associated with this channel"))
        elif ctx.author.id not in adventure.dms and not is_admin(ctx):
            return await ctx.respond(embed=ErrorEmbed(description="Error: You either need to be the DM for this "
                                                                  "adventure or Senate to do this."))

        role = adventure.get_adventure_role(ctx)


        players = [p.id for p in role.members]
        adventure.cc += cc

        char_act: Activity = ctx.bot.compendium.get_object("c_activity", "ADVENTURE")
        dm_act: Activity = ctx.bot.compendium.get_object("c_activity", "ADVENTURE_DM")

        async with ctx.bot.db.acquire() as conn:
            await conn.execute(update_adventure(adventure))
            async for row in await conn.execute(get_multiple_characters(players, ctx.guild.id)):
                if row is not None:
                    character: PlayerCharacter = CharacterSchema(ctx.bot.compendium).load(row)

                    if character.player_id in adventure.dms:
                        activity = dm_act
                        log_cc = cc + ceil(cc * .25)
                    else:
                        activity = char_act
                        log_cc = cc

                    await create_logs(ctx, character, activity, adventure.name, log_cc, 0, adventure)

        await ctx.respond(embed=AdventureRewardEmbed(ctx, adventure, cc))



