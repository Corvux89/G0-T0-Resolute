import discord

from typing import Mapping, Type
from discord import SelectOption
from discord.ui import Modal, InputText

from Resolute.bot import G0T0Bot
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.views.base import InteractiveView

class RoomSettings(InteractiveView):
    __menu_copy_attrs__ = ("bot", "adventure", "roles")
    bot: G0T0Bot
    owner: discord.Member = None
    adventure: Adventure = None
    roles: list[discord.Role] = []    
    
    async def _before_send(self, interaction: discord.Interaction):
        pass

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send(destination)
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["RoomSettings"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send(interaction)
        await view.refresh_content(interaction)

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send(interaction)
        await self.commit()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)
    
class RoomSettingsUI(RoomSettings):
    @classmethod
    def new(cls, bot, owner, roles = [], adventure = None):
        inst = cls(owner = owner)
        inst.bot = bot
        inst.roles = roles
        inst.adventure = adventure
        return inst
    
    @discord.ui.select(placeholder="Select a view option", row=1)
    async def room_view(self, choice: discord.ui.Select, interaction: discord.Interaction):
        view = int(choice.values[0])

        read = True if view == 1 or view == 2 else False
        write = True if view == 1 else False

        for role in self.roles:
            perms = interaction.channel.overwrites_for(role)
            perms.view_channel=read
            perms.send_messages=write
            await interaction.channel.set_permissions(role, overwrite=perms)

        await self.refresh_content(interaction)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, row=2)
    async def room_rename(self, _: discord.ui.Button, interaction: discord.Interaction):
        modal = RoomNameModal(interaction.channel.name)
        response = await self.prompt_modal(interaction, modal)

        await interaction.channel.edit(name=response.name)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Add", style=discord.ButtonStyle.primary, row=2)
    async def room_add(self, _: discord.ui.Button, interaciton: discord.Interaction):
        modal = RoomNameModal()
        response = await self.prompt_modal(interaciton, modal)
        await interaciton.channel.category.create_text_channel(response.name, reason=f"Room created by {self.owner.name}")
        await self.refresh_content(interaciton)

    @discord.ui.button(label="Move", style=discord.ButtonStyle.primary, row=2)
    async def room_move(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(_RoomMoveUI, interaction)
    
    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, row=3)
    async def exit(self, *_):
        await self.on_timeout()

    async def _before_send(self, interaction: discord.Interaction):
        if not self.roles:
            await interaction.channel.send(embed=ErrorEmbed("No roles found to manage"), delete_after=5)
            await self.on_timeout()

        if not self.adventure:
            self.remove_item(self.room_move)
            self.remove_item(self.room_rename)
            self.remove_item(self.room_add)

        # Defaulting
        default = 1
        channel = interaction.guild.get_channel(interaction.channel.id)
        perms = channel.permissions_for(self.roles[0])

        if perms.send_messages == False and perms.view_channel == False:
            default = 3
        elif perms.view_channel == True and perms.send_messages == False:
            default = 2


        view_options = [
            SelectOption(label="Read/Write Access", value="1", description="Allow others to read and write", default=True if default == 1 else False),
            SelectOption(label="Read Only Acccess", value="2", description="Allow others to just read", default=True if default == 2 else False),
            SelectOption(label="No Access", value="3", description="Don't allow others to view/write", default=True if default == 3 else False)
            ]
        
        self.room_view.options = view_options
        
    
    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Choose an option: \n"}
    

class _RoomMoveUI(RoomSettings):
    current_position: int = None


    @discord.ui.button(label="Up", style=discord.ButtonStyle.green, row=1, emoji="⬆")
    async def move_up(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.current_position == 0:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel is already in the top position"), delete_after=5)
        else:
            await update_position(interaction.channel.category.channels, self.current_position, self.current_position-1)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Top", style=discord.ButtonStyle.primary, row=1, emoji="🔝")
    async def move_top(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.current_position == 0:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel is already in the top position"), delete_after=5)
        else:
            await update_position(interaction.channel.category.channels, self.current_position, 0)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Down", style=discord.ButtonStyle.green, row=2, emoji="⬇")
    async def move_down(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.current_position == len(interaction.channel.category.channels)-1:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel is already in the lowest position"), delete_after=5)
        else:
            await update_position(interaction.channel.category.channels, self.current_position, self.current_position+1)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Bottom", style=discord.ButtonStyle.primary, row=2)
    async def move_bottom(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.current_position == len(interaction.channel.category.channels)-1:
            await interaction.channel.send(embed=ErrorEmbed(f"Channel is already in the lowest position"), delete_after=5)
        else:
            await update_position(interaction.channel.category.channels, self.current_position, len(interaction.channel.category.channels)-1)
        
        await self.refresh_content(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=3)
    async def back(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.defer_to(RoomSettingsUI, interaction)

    async def _before_send(self, interaction: discord.Interaction):
        self.current_position = interaction.channel.category.channels.index(interaction.channel)
    
    async def get_content(self) -> Mapping:
        return {"embed": None, "content": "Choose an option on where to move the channel: \n"}

async def update_position(channel_list: list[discord.TextChannel], old_position: int, new_position: int) -> None:
    channel_list.insert(new_position, channel_list.pop(old_position))

    for i, c in enumerate(channel_list):
        await c.edit(position=i)
    
    return

    
class RoomNameModal(Modal):
    name: str

    def __init__(self, name = None):
        super().__init__(title=f"Channel Name")
        self.name = name

        self.add_item(InputText(label="Channel Name", required=True, value=self.name, placeholder="Channel Name", max_length=25))

    async def callback(self, interaction: discord.Interaction):
        self.name = self.children[0].value

        await interaction.response.defer()
        self.stop()
        