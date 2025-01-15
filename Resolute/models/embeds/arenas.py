from discord import Embed, ApplicationContext, Interaction, Color
from Resolute.constants import THUMBNAIL, ZWSP3
from Resolute.helpers.general_helpers import get_webhook
from Resolute.models.objects.applications import ArenaPost
from Resolute.models.objects.arenas import Arena

class ArenaStatusEmbed(Embed):
    def __init__(self, ctx: ApplicationContext | Interaction, arena: Arena):
        self.arena = arena
        self.ctx = ctx
        super().__init__(title=f"{arena.type.value.title()} Arena Status", color=Color.random())
        self.set_thumbnail(url=THUMBNAIL)

        self.description = f"**Tier**: {arena.tier.id}\n"\
                           f"**Completed Phases**: {arena.completed_phases} / {arena.tier.max_phases}"
        
        if arena.completed_phases == 0:
            self.description += f"\n\nUse the button below to join!"
        elif arena.completed_phases >= arena.tier.max_phases / 2:
            self.description += f"\nBonus active!"

        self.add_field(name=f"**Host**:",
                       value=f"{ZWSP3}- {ctx.guild.get_member(arena.host_id).mention}",
                       inline=False)
        
        if arena.player_characters:
            self.add_field(name="**Players**:",
                        value="\n".join([f"{ZWSP3}- [{c.level}] {c.name}{'*inactive*' if not c.active else ''} ({ctx.guild.get_member(c.player_id).mention})" for c in arena.player_characters]),
                        inline=False)
            
    async def update(self):
        message = await self.ctx.channel.fetch_message(self.arena.pin_message_id)
        
        if message:
            await message.edit(embed=self)
            
class ArenaPhaseEmbed(Embed):
    def __init__(self, ctx: ApplicationContext, arena: Arena, result: str):
        super().__init__(
            title=f"Phase {arena.completed_phases} Complete!",
            description=f"Complete phases: **{arena.completed_phases} / {arena.tier.max_phases}**",
            color=Color.random()
        )

        self.set_thumbnail(url=THUMBNAIL)

        bonus = (arena.completed_phases > arena.tier.max_phases / 2) and result == "WIN"

        field_str = [f"{ctx.guild.get_member(arena.host_id).mention or 'Player not found'}: 'HOST'"]

        for character in arena.player_characters:
            text = f"{character.name} ({ctx.guild.get_member(character.player_id).mention or 'Player not found'}): '{result}'{f', `BONUS`' if bonus else ''}"
            field_str.append(text)
        
        self.add_field(name="The following rewards have been applied:",
                       value="\n".join(field_str),
                       inline=False)
        
class ArenaPostEmbed(Embed):
    def __init__(self, post: ArenaPost):
        super().__init__(
            title=f"{post.type.value} Arena Request",
            color=Color.random()
        )
        self.post = post

        self.set_thumbnail(url=post.player.member.avatar.url)

        char_str = "\n\n".join([f'[{post.characters.index(c)+1}] {c.inline_class_description()}' for c in post.characters])

        self.add_field(name="Character Priority",
                       value=char_str,
                       inline=False)
        
        self.set_footer(text=f"{post.player.member.id}")

    async def build(self) -> bool:
        if self.post.player.guild.arena_board_channel:
            webhook = await get_webhook(self.post.player.guild.arena_board_channel)
            if self.post.message:
                await webhook.edit_message(self.post.message.id, embed=self)
            else:
                await webhook.send(username=self.post.player.member.display_name,
                                   avatar_url=self.post.player.member.display_avatar.url,
                                   embed=self)
            return True
        return False