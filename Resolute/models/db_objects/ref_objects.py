from typing import List

import discord.utils
from discord import ApplicationContext, TextChannel, CategoryChannel, Message, Bot

from ProphetBot.models.db_objects import DashboardType, GlobalModifier, HostStatus


class RefCategoryDashboard(object):
    category_channel_id: int
    dashboard_post_channel_id: int
    dashboard_post_id: int
    excluded_channel_ids: List[int]
    dashboard_type: int

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def channels_to_check(self, bot: Bot) -> List[TextChannel]:
        category: CategoryChannel = bot.get_channel(self.category_channel_id)
        if category is not None:
            return list(filter(lambda c: c.id not in self.excluded_channel_ids, category.text_channels))
        else:
            return []

    def get_category_channel(self, bot: Bot) -> CategoryChannel | None:
        return bot.get_channel(self.category_channel_id)

    async def get_pinned_post(self, bot: Bot) -> Message | None:
        channel = bot.get_channel(self.dashboard_post_channel_id)
        if channel is not None:
            try:
                msg = await channel.fetch_message(self.dashboard_post_id)
            except discord.errors.NotFound as e:
                return None
            return msg
        return None


class RefWeeklyStipend(object):
    guild_id: int
    role_id: int
    ratio: float
    reason: str
    leadership: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class GlobalPlayer(object):
    guild_id: int
    player_id: int
    modifier: GlobalModifier
    host: HostStatus
    gold: int
    xp: int
    update: bool
    active: bool
    num_messages: int
    channels: List[int]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_name(self, ctx: ApplicationContext):
        try:
            name = discord.utils.get(ctx.bot.get_all_members(), id=self.player_id).mention
            pass
        except:
            name = f"Player {self.player_id} not found on this server"
            pass

        return name


class GlobalEvent(object):
    guild_id: int
    name: str
    base_gold: int
    base_xp: int
    base_mod: GlobalModifier
    combat: bool
    channels: List[int]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_channel_names(self, bot: Bot):
        names = []
        for c in self.channels:
            names.append(bot.get_channel(int(c)).name)
        return names
