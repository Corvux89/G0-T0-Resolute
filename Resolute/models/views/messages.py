

import discord
from Resolute.bot import G0T0Bot
from Resolute.constants import APPROVAL_EMOJI
from Resolute.helpers.logs import create_log
from Resolute.helpers.players import get_player
from Resolute.models.categories.categories import Activity
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.characters import PlayerCharacter
from Resolute.models.objects.exceptions import CharacterNotFound
from Resolute.models.objects.players import Player
from Resolute.models.views.base import InteractiveView

class LogMap(object):
    player: Player
    character: PlayerCharacter = None

    def __init__(self, player, **kwargs):
        self.player = player
        self.character = kwargs.get('character')


class MessageLog(InteractiveView):
    __menu_copy_attrs__ = ("bot", "msg", "activity")
    bot: G0T0Bot
    msg: discord.Message
    activity: Activity = None
    members: list[LogMap] = []

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        try:
            await self.message.delete()
        except discord.HTTPException:
            pass

class MessageLogUI(MessageLog):
    @classmethod
    async def new(cls, bot: G0T0Bot, owner: discord.Member, message: discord.Message):
        inst = cls(owner=owner)
        inst.bot = bot
        inst.msg = message
        inst.members = []

        for member in message.mentions:
            player = await get_player(bot, member.id, owner.guild.id)

            if len(player.characters) == 0:
                raise CharacterNotFound(player.member)

            inst.members.append(LogMap(player, character=player.characters[0] if len(player.characters) == 1 else None))
        return inst
    
    async def _before_send(self):
        act_list = [
            discord.SelectOption(label="RP", value="RP", default=True if self.activity and self.activity.value == "RP" else False),
            discord.SelectOption(label="Snapshot", value="SNAPSHOT", default=True if self.activity and self.activity.value == "SNAPSHOT" else False)
        ]
        self.activity_select.options = act_list

        if self.activity:
                self.remove_item(self.activity_select)


                if member := next((c for c in self.members if not c.character), None):
                    if self.get_item("character_select") is None:
                        self.add_item(self.character_select)

                    self.log.disabled = True

                    chars = [discord.SelectOption(label=f"{c.name}", value=f"{c.id}") for c in member.player.characters]
                    self.character_select.placeholder = f"Select a character for {member.player.member.display_name}"
                    self.character_select.options = chars
                else:
                    self.log.disabled = False
                    self.remove_item(self.character_select)
            
        else:
            self.remove_item(self.character_select)
            self.log.disabled = True

    @discord.ui.select(placeholder="Select a log type", custom_id="activity_select")
    async def activity_select(self, act: discord.ui.Select, interaction: discord.Interaction):
        self.activity = self.bot.compendium.get_activity(act.values[0])
        await self.refresh_content(interaction)

    @discord.ui.select(placeholder="Select a log character", custom_id="character_select")
    async def character_select(self, char: discord.ui.Select, interaction: discord.Interaction):
        if member := next((c for c in self.members if not c.character), None):
            member.character = next((c for c in member.player.characters if c.id == int(char.values[0])), None)
        await self.refresh_content(interaction)

    @discord.ui.button(label="Log", style=discord.ButtonStyle.primary, row=2)
    async def log(self, _: discord.ui.Button, interaction: discord.Interaction):
        for member in self.members:
            log_entry = await create_log(self.bot, self.owner, self.activity, member.player,
                                         character=member.character)
            
            await interaction.channel.send(embed=LogEmbed(log_entry, self.owner, member.player.member, member.character))

        await self.msg.add_reaction(APPROVAL_EMOJI[0])
        await self.on_timeout()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def exit(self, *_):
        await self.on_timeout()
