import asyncio
import logging
import io

import discord.utils
from PIL import Image, ImageDraw, ImageFilter
from discord import SlashCommandGroup
from discord.ext import commands, tasks

from Resolute.bot import G0T0Bot
from Resolute.constants import DASHBOARD_REFRESH_INTERVAL
from Resolute.helpers import get_last_message, get_or_create_guild, \
    get_guild_character_summary_stats, draw_progress_bar
from Resolute.models.db_objects import RefCategoryDashboard, DashboardType, PlayerGuild
from Resolute.models.embeds import RpDashboardEmbed, ShopDashboardEmbed, \
    GuildProgress
from Resolute.models.schemas import RefCategoryDashboardSchema
from Resolute.queries import get_dashboards, delete_dashboard
from timeit import default_timer as timer

log = logging.getLogger(__name__)


# def setup(bot: commands.Bot):
#     bot.add_cog(Dashboards(bot))


class Dashboards(commands.Cog):
    bot: G0T0Bot
    dashboard_commands = SlashCommandGroup("dashboard", "Dashboard commands")

    def __init__(self, bot):
        self.bot = bot
        print(f'Cog \'Dashboards\' loaded')

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(6.0)
        log.info(f"Reloading dashboards every {DASHBOARD_REFRESH_INTERVAL} minutes.")
        await self.update_dashboards.start()

    async def update_dashboard(self, dashboard: RefCategoryDashboard):
        """
        Primary method to update a dashboard

        :param dashboard: RefCategoryDashboard to update
        """

        original_message = await dashboard.get_pinned_post(self.bot)

        if original_message is None or not original_message.pinned:
            async with self.bot.db.acquire() as conn:
                return await conn.execute(delete_dashboard(dashboard))

        dType: DashboardType = self.bot.compendium.get_object("c_dashboard_type", dashboard.dashboard_type)
        channels = dashboard.channels_to_check(self.bot)

        if dType is not None and dType.value.upper() == "RP":
            channels_dict = {
                "Magewright": [],
                "Available": [],
                "In Use": []
            }

            g: discord.Guild = dashboard.get_category_channel(self.bot).guild
            magewright_role = discord.utils.get(g.roles, name="Magewright")

            for c in channels:
                last_message = await get_last_message(c)

                if last_message is None or last_message.content in ["```\n​\n```", "```\n \n```"]:
                    channels_dict["Available"].append(c.mention)
                elif magewright_role is not None and magewright_role.mention in last_message.content:
                    channels_dict["Magewright"].append(c.mention)
                else:
                    channels_dict["In Use"].append(c.mention)

            category = dashboard.get_category_channel(self.bot)
            return await original_message.edit(content='', embed=RpDashboardEmbed(channels_dict, category.name))

        elif dType is not None and dType.value.upper() == "SHOP":
            shop_dict = {}
            g: discord.Guild = dashboard.get_category_channel(self.bot).guild

            for shop_type in self.bot.compendium.c_shop_type[0].values():
                shop_dict[shop_type.value] = []

            async with self.bot.db.acquire() as conn:
                async for row in conn.execute(get_shops(g.id)):
                    if row is not None:
                        shop: Shop = ShopSchema(self.bot.compendium).load(row)
                        shop_dict[shop.type.value].append(shop)

            return await original_message.edit(content='', embed=ShopDashboardEmbed(g, shop_dict))

        elif dType is not None and dType.value.upper() == "GUILD":
            dGuild: discord.Guild = dashboard.get_category_channel(self.bot).guild
            g: PlayerGuild = await get_or_create_guild(self.bot.db, dGuild.id)
            total, inactive = await get_guild_character_summary_stats(self.bot, dGuild.id)

            progress=g.get_xp_float(total, inactive) if g.get_xp_float(total, inactive) <= 1 else 1

            # Start Drawing
            width = 500
            height = int(width * .15)
            scale = .86

            out = Image.new("RGBA", (width,height), (0,0,0,0))
            d = ImageDraw.Draw(out)
            d = draw_progress_bar(d, 0, 0, int(width*scale), int(height*scale), progress)
            sharp_out = out.filter(ImageFilter.SHARPEN)

            embed=GuildProgress(dGuild.name)

            with io.BytesIO() as output:
                sharp_out.save(output, format="PNG")
                output.seek(0)
                file = discord.File(fp=output, filename='image.png')
                embed.set_image(url="attachment://image.png")

                return await original_message.edit(file=file, embed=embed, content='')


    # --------------------------- #
    # Tasks
    # --------------------------- #
    @tasks.loop(minutes=DASHBOARD_REFRESH_INTERVAL)
    async def update_dashboards(self):
        start = timer()
        async with self.bot.db.acquire() as conn:
            async for row in conn.execute(get_dashboards()):
                dashboard: RefCategoryDashboard = RefCategoryDashboardSchema().load(row)
                await self.update_dashboard(dashboard)
        end = timer()
        log.info(f"DASHBOARD: Channel status dashboards updated in [ {end - start:.2f} ]s")
