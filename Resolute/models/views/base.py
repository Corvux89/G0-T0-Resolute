from typing import Mapping, Optional, Type

import discord
import discord.ui

from Resolute.models.embeds import ErrorEmbed
from Resolute.models.objects.exceptions import G0T0Error


class InteractiveView(discord.ui.View):
    """
    InteractiveView is a subclass of View that provides interactive functionalities for a Discord bot.
    Attributes:
        owner (discord.Member): The owner of the interaction.
        message (Optional[discord.Message]): The message associated with the view.
    Methods:
        __init__(owner: discord.Member, *args, **kwargs):
            Initializes the InteractiveView with the owner and other arguments.
        interaction_check(interaction: discord.Interaction) -> bool:
        on_error(error, item, interaction):
            Handles errors that occur during interaction.
        from_menu(other: "InteractiveView") -> "InteractiveView":
            Creates a new instance of InteractiveView from another instance.
        _before_send():
            Placeholder method to be executed before sending a message.
        commit():
            Placeholder method for committing changes.
        on_timeout() -> None:
            Handles the timeout event by editing and deleting the message.
        send_to(destination, *args, **kwargs):
            Sends the view to a specified destination.
        defer_to(view_type: Type["InteractiveView"], interaction: discord.Interaction, stop=True):
            Defers the interaction to another view type.
        get_content() -> Mapping:
            Returns the content to be sent with the view.
        refresh_content(interaction: discord.Interaction, **kwargs):
            Refreshes the content of the view based on the interaction.
        prompt_modal(interaction: discord.Interaction, modal):
            Prompts the user with a modal and waits for their response.
        """


    def __init__(self, owner: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.message = None # type: Optional[discord.Message]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Checks if the user initiating the interaction is the owner.
        Args:
            interaction (discord.Interaction): The interaction to check.
        Returns:
            bool: True if the user is the owner, False otherwise.
        Sends a message to the user if they are not the owner.
        """
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the owner of this interaction", ephemeral=True)
        return False
    
    async def on_error(self, error, item, interaction):
        """
        Handles errors that occur during an interaction.
        Args:
            error (Exception): The error that occurred.
            item: The item that was being interacted with when the error occurred.
            interaction: The interaction object representing the user's interaction.
        Returns:
            Coroutine: A coroutine that sends an error message if the error is an instance of G0T0Error,
                       otherwise calls the superclass's on_error method.
        """
        if isinstance(error, G0T0Error):
            return await interaction.response.send_message(embed=ErrorEmbed(error), ephemeral=True)

        return await super().on_error(error, item, interaction)
    
    @classmethod
    def from_menu(cls, other: "InteractiveView"):
        """
        Create a new instance of the class by copying attributes from another instance of InteractiveView.
        This method initializes a new instance of the class with the same owner and message as the provided
        `other` instance. It then copies a predefined set of attributes from the `other` instance to the new
        instance. If an attribute is not present in the `other` instance, it falls back to the class default.
        Args:
            other (InteractiveView): The instance from which to copy attributes.
        Returns:
            cls: A new instance of the class with copied attributes.
        """

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
        """
        An asynchronous method that is intended to be executed before sending a request or performing an action.
        This method is currently a placeholder and does not contain any implementation. Override this method in a subclass
        to add custom behavior that should occur before the main action is executed.
        Note:
            This method should be overridden with an asynchronous implementation.
        """
        pass

    async def commit(self):
        """
        Asynchronously commit the current transaction.
        This method should be overridden in subclasses to provide the actual
        implementation for committing a transaction. The implementation should
        ensure that all changes made during the transaction are saved and
        persisted.
        Raises:
            NotImplementedError: If the method is not overridden in a subclass.
        """
        pass

    async def on_timeout(self) -> None:
        """
        Handles the timeout event for the view.
        This method is called when the view times out. It attempts to edit the message
        associated with the view to remove the view and then delete the message. If the
        message is None, the method returns immediately. If an discord.HTTPException occurs
        during the process, it is caught and printed.
        Returns:
            None
        """
        if self.message is None:
            return
        try:
            await self.message.edit(view=None)
            await self.message.delete()
        except discord.HTTPException as e:
            print(e)
            pass

    async def send_to(self, destination, *args, **kwargs):
        """
        Asynchronously sends a message to the specified destination.
        This method prepares the content to be sent, performs any necessary
        actions before sending, and then sends the message to the destination.
        Args:
            destination: The target destination where the message will be sent.
            *args: Additional positional arguments to be passed to the destination's send method.
            **kwargs: Additional keyword arguments to be passed to the destination's send method.
        Returns:
            The message object that was sent to the destination.
        """
        content_kwargs = await self.get_content()
        await self._before_send()
        message = await destination.send(*args, view=self, **content_kwargs, **kwargs)
        self.message = message
        return message

    async def defer_to(self, view_type: Type["InteractiveView"], interaction: discord.Interaction, stop=True):
        """
        Defers the current view to another view of the specified type.
        This method stops the current view (if specified) and transitions to a new view
        of the given type. It prepares the new view by calling its `_before_send` method
        and then refreshes its content based on the provided interaction.
        Args:
            view_type (Type["InteractiveView"]): The type of the view to defer to.
            interaction (discord.Interaction): The interaction that triggered the deferment.
            stop (bool, optional): Whether to stop the current view. Defaults to True.
        Returns:
            None
        """
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def get_content(self) -> Mapping:
        """
        Asynchronously retrieves content.
        Returns:
            Mapping: An empty mapping object.
        """
        return {}

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        """
        Refreshes the content of the interaction.
        This method commits any changes, retrieves the updated content, and updates the interaction response accordingly.
        Args:
            interaction (discord.Interaction): The interaction object to be refreshed.
            **kwargs: Additional keyword arguments to be passed to the response methods.
        Returns:
            None
        Raises:
            None
        """
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
        """
        Asynchronously prompts a modal dialog in response to an interaction.
        Args:
            interaction (discord.Interaction): The interaction that triggers the modal.
            modal: The modal dialog to be displayed.
        Returns:
            The modal dialog after it has been interacted with.
        """
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal
