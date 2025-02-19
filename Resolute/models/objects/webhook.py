

import logging
import re

import discord
from discord.ext import commands

from Resolute.bot import G0T0Context
from Resolute.constants import ACTIVITY_POINT_MINIMUM
from Resolute.helpers.general_helpers import (get_selection, is_admin, is_staff,
                                              split_content)
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.enum import WebhookType
from Resolute.models.objects.exceptions import CharacterNotFound, Unauthorized
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
    ctx: commands.Context | G0T0Context
    type: WebhookType

    npc: NPC = None
    character: PlayerCharacter = None
    content: str = None
    message: discord.Message = None
    adventure: Adventure = None

    def __init__(self, ctx: commands.Context | G0T0Context, **kwargs):
        self.ctx = ctx
        self.type = kwargs.get('type', WebhookType.say)

        if hasattr(self.ctx, "player") and self.ctx.player:
            self.player = self.ctx.player

        self.message = kwargs.get('message', ctx.message)
        self.adventure = kwargs.get('adventure')


    async def send(self) -> None:
        # Maker sure we have required attributes
        if not self.player and self.ctx.player:
            self.player = self.ctx.player
        else:
            self.player = await self.ctx.bot.get_player(self.ctx.author.id, self.ctx.guild.id)

        # >say
        if self.type == WebhookType.say:
            self.content = self.message.content[5:]

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
        
        # Guild NPC
        elif self.type ==WebhookType.npc:
            if npc := self.player.guild.get_npc(key=self.ctx.invoked_with):
                self.npc = npc

        # Adventure NPC
        elif self.type == WebhookType.adventure:
            if self.ctx.channel.category:
                if not self.adventure:
                    self.adventure = self.ctx.bot.get_adventure_from_category(self.ctx.channel.category.id)                  

                if self.adventure:
                    self.npc = self.adventure.get_npc(key=self.ctx.invoked_with)

        # Final Checks
        if self.npc and not await self.is_authorized():
            raise Unauthorized()

        if self.npc:
            self.content = self.message.content.replace(f">{npc.key}", "")
            await self.player.update_command_count("npc")

        if self.npc or self.character:
            await _handle_character_mentions(self)

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
                
            if self.message.reference is not None and (reply_player := await _get_reply_player(self)):
                try:
                    await reply_player.member.send(
                        f"{self.ctx.author} replied to your message in:\n"
                        f"{self.ctx.channel.jump_url}"
                    )
                except Exception as error:
                    log.error(f"Error replying to message {error}")

    async def edit(self, content: str) -> None:
        self.content = content
        if self.type == WebhookType.say:
            if hasattr(self.ctx, "player") and self.ctx.player and not self.player:
                self.player = self.ctx.player
            else:
                self.player = await self.ctx.bot.get_player(self.ctx.author.id, self.ctx.guild.id)

            await _handle_character_mentions(self)

            try:
                await self.player.edit_webhook_message(self.ctx, self.message.id, self.content)

                if not self.player.guild.is_dev_channel(self.ctx.channel):
                    await self.player.update_post_stats(self.character, self.message, retract=True)
                    await self.player.update_post_stats(self.character, self.message, content=self.content)

                    if len(self.content) <= ACTIVITY_POINT_MINIMUM and len(self.message.content) >= ACTIVITY_POINT_MINIMUM:
                        await self.ctx.bot.update_player_activity_points(self.player, False)
                    elif len(self.content) >= ACTIVITY_POINT_MINIMUM and len(self.message.content) <= ACTIVITY_POINT_MINIMUM:
                        await self.ctx.bot.update_player_activity_points(self.player)
            except:
                await self.player.member.send(f"Error editing message in {self.ctx.channel.jump_url}. Try again.")
                await self.player.member.send(f"```{self.content}```")
                return
        
    async def delete(self) -> None:
        if self.npc and not await self.is_authorized():
            raise Unauthorized()

        if not self.player.guild.is_dev_channel(self.ctx.channel):
            await self.player.update_post_stats(self.character if self.character else self.npc, self.message, retract=True)

            if len(self.message.content) >= ACTIVITY_POINT_MINIMUM:
                await self.ctx.bot.update_player_activity_points(self.player, False)            
        
        await self.message.delete()
    
    async def is_authorized(self) -> bool:
        if not self.npc:
            return False

        if self.type == WebhookType.npc:
            user_roles = [role.id for role in self.player.member.roles]

            return bool(set(user_roles) & set(self.npc.roles)) or await is_admin(self.ctx)
        
        elif self.type == WebhookType.adventure:
            if not self.adventure and self.ctx.channel.category:
                self.adventure = await self.bot.get_adventure_from_category(self.ctx.channel.category.id)

            if self.adventure:
                return self.player.id in self.adventure.dms or await is_staff(self.ctx)

        return False
    
    async def is_valid_message(self, **kwargs) -> bool:
        if not self.message.author.bot:
            return False
        
        if self.type == WebhookType.say:
            if kwargs.get('update_player', False):
                if (name := _get_player_name(self)) and (member := discord.utils.get(self.message.guild.members, display_name=name)):
                    self.player = await self.ctx.bot.get_player(member.id, member.guild.id)
                else:
                    return False

            if char_name := _get_char_name(self):
                for char in self.player.characters:
                    if char.name.lower() == char_name.lower():
                        self.character = char
                        return True
                    
        elif self.type == WebhookType.adventure:
            if self.ctx.channel.category:
                self.adventure = await self.ctx.bot.get_adventure_from_category(self.ctx.channel.category.id)

                if self.adventure and (npc := self.adventure.get_npc(name=self.message.author.name)):
                    self.npc = npc
                    return True
                    
        elif self.type == WebhookType.npc:
            if npc := self.player.guild.get_npc(name=self.message.author.name):
                self.npc = npc
                return True

        return False

