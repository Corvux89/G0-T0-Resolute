**__DM Command Guide__**

__Adventure Settings:__
**Closing an adventure**
`/adventure close role:<role>`
-Closes out an adventure, and deletes the role. Use this before archiving to clean up the adventure. Can either be ran in an adventure channel to close that adventure out, or closes out the adventure with the specified role. Will only work if you are the DM or Council+.

**Adventure status**
`/adventure status role:<role>`
-If ran in an adventure channel will show the status for that adventure, otherwise the adventure for the role specified

__Player Settings:__
**Adding a player to your adventure:**
`/adventure add <player_1> <player_2> <player_3> <player_4> <player_5> <player_6> <player_7> <player_8>`
-At least 1 player must be specified.

**Removing  a player from your adventure:**
`/adventure remove <player>`

__Channel Viewing:__
**Open/Hide a channel from the public:**
`/room view <view> <allow_post>`
-Example usage: 
**Opening a room for applications**
`/room view view:open allow_post:True`

**Making a room viewable**
`/room view view:open`

**Closing a room**
`/room view view:close`

__Room Settings:__
**Add a channel to your adventure:**
`/room add_room <room_name>`
-Spaces will become dashes and everything will be lowercase
-Example usage: `/room add_room Best Adventure Ever`

**Changing the name of a channel:**
`/room rename <name>`
-Changes the name of the channel this command is run in
-Spaces will become dashes and everything will be lowercase
-Example usage: `/room rename Bestest Adventure Ever`

**Changing the position of a channel**
`/room move <position>`
-Moves the current channel within the adventure category. This may make the channel list jittery for a moment, so please use this command sparingly.
Positions:
• `top`: Makes this the top channel of the category 
• `up`: Moves the channel up by one step. 
• `down`: Moves the channel down by one step. 
• `bot`: Makes this the bottom channel of the category. 
- Example usage 1: `/room move top`
- Example usage 2: `/room move down`

**Rewards**
`/adventure reward <cc>`
-Logs CC for the players and CC + 25% for DM's
-Example usage: `/adventure reward cc:7`
Will log 7 CC's for players and 9 for DM's.