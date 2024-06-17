import discord

from discord import Embed, Member, PermissionOverwrite, Role

from Resolute.constants import ZWSP3

class ChannelEmbed(Embed):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title=f"{channel.name} Summary")

        self.description = f"**Category**: {channel.category.mention}\n"\
        

        category_overwrites = channel.category.overwrites


        self.add_field(name="Category Overwrites",
                       value="\n".join(get_overwrite_string(category_overwrites)),
                       inline=False)
        
        channel_overwrites = channel.overwrites

        self.add_field(name="Channel Overwrites",
                       value="\n".join(get_overwrite_string(channel_overwrites)),
                       inline=False)


def get_overwrite_string(overwrites: dict[Role | Member, PermissionOverwrite]):
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



        