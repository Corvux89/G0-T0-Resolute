import logging
import datetime
import calendar
from typing import List
import discord
from Resolute.models.db_objects.category_objects import *

log = logging.getLogger(__name__)


class PlayerCharacterClass(object):
    character_id: int
    primary_class: CharacterClass
    archetype: CharacterArchetype
    active: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_formatted_class(self):
        if self.archetype is not None:
            return f"{self.archetype.value} {self.primary_class.value}"
        else:
            return f"{self.primary_class.value}"


class PlayerCharacter(object):
    # Attributes based on queries: total_level, div_gold, max_gold, div_xp, max_xp, l1_arena, l2_arena, l1_rp, l2_rp
    player_id: int
    guild_id: int
    name: str
    species: CharacterSpecies
    credits: int
    cc: int
    div_cc: int
    token: int
    level: int
    active: bool
    reroll: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_member(self, ctx: ApplicationContext) -> discord.Member:
        return discord.utils.get(ctx.guild.members, id=self.player_id)

    def get_member_mention(self, ctx: ApplicationContext):
        try:
            name = discord.utils.get(ctx.guild.members, id=self.player_id).mention
            pass
        except:
            name = f"Player {self.player_id} not found on this server for character {self.name}"
            pass
        return name

    def mention(self) -> str:
        return f"<@{self.player_id}>"


class PlayerGuild(object):
    id: int
    max_level: int
    weeks: int
    max_reroll: int
    greeting: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_reset_day(self):
        if hasattr(self, "reset_day"):
            weekDays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
            return weekDays[self.reset_day]

    def get_next_reset(self):
        if self.reset_hour is not None:
            now = datetime.datetime.utcnow()
            day_offset = (self.reset_day - now.weekday() + 7) % 7
            test = now - datetime.timedelta(days=6)

            run_date = now + datetime.timedelta(days=day_offset)

            if (self.reset_hour < now.hour and run_date <= now) \
                    or (run_date < (self.last_reset + datetime.timedelta(days=6))):
                run_date += datetime.timedelta(days=7)

            dt = calendar.timegm(
                datetime.datetime(run_date.year, run_date.month, run_date.day, self.reset_hour, 0, 0).utctimetuple())

            return dt
        else:
            return None

    def get_last_reset(self):
        return calendar.timegm(self.last_reset.utctimetuple())


class Adventure(object):
    guild_id: int
    name: str
    role_id: int
    dms: List[int]
    category_channel_id: int
    cc: int

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_adventure_role(self, ctx: ApplicationContext) -> Role:
        return discord.utils.get(ctx.guild.roles, id=self.role_id)


class DBLog(object):
    author: int
    cc: int
    credits: int
    token: int
    character_id: int
    activity: Activity
    notes: str
    adventure_id: int | None
    invalid: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_author(self, ctx: ApplicationContext) -> discord.Member | None:
        return discord.utils.get(ctx.guild.members, id=self.author)


class Arena(object):
    channel_id: int
    role_id: int
    host_id: int
    tier: ArenaTier
    type: ArenaType
    completed_phases: int

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_role(self, ctx: ApplicationContext | discord.Interaction) -> Role:
        return discord.utils.get(ctx.guild.roles, id=self.role_id)

    def get_host(self, ctx: ApplicationContext | discord.Interaction) -> discord.Member:
        return discord.utils.get(ctx.guild.members, id=self.host_id)


class CharacterStarship(object):
    character_id: List[int]
    name: str
    transponder: str
    starship: StarshipRole
    tier: int | None = None
    active: bool = True

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_formatted_starship(self, compendium):
        return f"**{self.name}** *({self.starship.get_size(compendium).value} {self.starship.value} {self.tier})*: {self.transponder}"


