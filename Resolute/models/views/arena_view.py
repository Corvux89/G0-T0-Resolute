from typing import Type

import discord


from Resolute.models.categories.categories import ArenaType
from Resolute.models.embeds import ErrorEmbed
from Resolute.models.embeds.players import ArenaPostEmbed
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.enum import ArenaPostType
from Resolute.models.objects.exceptions import (
    ArenaNotFound,
    CharacterNotFound,
    G0T0Error,
)
from Resolute.models.objects.guilds import PlayerGuild
from Resolute.models.views.base import InteractiveView
from Resolute.bot import G0T0Bot
from Resolute.models.objects.players import ArenaPost, Player


class ArenaView(discord.ui.View):
    """
    ArenaView class represents a view for the arena in the G0-T0-Resolute game.
    Attributes:
        __menu_copy_attrs__ (tuple): Attributes to copy from another instance.
        bot (G0T0Bot): The bot instance associated with the view.
        player (Player): The player associated with the view, default is None.
    Methods:
        __init__(bot: G0T0Bot):
            Initializes the ArenaView with the given bot.
        on_error(error, item, interaction):
            Handles errors that occur during interaction. Sends an error message if the error is of type G0T0Error.
        from_menu(cls, other: "ArenaView"):
            Creates a new instance of ArenaView by copying attributes from another instance.
        _before_send():
            Placeholder method to be executed before sending a message.
        send_to(destination, *args, **kwargs):
            Sends the view to the specified destination and pins the message.
        defer_to(view_type: Type["ArenaView"], interaction: discord.Interaction, stop=True):
            Defers the view to another view type and refreshes the content.
        refresh_content(interaction: discord.Interaction, **kwargs):
            Refreshes the content of the view based on the interaction.
    """

    __menu_copy_attrs__ = ("bot", "player")
    bot: G0T0Bot
    player: Player = None

    def __init__(self, bot: G0T0Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def on_error(self, error, item, interaction):
        if isinstance(error, G0T0Error):
            return await interaction.response.send_message(
                embed=ErrorEmbed(error), ephemeral=True
            )

    @classmethod
    def from_menu(cls, other: "ArenaView"):
        inst = cls(bot=other.bot)
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

    async def send_to(self, destination, *args, **kwargs):
        await self._before_send()
        message = await destination.send(*args, view=self, **kwargs)
        await message.pin(reason=f"Arena Claimed by {destination.author.name}")
        self.message = message
        return message

    async def defer_to(
        self, view_type: Type["ArenaView"], interaction: discord.Interaction, stop=True
    ):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        await self._before_send()
        if interaction.response.is_done():
            arena = await self.bot.get_arena(interaction.channel.id)
            message: discord.Message = await interaction.channel.fetch_message(
                arena.pin_message_id
            )
            await message.edit(view=self, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **kwargs)

    async def clear_timeout(self) -> None:
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


class CharacterArenaViewUI(ArenaView):
    """
    A view for managing character interactions within an arena.
    Methods
    -------
    new(cls, bot: G0T0Bot) -> CharacterArenaViewUI
        Class method to create a new instance of CharacterArenaViewUI.
    join_arena_button(self, _: discord.ui.Button, interaction: discord.Interaction)
        Handles the interaction when a user clicks the "Join Arena" button.
    """

    @classmethod
    def new(cls, bot: G0T0Bot):
        inst = cls(bot=bot)
        return inst

    @discord.ui.button(
        label="Join Arena",
        style=discord.ButtonStyle.primary,
        custom_id="join_arena_button",
    )
    async def join_arena_button(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        arena = await self.bot.get_arena(interaction.channel.id)

        if arena is None:
            raise ArenaNotFound()

        if interaction.user.id == arena.host_id:
            raise G0T0Error("You're already hosting this arena.")

        self.player = await self.bot.get_player(
            interaction.user.id, interaction.guild.id
        )

        if not self.player.characters:
            raise CharacterNotFound(self.player.member)
        elif len(self.player.characters) == 1:
            await self.player.add_to_arena(
                interaction, self.player.characters[0], arena
            )
        else:
            await self.defer_to(ArenaCharacterSelect, interaction)

        await self.refresh_content(interaction)


class ArenaCharacterSelect(ArenaView):
    owner_id: int = None
    clear: bool = False

    @classmethod
    def new(
        cls, bot: G0T0Bot, player: Player, owner_id: int = None, clear: bool = False
    ):
        inst = cls(bot=bot)
        inst.player = player
        inst.owner_id = owner_id
        inst.clear = clear
        return inst

    async def send_to(self, destination, *args, **kwargs):
        await self._before_send()
        self.remove_item(self.join_arena_button)
        message = await destination.send(
            *args,
            view=self,
            content=f"Select a character for {destination.guild.get_member(self.player.id).display_name}",
        )
        self.message = message
        return message

    def __init__(self, bot: G0T0Bot):
        super().__init__(bot)

    @discord.ui.select(
        placeholder="Select a character to join arena",
        row=1,
        custom_id="character_select",
    )
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        arena = await self.bot.get_arena(interaction.channel.id)
        character = await self.bot.get_character(char.values[0])

        if not self.player:
            self.player = await self.bot.get_player(
                character.player_id, interaction.guild.id
            )

        if (
            character.player_id != interaction.user.id
            and interaction.user.id != arena.host_id
            and interaction.user.id != self.owner_id
        ):
            raise G0T0Error("Thats not your character")

        await self.player.add_to_arena(interaction, character, arena)
        if self.clear:
            await self.clear_timeout()
        else:
            await self.defer_to(CharacterArenaViewUI, interaction)

    @discord.ui.button(
        label="Join Arena",
        style=discord.ButtonStyle.primary,
        custom_id="join_arena_button",
    )
    async def join_arena_button(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        arena = await self.bot.get_arena(interaction.channel.id)

        if arena is None:
            raise ArenaNotFound()

        if interaction.user.id == arena.host_id:
            raise G0T0Error("You're already hosting this arena.")

        self.player = await self.bot.get_player(
            interaction.user.id, interaction.guild.id
        )

        if not self.player.characters:
            raise CharacterNotFound(self.player.member)
        elif len(self.player.characters) == 1:
            await self.player.add_to_arena(
                interaction, self.player.characters[0], arena
            )
        else:
            await self.defer_to(ArenaCharacterSelect, interaction)

        await self.on_timeout()

    async def _before_send(self):
        char_list = []
        for char in self.player.characters:
            char_list.append(
                discord.SelectOption(label=f"{char.name}", value=f"{char.id}")
            )
        self.character_select.__setattr__(
            "placeholder",
            f"{self.bot.get_guild(self.player.guild_id).get_member(self.player.id).display_name} select a character to join arena",
        )
        self.character_select.options = char_list


class ArenaRequest(InteractiveView):
    __menu_copy_attrs__ = ("bot", "post", "guild")
    bot: G0T0Bot
    post: ArenaPost
    guild: PlayerGuild

    async def get_content(self):
        return {"content": "", "embed": ArenaPostEmbed(self.post)}


class ArenaRequestCharacterSelect(ArenaRequest):
    character: PlayerCharacter = None

    @classmethod
    def new(cls, bot: G0T0Bot, player: Player, post: ArenaPost = None):
        inst = cls(owner=player.member)
        inst.bot = bot
        inst.post = post or ArenaPost(player, [])
        return inst

    async def _before_send(self):
        if len(self.post.player.characters) == 1:
            self.remove_item(self.character_select)
            self.remove_item(self.queue_character)
            self.remove_item(self.remove_character)
        else:
            char_list = []

            for char in self.post.player.characters:
                char_list.append(
                    discord.SelectOption(
                        label=f"{char.name}",
                        value=f"{char.id}",
                        default=(
                            True
                            if self.character and char.id == self.character.id
                            else False
                        ),
                    )
                )

            self.character_select.options = char_list

            self.queue_character.disabled = False if self.character else True
            self.remove_character.disabled = False if self.character else True
            self.next_application.disabled = (
                False if len(self.post.characters) > 0 else True
            )

        if (
            self.post.player.guild.member_role
            and self.post.player.guild.member_role not in self.post.player.member.roles
        ):
            self.remove_item(self.arena_type_select)
        else:
            type_list = []
            for type in ArenaPostType:
                type_list.append(
                    discord.SelectOption(
                        label=f"{type.value}",
                        value=f"{type.name}",
                        default=True if self.post.type.name == type.name else False,
                    )
                )
            self.arena_type_select.options = type_list

    @discord.ui.select(
        placeholder="Select an arena type to join", row=1, custom_id="arena_type"
    )
    async def arena_type_select(
        self, type: discord.ui.Select, interaction: discord.Interaction
    ):
        self.post.type = ArenaPostType[type.values[0]]
        await self.refresh_content(interaction)

    @discord.ui.select(
        placeholder="Select a character to join arena",
        row=2,
        custom_id="character_select",
    )
    async def character_select(
        self, char: discord.ui.Select, interaction: discord.Interaction
    ):
        character = await self.bot.get_character(char.values[0])

        if (
            character.player_id != interaction.user.id
            and interaction.user.id != self.owner.id
        ):
            raise G0T0Error("Thats not your character")

        self.character = character

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Add", style=discord.ButtonStyle.primary, custom_id="add_character", row=3
    )
    async def queue_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.post.type.name != "BOTH" and not self.post.player.can_join_arena(
            self.bot.compendium.get_object(ArenaType, self.post.type.name),
            self.character,
        ):
            raise G0T0Error(
                f"{self.character.name} can't queue up for another {self.post.type.name.lower()} arena."
            )

        if self.character.id not in [c.id for c in self.post.characters]:
            self.post.characters.append(self.character)

        await self.refresh_content(interaction)

    @discord.ui.button(
        label="Remove",
        style=discord.ButtonStyle.red,
        custom_id="remove_character",
        row=3,
    )
    async def remove_character(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.character.id in [c.id for c in self.post.characters]:
            char = next(
                (c for c in self.post.characters if c.id == self.character.id), None
            )
            self.post.characters.remove(char)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary, row=4)
    async def next_application(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.post.type.name != "BOTH":
            for character in self.post.characters:
                if not self.post.player.can_join_arena(
                    self.bot.compendium.get_object(ArenaType, self.post.type.name),
                    character,
                ):
                    raise G0T0Error(
                        f"{character.name} can't queue up for another {self.post.type.name.lower()} arena.\nPlease update and try to resubmit"
                    )

        if await ArenaPostEmbed(self.post).build():
            await interaction.respond("Request Submitted!", ephemeral=True)
        else:
            await interaction.respond("Something went wrong", ephemeral=True)

        await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=4)
    async def exit_application(
        self, _: discord.ui.Button, interaction: discord.Interaction
    ):

        if self.post.message:
            await self.post.message.clear_reactions()

        await self.on_timeout()
