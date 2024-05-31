from discord import Embed, Color

from .guilds import *
from .characters import *
from .logs import *
from .players import *


class ErrorEmbed(Embed):

    def __init__(self, *args, **kwargs):
        kwargs['title'] = "Error:"
        kwargs['color'] = Color.brand_red()
        super().__init__(**kwargs)
