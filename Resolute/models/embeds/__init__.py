import discord

class ErrorEmbed(discord.Embed):

    def __init__(self, description, *args, **kwargs):
        kwargs['title'] = "Error:"
        kwargs['color'] = discord.Color.brand_red()
        kwargs['description'] = kwargs.get('description', description)
        super().__init__(**kwargs)
