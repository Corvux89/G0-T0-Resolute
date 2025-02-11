import discord

from Resolute.constants import ZWSP3


class ChannelEmbed(discord.Embed):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title=f"{channel.name} Summary")
        chunk_size = 1000

        self.description = f"**Category**: {channel.category.mention}\n"\
        

        category_overwrites = channel.category.overwrites
        category_string = "\n".join(get_overwrite_string(category_overwrites))
        category_chunk = [category_string[i:i+chunk_size] for i in range(0, len(category_string), chunk_size)]

        for i,chunk in enumerate(category_chunk):
            self.add_field(name=f"Category Overwrites {f'{i+1}' if len(category_chunk)>1 else ''}",
                        value=chunk,
                        inline=False)
        
        channel_overwrites = channel.overwrites
        channel_string = "\n".join(get_overwrite_string(channel_overwrites))
        channel_chunk = [channel_string[i:i+chunk_size] for i in range(0, len(channel_string), chunk_size)]

        for i,chunk in enumerate(channel_chunk):
            self.add_field(name=f"Channel Overwrites {f'{i+1}' if len(channel_chunk)>1 else ''}",
                        value=chunk,
                        inline=False)


def get_overwrite_string(overwrites: dict[ discord.Role | discord.Member, discord.PermissionOverwrite]):
    out = []
    for target in overwrites:
        value = f"**{target.mention}**:\n"
        ovr = [x for x in overwrites[target] if x[1] is not None]

        if ovr:
            value += "\n".join([f"{ZWSP3}{o[0]} - {o[1]}" for o in ovr])
        else:
            value += "None\n"
        
        out.append(value)
    return out



        