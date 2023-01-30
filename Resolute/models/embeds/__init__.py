from discord import Embed, Color

from .entity_embeds import *
from .ref_embeds import *


class ErrorEmbed(Embed):

    def __init__(self, *args, **kwargs):
        kwargs['title'] = "Error:"
        kwargs['color'] = Color.brand_red()
        super().__init__(**kwargs)
