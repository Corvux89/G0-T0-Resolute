
from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import get_webhook
from Resolute.models.embeds.players import RPPostEmbed
from Resolute.models.objects.players import (Player, RPPost)


async def manage_player_roles(bot: G0T0Bot, player: Player, reason: str = None) -> None:
    # Primary Role handling
    if player.highest_level_character and player.highest_level_character.level >= 3:
        if player.guild.member_role and player.guild.member_role not in player.member.roles:
            await player.member.add_roles(player.guild.member_role, reason=reason)

    # Character Tier Roles
    if player.guild.entry_role:
        if player.has_character_in_tier(bot.compendium, 1):
            if player.guild.entry_role not in player.member.roles:
                await player.member.add_roles(player.guild.entry_role, reason=reason)
        elif player.guild.entry_role in player.member.roles:
            await player.member.remove_roles(player.guild.entry_role, reason=reason)

    if player.guild.tier_2_role:
        if player.has_character_in_tier(bot.compendium, 2):
            if player.guild.tier_2_role not in player.member.roles:
                await player.member.add_roles(player.guild.tier_2_role, reason=reason)
        elif player.guild.tier_2_role in player.member.roles:
            await player.member.remove_roles(player.guild.tier_2_role, reason=reason)
    
    if player.guild.tier_3_role:
        if player.has_character_in_tier(bot.compendium, 3):
            if player.guild.tier_3_role not in player.member.roles:
                await player.member.add_roles(player.guild.tier_3_role, reason=reason)
        elif player.guild.tier_3_role in player.member.roles:
            await player.member.remove_roles(player.guild.tier_3_role, reason=reason)

    if player.guild.tier_4_role:
        if player.has_character_in_tier(bot.compendium, 4):
            if player.guild.tier_4_role not in player.member.roles:
                await player.member.add_roles(player.guild.tier_4_role, reason=reason)
        elif player.guild.tier_4_role in player.member.roles:
            await player.member.remove_roles(player.guild.tier_4_role, reason=reason)

    if player.guild.tier_5_role:
        if player.has_character_in_tier(bot.compendium, 5):
            if player.guild.tier_5_role not in player.member.roles:
                await player.member.add_roles(player.guild.tier_5_role, reason=reason)
        elif player.guild.tier_5_role in player.member.roles:
            await player.member.remove_roles(player.guild.tier_5_role, reason=reason)

    if player.guild.tier_6_role:
        if player.has_character_in_tier(bot.compendium, 6):
            if player.guild.tier_6_role not in player.member.roles:
                await player.member.add_roles(player.guild.tier_6_role, reason=reason)
        elif player.guild.tier_6_role in player.member.roles:
            await player.member.remove_roles(player.guild.tier_6_role, reason=reason)

    
async def build_rp_post(player: Player, posts: list[RPPost], message_id: int = None) -> bool:
    if player.guild.rp_post_channel:
        try:
            webhook = await get_webhook(player.guild.rp_post_channel)
            if message_id:
                await webhook.edit_message(message_id, embed=RPPostEmbed(player, posts))
            else:
                await webhook.send(username=player.member.display_name, avatar_url=player.member.display_avatar.url,
                                    embed=RPPostEmbed(player, posts))
        except:
            return False
        return True
    return False