import logging

import discord
from discord import SlashCommandGroup, ApplicationContext, Member, Option, CategoryChannel, TextChannel
from discord.ext import commands
from ProphetBot.bot import  BpBot
from ProphetBot.helpers import is_admin
from ProphetBot.models.embeds import ErrorEmbed

log = logging.getLogger(__name__)


def setup(bot: commands.Bot):
    bot.add_cog(Holdings(bot))


class Holdings(commands.Cog):
    bot: BpBot
    holding_admin = SlashCommandGroup("holding_admin", "Commands related to holding administration")


    @holding_admin.command(
        name="create",
        description="Open a holding"
    )
    @commands.check(is_admin)
    async def holding_open(self, ctx: ApplicationContext,
                           owner: Option(Member, description="Holding owner", required=True),
                           name: Option(str, description="Name of the holding", required=True),
                           category_channel: Option(CategoryChannel, description="Holding Channel Category",
                                                    required=True),
                           owner_2: Option(Member, description="2nd Owner", required=False),
                           owner_3: Option(Member, description="3rd Owner", required=False)):

        await ctx.defer()

        chan_perms = dict()

        chan_perms[owner] = discord.PermissionOverwrite(view_channel=True,
                                                        manage_messages=True,
                                                        send_messages=True)
        if owner_2 is not None:
            chan_perms[owner_2] = chan_perms[owner]

        if owner_3 is not None:
            chan_perms[owner_3] = chan_perms[owner]

        if bots_role := discord.utils.get(ctx.guild.roles, name="Bots"):
            chan_perms[bots_role] = discord.PermissionOverwrite(view_channel=True,
                                                                send_messages=True)

        if guild_member := discord.utils.get(ctx.guild.roles, name="Guild Member"):
            chan_perms[guild_member] = discord.PermissionOverwrite(view_channel=True,
                                                                   send_messages=False)

        if guild_initiate := discord.utils.get(ctx.guild.roles, name="Guild Initiate"):
            chan_perms[guild_initiate] = discord.PermissionOverwrite(view_channel=True,
                                                                     send_messages=False)


        holding_chanel = await ctx.guild.create_text_channel(
            name=name,
            category=category_channel,
            overwrites=chan_perms,
            reason=f"New holding {name}"
        )

        await holding_chanel.send(f'{owner.mention} welcome to your new holding.\n'
                                  f'Go ahead and set everything up.\n'
                                  f'1. Make sure you can delete this message\n'
                                  f'2. `/room view view:Open allow_post:true` to open the holding up for visitors!')
        await ctx.delete()

    @holding_admin.command(
        name="modify_owner",
        description="Add an owner to a holding"
    )
    @commands.check(is_admin)
    async def holding_modify(self, ctx: ApplicationContext,
                             owner: Option(Member, description="Owner to add/remove", required=True),
                             channel: Option(TextChannel, description="Holding to modify", required=True),
                             modify: Option(str, description="Add/remove owner. Default: Add", choices=["Add", "Remove"],
                                            required=False, default="Add")):
        await ctx.defer()

        chan_perms = channel.overwrites

        if modify=="Add":
            chan_perms[owner] = discord.PermissionOverwrite(view_channel=True,
                                                            manage_messages=True)
            phrase = "added as an owner!"
        elif modify=="Remove":
            phrase = "removed as an owner"
            del chan_perms[owner]
        else:
            return await ctx.respond(embed=ErrorEmbed(description="Error: Something is wrong with the parameters."),
                                                      ephemeral=True)

        await channel.edit(overwrites=chan_perms)

        await channel.send(f"{owner.mention} {phrase}.")

