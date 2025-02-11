

import logging
import re

import discord
from discord.ext import commands

from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers.general_helpers import (get_selection, is_admin,
                                              split_content)
from Resolute.helpers.messages import get_player_from_say_message
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.enum import WebhookType
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.objects.npc import NPC
from Resolute.models.objects.players import Player

log = logging.getLogger(__name__)

class G0T0Webhook(object):
    """
    A class to handle webhook interactions for the G0-T0 Resolute project.
    Attributes:
        player (Player): The player associated with the webhook.
        ctx (ApplicationContext | commands.Context): The context of the application or command.
        type (WebhookType): The type of webhook.
        npc (NPC): The NPC associated with the webhook, if any.
        character (PlayerCharacter): The player character associated with the webhook, if any.
        content (str): The content of the webhook message.
    Methods:
        __init__(ctx: ApplicationContext | commands.Context, type: WebhookType, **kwargs):
            Initializes the G0T0Webhook instance with the given context and type.
        run():
            Executes the webhook logic based on its type and context.
        _get_reply_player() -> Player:
            Retrieves the player who is being replied to, if any.
        _find_character_by_name(name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
            Finds characters by name from a list of player characters.
        _handle_character_mention():
            Handles character mentions within the webhook content.
        _get_npc_from_guild():
            Retrieves an NPC from the guild based on the invoked command.
        _get_npc_from_adventure(adventure: Adventure):
            Retrieves an NPC from an adventure based on the invoked command.
        is_authorized(npc):
            Checks if the player is authorized to interact with the given NPC.
    """

    player: Player = None
    ctx: discord.ApplicationContext | commands.Context
    type: WebhookType

    npc: NPC = None
    character: PlayerCharacter = None
    content: str = None

    def __init__(self, ctx: discord.ApplicationContext|commands.Context, type: WebhookType, **kwargs):
        self.ctx = ctx
        self.type = type


    async def run(self) -> None:
        self.player = await self.ctx.bot.get_player(self.ctx.author.id, self.ctx.guild.id)

        if self.type == WebhookType.say:
            self.content = self.ctx.message.content[5:]

            if self.content == "" or self.content.lower() == ">say":
                return

            if not self.player.characters:
                raise CharacterNotFound(self.player.member)
            
            if match := re.match(r"^(['\"“”])(.*?)['\"“”]", self.content):
                search = match.group(2)
                self.character = next((c for c in self.player.characters if search.lower() in c.name.lower()), None)
                if self.character:
                    self.content = re.sub(r"^(['\"“”])(.*?)['\"“”]\s*", "", self.content, count=1)
                
            if not self.character:
                self.character = await self.player.get_webhook_character(self.ctx.channel)    

        elif self.type ==WebhookType.npc:
            if (npc := self._get_npc_from_guild()) and await self.is_authorized(npc):
                self.npc = npc

        elif self.type == WebhookType.adventure:
            if self.ctx.channel.category and (adventure := await self.ctx.bot.get_adventure_from_category(self.ctx.channel.category.id)) and (npc := self._get_npc_from_adventure(adventure)):
                self.npc = npc

        if self.npc:
            self.content = self.ctx.message.content.replace(f">{npc.key}", "")
            await self.player.update_command_count("npc")

        if self.npc or self.character:
            await self._handle_character_mention()

            try:
                await self.ctx.message.delete()
            except:
                pass

            chunks = split_content(self.content)

            for chunk in chunks:
                try:
                    if self.npc:
                        await self.npc.send_webhook_message(self.ctx, chunk)
                    else:
                        await self.player.send_webhook_message(self.ctx, self.character, chunk)

                    if not self.player.guild.is_dev_channel(self.ctx.channel):
                        await self.player.update_post_stats(self.npc if self.npc else self.character, self.ctx.message, content=chunk)

                        if len(chunk) > ACTIVITY_POINT_MINIMUM:
                            await self.ctx.bot.update_player_activity_points(self.player)

                except:
                    await self.player.member.send(f"Error sending message in {self.ctx.channel.jump_url}. Try again.")
                    await self.player.member.send(f"```{chunk}```")
                    return
                
            if self.ctx.message.reference is not None and (reply_player := await self._get_reply_player()):
                try:
                    await reply_player.member.send(
                        f"{self.ctx.author} replied to your message in:\n"
                        f"{self.ctx.channel.jump_url}"
                    )
                except Exception as error:
                    log.error(f"Error replying to message {error}")
                                  

                        
                
    async def _get_reply_player(self) -> Player:
        if self.ctx.message.reference.resolved and self.ctx.message.reference.resolved.author.bot:
            return await get_player_from_say_message(self.ctx.bot, self.ctx.message.reference.resolved)


    def _find_character_by_name(self, name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
        direct_matches = [c for c in characters if c.name.lower() == name.lower()]

        # Prioritize main name first
        if not direct_matches:
            direct_matches = [c for c in characters if c.nickname and c.nickname.lower() == name.lower()]

        if not direct_matches:
            partial_matches = [c for c in characters if name.lower() in c.name.lower() or (c.nickname and name.lower() in c.nickname.lower())]
            return partial_matches

        return direct_matches

    async def _handle_character_mention(self) -> None:
        mentioned_characters = []

        if char_mentions := re.findall(r'{\$([^}]*)}', self.content):
            guild_characters = await self.player.guild.get_all_characters(self.ctx.bot.compendium)

            for mention in char_mentions:
                matches = self._find_character_by_name(mention, guild_characters)
                mention_char = None

                if len(matches) == 1:
                    mention_char = matches[0]
                elif len(matches) > 1:
                    choices = [f"{c.name} [{self.ctx.guild.get_member(c.player_id).display_name}]" for c in matches if self.ctx.guild.get_member(c.player_id)]

                    if choice := await get_selection(self.ctx, choices, True, True, f"Type your choice in {self.ctx.channel.jump_url}", True, f"Found multiple matches for `{mention}`"):
                        mention_char = matches[choices.index(choice)]

                if mention_char:
                    if mention_char not in mentioned_characters:
                        mentioned_characters.append(mention_char)
                    self.content = self.content.replace("{$" + mention + "}", f"[{mention_char.nickname if mention_char.nickname else mention_char.name}](<discord:///users/{mention_char.player_id}>)")

            for char in mentioned_characters:
                char: PlayerCharacter
                if member := self.ctx.guild.get_member(char.player_id):
                    try:
                        await member.send(f"{self.ctx.author.mention} directly mentioned `{char.name}` in:\n{self.ctx.channel.jump_url}")
                    except:
                        pass

    def _get_npc_from_guild(self) -> NPC:
        return next((npc for npc in self.player.guild.npcs if npc.key == self.ctx.invoked_with), None)
    
    def _get_npc_from_adventure(self, adventure: Adventure) -> NPC:
        if self.player.id in adventure.dms:
            return next((npc for npc in adventure.npcs if npc.key == self.ctx.invoked_with), None)
        return None
    
    async def is_authorized(self, npc) -> bool:
        user_roles = [role.id for role in self.player.member.roles]

        return bool(set(user_roles) & set(npc.roles)) or await is_admin(self.ctx)

    