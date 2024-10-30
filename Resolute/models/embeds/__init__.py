from discord import Embed, Color

class ErrorEmbed(Embed):

    def __init__(self, description, *args, **kwargs):
        kwargs['title'] = "Error:"
        kwargs['color'] = Color.brand_red()
        kwargs['description'] = kwargs.get('description', description)
        super().__init__(**kwargs)
