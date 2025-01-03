from typing import Type

import discord

from Resolute.bot import G0T0Bot
from Resolute.helpers import (add_player_to_arena, build_arena_post, get_arena,
                              get_character, get_player, get_player_arenas)
from Resolute.models.embeds.arenas import ArenaPostEmbed
from Resolute.models.objects.arenas import ArenaPost
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import (ArenaNotFound,
                                                CharacterNotFound, G0T0Error)
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView


class ArenaView(discord.ui.View):
    __menu_copy_attrs__ = ("bot", "player")
    bot: G0T0Bot
    player: Player = None

    def __init__(self, bot: G0T0Bot):
        super().__init__(timeout=None)
        self.bot = bot

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
    
    async def defer_to(self, view_type: Type["ArenaView"], interaction: discord.Interaction, stop=True):
        view = view_type.from_menu(self)
        if stop:
            self.stop()
        await view._before_send()
        await view.refresh_content(interaction)

    
    async def refresh_content(self, interaction: discord.Interaction, **kwargs):
        await self._before_send()
        if interaction.response.is_done():
            arena = await get_arena(self.bot, interaction.channel.id)
            message: discord.Message = await interaction.channel.fetch_message(arena.pin_message_id)
            await message.edit(view=self, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **kwargs)

class CharacterArenaViewUI(ArenaView):
    @classmethod
    def new(cls, bot: G0T0Bot):
        inst = cls(bot=bot)
        return inst
    
    @discord.ui.button(label="Join Arena", style=discord.ButtonStyle.primary, custom_id="join_arena_button")
    async def join_arena_button(self, _: discord.ui.Button, interaction: discord.Interaction):
        arena = await get_arena(self.bot, interaction.channel.id)

        if arena is None or arena.type.value != "CHARACTER":
            raise ArenaNotFound()
        
        if interaction.user.id == arena.host_id:
            raise G0T0Error("You're already hosting this arena.")
        
        self.player = await get_player(self.bot, interaction.user.id, interaction.guild.id)

        if not self.player.characters:
            raise CharacterNotFound(self.player.member)
        elif len(self.player.characters) == 1:
            await add_player_to_arena(self.bot, interaction, self.player, self.player.characters[0], arena)
        else:
            await self.defer_to(ArenaCharacterSelect, interaction)

        await self.refresh_content(interaction)
    
class ArenaCharacterSelect(ArenaView):
    owner_id: int = None

    @classmethod
    def new(cls, bot: G0T0Bot, player: Player, owner_id: int = None):
        inst = cls(bot=bot)
        inst.player = player
        inst.owner_id = owner_id
        return inst
    
    async def send_to(self, destination, *args, **kwargs):
        await self._before_send()
        self.remove_item(self.join_arena_button)
        message = await destination.send(*args, view=self, content=f"Select a character for {destination.guild.get_member(self.player.id).display_name}")
        self.message = message
        return message
    
    def __init__(self, bot: G0T0Bot):
        super().__init__(bot)            

    @discord.ui.select(placeholder="Select a character to join arena", row=1, custom_id="character_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        arena = await get_arena(self.bot, interaction.channel.id)
        character = await get_character(self.bot, char.values[0])

        if not self.player:
            self.player = await get_player(self.bot, character.player_id, interaction.guild.id)

        if character.player_id != interaction.user.id and interaction.user.id != arena.host_id and interaction.user.id != self.owner_id:
            raise G0T0Error("Thats not your character")

        await add_player_to_arena(self.bot, interaction, self.player, character, arena)

        await self.defer_to(CharacterArenaViewUI, interaction)

    @discord.ui.button(label="Join Arena", style=discord.ButtonStyle.primary, custom_id="join_arena_button")
    async def join_arena_button(self, _: discord.ui.Button, interaction: discord.Interaction):
        arena = await get_arena(self.bot, interaction.channel.id)

        if arena is None or arena.type.value != "CHARACTER":
            raise ArenaNotFound()

        if interaction.user.id == arena.host_id:
            raise G0T0Error("You're already hosting this arena.")
        
        self.player = await get_player(self.bot, interaction.user.id, interaction.guild.id)

        if not self.player.characters:
            raise CharacterNotFound(self.player.member)
        elif len(self.player.characters) == 1:
            await add_player_to_arena(self.bot, interaction, self.player, self.player.characters[0], arena)
        else:
            await self.defer_to(ArenaCharacterSelect, interaction)

        await self.on_timeout()

    async def _before_send(self):
        char_list = []
        for char in self.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{char.id}"))
        self.character_select.__setattr__("placeholder", f"{self.bot.get_guild(self.player.guild_id).get_member(self.player.id).display_name} select a character to join arena")
        self.character_select.options = char_list

class ArenaRequest(InteractiveView):
    __menu_copy_attrs__ = ("bot", "post")   
    bot: G0T0Bot
    post: ArenaPost

    async def get_content(self):
        return {"content": "", "embed": ArenaPostEmbed(self.post)}
    
    
class ArenaRequestCharacterSelect(ArenaRequest):
    character: PlayerCharacter = None

    @classmethod
    def new(cls, bot: G0T0Bot, owner: discord.Member, player: Player, post: ArenaPost = None):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.post = post or ArenaPost(player, [])
        inst.character = None
        return inst

    async def _before_send(self):
        char_list = []
        for char in self.post.player.characters:
            char_list.append(discord.SelectOption(label=f"{char.name}", value=f"{char.id}", default=True if self.character and char.id == self.character.id else False))
        self.character_select.options = char_list

        self.queue_character.disabled = False if self.character else True
        self.remove_character.disabled = False if self.character else True
        self.next_application.disabled = False if len(self.post.characters) > 0 else True


    @discord.ui.select(placeholder="Select a character to join arena", row=1, custom_id="character_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        character = await get_character(self.bot, char.values[0])
 
        if character.player_id != interaction.user.id and interaction.user.id != self.owner.id:
            raise G0T0Error("Thats not your character")
        
        self.character = character
        
        await self.refresh_content(interaction)
    
    @discord.ui.button(label="Add", style=discord.ButtonStyle.primary, custom_id="add_character", row=2)
    async def queue_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        arenas = await get_player_arenas(self.bot, self.post.player)
        add = True

        for arena in arenas:
            if self.character.id in arena.characters and arena.completed_phases < arena.tier.max_phases-1:
                add = False
                await interaction.channel.send("Character already in a new arena.", delete_after=5)

        if self.character.id not in [c.id for c in self.post.characters] and add:
            self.post.characters.append(self.character)
            
        await self.refresh_content(interaction)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red, custom_id="remove_character", row=2)
    async def remove_character(self, _: discord.ui.Button, interaction: discord.Interaction):
        if self.character.id in [c.id for c in self.post.characters]:
            char = next((c for c in self.post.characters if c.id == self.character.id), None)
            self.post.characters.remove(char)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary, row=3)
    async def next_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        if await build_arena_post(interaction, self.bot, self.post):
            await interaction.respond("Request Submitted!", ephemeral=True)
        else:
            await interaction.respond("Something went wrong", ephemeral=True)

        await self.on_timeout()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, row=3)
    async def exit_application(self, _: discord.ui.Button, interaction: discord.Interaction):
        await self.on_timeout()

                
    