# --------------------------- #
# Private Methods
# --------------------------- #

def _get_player_name(webhook: G0T0Webhook) -> str:
    try:
        player_name = webhook.message.author.name.split(' // ')[1:]
    except:
        return None
    
    return " // ".join(player_name)

def _get_char_name(webhook: G0T0Webhook) -> str:
    try:
        char_name = webhook.message.author.name.split(' // ')[0].split('] ', 1)[1].strip()
    except:
        return None
    
    return char_name

async def _get_reply_player(webhook: G0T0Webhook) -> Player:
    if webhook.message.reference.resolved and webhook.message.reference.resolved.author.bot:
        orig_webhook = G0T0Webhook(webhook.ctx, message=webhook.message.reference.resolved)

        if await orig_webhook.is_valid_message(update_player=True):
            return orig_webhook.player
        
def _find_character_by_name(name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
    direct_matches = [c for c in characters if c.name.lower() == name.lower()]

    # Prioritize main name first
    if not direct_matches:
        direct_matches = [c for c in characters if c.nickname and c.nickname.lower() == name.lower()]

    if not direct_matches:
        partial_matches = [c for c in characters if name.lower() in c.name.lower() or (c.nickname and name.lower() in c.nickname.lower())]
        return partial_matches

    return direct_matches

        
async def _handle_character_mentions(webhook: G0T0Webhook) -> None:
    mentioned_characters = []

    if char_mentions := re.findall(r'{\$([^}]*)}', webhook.content):
        guild_characters = await webhook.player.guild.get_all_characters(webhook.ctx.bot.compendium)

        for mention in char_mentions:
            matches = _find_character_by_name(mention, guild_characters)
            mention_char = None

            if len(matches) == 1:
                mention_char = matches[0]
            elif len(matches) > 1:
                choices = [f"{c.name} [{webhook.ctx.guild.get_member(c.player_id).display_name}]" for c in matches if webhook.ctx.guild.get_member(c.player_id)]

                if choice := await get_selection(webhook.ctx, choices, True, True, f"Type your choice in {webhook.ctx.channel.jump_url}", True, f"Found multiple matches for `{mention}`"):
                    mention_char = matches[choices.index(choice)]

            if mention_char:
                if mention_char not in mentioned_characters:
                    mentioned_characters.append(mention_char)
                webhook.content = webhook.content.replace("{$" + mention + "}", f"[{mention_char.nickname if mention_char.nickname else mention_char.name}](<discord:///users/{mention_char.player_id}>)")

        for char in mentioned_characters:
            char: PlayerCharacter
            if member := webhook.ctx.guild.get_member(char.player_id):
                try:
                    await member.send(f"{webhook.ctx.author.mention} directly mentioned `{char.name}` in:\n{webhook.ctx.channel.jump_url}")
                except:
                    pass
    