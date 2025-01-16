import discord
from discord import Member, Role


async def update_dm(member: Member, category_premissions: dict, role: Role, adventure_name: str,
                    remove: bool = False) -> dict:
    if remove:
        if role in member.roles:
            await member.remove_roles(role, reason=f"Removed from adventure {adventure_name}")
        del category_premissions[member]
    else:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Creating/Modifying adventure {adventure_name}")
        category_premissions[member] = discord.PermissionOverwrite(manage_messages=True)
    
    return category_premissions


