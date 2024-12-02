# Commands
## Style
`/command name <required parameter> [optional parameter: {default value}]`
## Logs
`/log rp <member>`: Logs a completed RP for the specific player.
    **Example Usage:** `/log rp player:@Luke#1234`

`/log snapshot <member>`: Logs a completed Snapshot for the specific player.;
    **Example Usage:** `/log snapshot player:@Luke1234`

`/log bonus <member> <reason> [cc] [credits]`: For a player who has gone above and beyond. This grants bonus credis and/or chain codes and does not count against weekly limits.
`reason` - The reason for granting the bonus. Quotes are not needed
`cc`: Optional - Amount of chain codes to give. Defaults to 0 if not specified
`credits`: Optional - Amount of credits to give. Defaults to 0 if not specified
**Example Usage:** `/log bonus player:@Luke#1234 reason:Kissing  a girl cc:1`

## Market
On market transactinos you can right-click/long-press and approve transactions as long as it hasn't been denied (❌ by admins)

`/log get_history <member> [num_logs: {5}]`: Displays a log history for a player
`num_logs` - The number of logs to display. Min 1, Max 20, Default 5

## Character Management
`/character_admin manage <member>` - Manage a character. This command is where you will create characters, inactivate (if you have ability), level characters, add/remove renown, reroll, and generally anything else needed to manage a player character

## Adventure NPS
`/adventure manage [adventure_role] [adventure_category]` can be used to setup new Adventure NPC's or modify existing ones if they need an avatar URL setup