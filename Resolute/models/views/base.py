from typing import Mapping, Optional, Type

import discord


class InteractiveView(discord.ui.View):
    def __init__(self, owner: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.message = None # type: Optional[discord.Message]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the owner of this interaction", ephemeral=True)
        return False
    
    @classmethod
    def from_menu(cls, other: "InteractiveView"):
        inst = cls(owner=other.owner)
        inst.message = other.message
        for attr in cls.__menu_copy_attrs__:
            # copy the instance attr to the new instance if available, or fall back to the class default
            sentinel = object()
            value = getattr(other, attr, sentinel)
            if value is sentinel:
                value = getattr(cls, attr, None)
            setattr(inst, attr, value)
        return inst
    
    async def _before_send(self):
        pass

    async def commit(self):
        pass

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.edit(view=None)
            await self.message.delete()
        except discord.HTTPException as e:
            print(e)
            pass

    async def send_to(self, destination, *args, **kwargs):
        content_kwargs = await self.get_content()
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["InteractiveView"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self) -> Mapping:
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        await self.commit()
        content_kwargs = await self.get_content()
        await self._before_send()
        if interaction.response.is_done():
            try:
                await interaction.edit_original_response(view=self, **content_kwargs, **kwargs)
            except:
                pass
        else:
            await interaction.response.edit_message(view=self, **content_kwargs, **kwargs)

    @staticmethod
    async def prompt_modal(interaction: discord.Interaction, modal):
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal
