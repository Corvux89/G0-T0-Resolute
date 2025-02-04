from discord import Member, PermissionOverwrite, Role


async def update_dm(member: Member, category_premissions: dict, role: Role, adventure_name: str,
                    remove: bool = False) -> dict:
    """
    Updates the Dungeon Master's (DM) roles and permissions for a specific adventure.
    Args:
        member (Member): The member whose roles and permissions are being updated.
        category_premissions (dict): A dictionary of category permissions to be updated.
        role (Role): The role to be added or removed from the member.
        adventure_name (str): The name of the adventure for logging purposes.
        remove (bool, optional): If True, the role will be removed from the member and permissions will be deleted. Defaults to False.
    Returns:
        dict: The updated category permissions dictionary.
    """
    if remove:
        if role in member.roles:
            await member.remove_roles(role, reason=f"Removed from adventure {adventure_name}")
        del category_premissions[member]
    else:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Creating/Modifying adventure {adventure_name}")
        category_premissions[member] = PermissionOverwrite(manage_messages=True)
    
    return category_premissions


