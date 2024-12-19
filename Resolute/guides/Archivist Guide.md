# Commands
## Style
`/command name <required parameter> [optional parameter: {default value}]`

## Logs
If something is logged by accident, an admin can null the log if needed (Right-click/long-press, `Apps`, `Null`)

### Roleplay
Right-click/long-press on the summary post, go to `Apps`, then `Approve`. Clarification prompts will come up as needed.

or 

`/log rp <member>`: Logs a completed RP for the specific player.
    **Example Usage:** `/log rp player:@Luke#1234`

`/log snapshot <member>`: Logs a completed Snapshot for the specific player.;
    **Example Usage:** `/log snapshot player:@Luke1234`

### Bonuses
`/log bonus <member> <reason> [cc] [credits]`: For a player who has gone above and beyond. This grants bonus credis and/or chain codes and does not count against weekly limits.
`reason` - The reason for granting the bonus. Quotes are not needed
`cc`: Optional - Amount of chain codes to give. Defaults to 0 if not specified
`credits`: Optional - Amount of credits to give. Defaults to 0 if not specified
**Example Usage:** `/log bonus player:@Luke#1234 reason:Kissing  a girl cc:1`

### Market
Right-click/long press on the transaction request, go to `Apps`, then `Approve`. It will log the transaction as long as it hasn't been denied by admins (❌)

As a backup if things go wrong:
`/log buy <member> <item> <cost> [currency: {Credits}]`: Logs a transaction of the player buying an item. The cost is **subtracted** from the player’s appropriate currency amounts.
`item` - The item name. Be as specific as possible. Quotes are not needed.
`cost` - The purchased item’s cost. Default is Credits, unless ‘currency’ is switched to ‘CC’
`currency` - The currency the purchase is in. Default is Credits.
**Example Usage:** `/log buy player:@Carric#4590 item:Family Therapy cost:200` or if using Chain Codes as currency `/log buy player:@Luke#1234 item:Family Therapy cost:2 currency:CC`

`/log sell <member> <item> <cost> [currency: {Credits}]`: Logs a transaction of the player selling an item. The cost is **added** to the player’s appropriate currency amount. 
`item` - The item name. Be as specific as possible. Quotes are not needed.
`cost` - The purchased item’s cost. Default is Credits, unless ‘currency’ is switched to ‘CC’
`currency` - The currency the purchase is in. Default is Credits.
**Example Usage:** `/log sell player:@Luke#1234 item:Father's day gift cost:200` or if using Chain Codes as currency ‘/log sell player:@Luke#1234 item:Father's day gift cost:2 currency:CC’

### Misc.
`/log get_history <member> [num_logs: {5}]`: Displays a log history for a player
`num_logs` - The number of logs to display. Min 1, Max 20, Default 5

## Character Management
`/character_admin manage <member>` - Manage a character. This command is where you will create characters, inactivate (if you have ability), level characters, add/remove renown, reroll, and generally anything else needed to manage a player character

## Adventure NPCS
`/adventure manage [adventure_role] [adventure_category]` can be used to setup new Adventure NPC's or modify existing ones if they need an avatar URL setup