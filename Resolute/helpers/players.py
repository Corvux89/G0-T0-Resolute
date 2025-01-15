
from Resolute.bot import G0T0Bot
from Resolute.helpers.general_helpers import get_selection, get_webhook
from Resolute.helpers.guilds import get_guild
from Resolute.models.embeds.players import RPPostEmbed
from Resolute.models.objects.exceptions import G0T0Error
from Resolute.models.objects.players import (Player, PlayerSchema, RPPost,
                                             get_player_query,
                                             upsert_player_query)


async def get_player(bot: G0T0Bot, player_id: int, guild_id: int, inactive: bool = False, ctx = None, lookup_only: bool = False) -> Player:
    async with bot.db.acquire() as conn:
        results = await conn.execute(get_player_query(player_id, guild_id))
        rows = await results.fetchall()

        if len(rows) == 0 and guild_id and not lookup_only:
            player = Player(id=player_id, guild_id=guild_id)
            results = await conn.execute(upsert_player_query(player))
            row = await results.first()
        elif lookup_only:
            return None
        elif len(rows) == 0 and not guild_id:
            if ctx:
                guilds = [g for g in bot.guilds if g.get_member(player_id)]

                if len(guilds) == 1:
                    row = None
                    player = Player(id=player_id, guild_id=guilds[0].id)
                    results = await conn.execute(upsert_player_query(player))
                    row = await results.first()
                elif len(guilds) > 1:
                    guild = await get_selection(ctx, guilds, True, True, None, False, "Which guild is the command for?\n")

                    if guild:
                        player = Player(id=player_id, guild_id=guild.id)
                        results = await conn.execute(upsert_player_query(player))
                        row = await results.first()
                    else:
                        raise G0T0Error("No guild selected.")
            else:
                raise G0T0Error("Unable to find player")
        else:
            if ctx:
                guilds = [bot.get_guild(r["guild_id"]).name for r in rows]
                guild = await get_selection(ctx, guilds, True, True, None, False, "Which guild is the command for?\n")
                row = rows[guilds.index(guild)]
            else:
                row = rows[0]
        

    player: Player = await PlayerSchema(bot, inactive).load(row)

    return player

async def manage_player_roles(bot: G0T0Bot, player: Player, reason: str = None) -> None:
    g = await get_guild(bot, player.guild_id)

    # Primary Role handling
    if player.highest_level_character and player.highest_level_character.level >= 3:
        if g.member_role and g.member_role not in player.member.roles:
            await player.member.add_roles(g.member_role, reason=reason)

    # Character Tier Roles
    if g.entry_role:
        if player.has_character_in_tier(bot, 1):
            if g.entry_role not in player.member.roles:
                await player.member.add_roles(g.entry_role, reason=reason)
        elif g.entry_role in player.member.roles:
            await player.member.remove_roles(g.entry_role, reason=reason)

    if g.tier_2_role:
        if player.has_character_in_tier(bot, 2):
            if g.tier_2_role not in player.member.roles:
                await player.member.add_roles(g.tier_2_role, reason=reason)
        elif g.tier_2_role in player.member.roles:
            await player.member.remove_roles(g.tier_2_role, reason=reason)
    
    if g.tier_3_role:
        if player.has_character_in_tier(bot, 3):
            if g.tier_3_role not in player.member.roles:
                await player.member.add_roles(g.tier_3_role, reason=reason)
        elif g.tier_3_role in player.member.roles:
            await player.member.remove_roles(g.tier_3_role, reason=reason)

    if g.tier_4_role:
        if player.has_character_in_tier(bot, 4):
            if g.tier_4_role not in player.member.roles:
                await player.member.add_roles(g.tier_4_role, reason=reason)
        elif g.tier_4_role in player.member.roles:
            await player.member.remove_roles(g.tier_4_role, reason=reason)

    if g.tier_5_role:
        if player.has_character_in_tier(bot, 5):
            if g.tier_5_role not in player.member.roles:
                await player.member.add_roles(g.tier_5_role, reason=reason)
        elif g.tier_5_role in player.member.roles:
            await player.member.remove_roles(g.tier_5_role, reason=reason)

    if g.tier_6_role:
        if player.has_character_in_tier(bot, 6):
            if g.tier_6_role not in player.member.roles:
                await player.member.add_roles(g.tier_6_role, reason=reason)
        elif g.tier_6_role in player.member.roles:
            await player.member.remove_roles(g.tier_6_role, reason=reason)

    
async def build_rp_post(bot: G0T0Bot, player: Player, posts: list[RPPost], message_id: int = None) -> bool:
    g = await get_guild(bot, player.guild_id)

    if g.rp_post_channel:
        try:
            webhook = await get_webhook(g.rp_post_channel)
            if message_id:
                await webhook.edit_message(message_id, embed=RPPostEmbed(player, posts))
            else:
                await webhook.send(username=player.member.display_name, avatar_url=player.member.display_avatar.url,
                                    embed=RPPostEmbed(player, posts))
        except:
            return False
        return True
    return False