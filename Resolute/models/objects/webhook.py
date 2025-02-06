

from enum import Enum
import re

from discord import ApplicationContext, Message, Webhook
from discord.ext import commands

from Resolute.helpers.general_helpers import get_selection, get_webhook, is_admin
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.objects.players import Player
from Resolute.models.objects.NPC import NPC

class WebhookType(Enum):
    npc = "npc"
    say = "say"


class G0T0Webhook(object):
    player: Player
    ctx: ApplicationContext | commands.Context
    type: WebhookType

    npc: NPC = None
    content: str = None
    webhook: Webhook = None


    async def __init__(self, ctx: ApplicationContext|commands.Context, type: WebhookType, **kwargs):
        self.ctx = ctx
        self.player = await self.ctx.bot.get_player(ctx.author.id, ctx.guild.id)
        self.type = type

        if type == WebhookType.say:
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

        elif type == WebhookType.npc:
            if npc := self._get_npc_from_guild() and self.is_authorized(npc):
                self.npc = npc
            elif self.ctx.channel.category and (adventure := await self.ctx.bot.get_adventure_from_category(self.ctx.channel.category.id)) and (npc := self._get_npc_from_adventure(adventure)):
                self.npc = npc

            if self.npc:
                self.content = self.ctx.message.content.replace(f">{npc.key}", "")
                await self.player.update_command_count("npc")
                self.webhook = await get_webhook(self.ctx.channel)

        
        if self.character or self.webhook:



    
    def _find_character_by_name(name: str, characters: list[PlayerCharacter]) -> list[PlayerCharacter]:
        direct_matches = [c for c in characters if c.name.lower() == name.lower()]

        # Prioritize main name first
        if not direct_matches:
            direct_matches = [c for c in characters if c.nickname and c.nickname.lower() == name.lower()]

        if not direct_matches:
            partial_matches = [c for c in characters if name.lower() in c.name.lower() or (c.nickname and name.lower() in c.nickname.lower())]
            return partial_matches
    
        return direct_matches

    async def _handle_character_mention(self):
        mentioned_characters = []

        if char_mentions := re.findall(r'{\$([^}]*)}', self.content):
            guild_characters = self.player.guild.get_all_characters(self.ctx.bot.compendium)

            for mention in char_mentions:
                matches = self._find_character_by_name(mention, guild_characters)
                mention_char = None

                if len(matches) == 1:
                    mention_char = matches[0]
                elif len(matches) > 1:
                    choices = [f"{c.name} [{self.ctx.guild.get_member(c.player_id).display_name}]" for c in matches]
                if choice := await get_selection(self.ctx, choices, True, True, f"Type your choice in {self.ctx.channel.jump_url}", True, f"Found multiple matches for `{mention}`"):
                    mention_char = matches[choices.index(choice)]

                if mention_char:
                    if mention_char not in mentioned_characters:
                        mentioned_characters.append(mention_char)
                    content = content.replace("{$" + mention + "}", f"[{mention_char.nickname if mention_char.nickname else mention_char.name}](<discord:///users/{mention_char.player_id}>)")

            for char in mentioned_characters:
                char: PlayerCharacter
                if member := self.ctx.guild.get_member(char.player_id):
                    try:
                        await member.send(f"{self.ctx.author.mention} directly mentioned `{char.name}` in:\n{self.ctx.channel.jump_url}")
                    except:
                        pass

        self.content = content

    def _get_npc_from_guild(self):
        return next((npc for npc in self.player.guild.npcs if npc.key == self.ctx.invoked_with), None)
    
    def _get_npc_from_adventure(self, adventure: Adventure):
        if self.player.id in adventure.dms:
            return next((npc for npc in adventure.npcs if npc.key == self.ctx.invoked_with), None)
        return None
    
    async def is_authorized(self, npc):
        user_roles = [role.id for role in self.player.member.roles]

        return bool(set(user_roles) & set(npc.roles)) or await is_admin(self.ctx)

    