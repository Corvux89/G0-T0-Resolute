# G0T0 Bot Version 2.0 DEV Plan

## Databse Updates

### `c_activity`
:white_check_mark: Add `MOD_CHARACTER` activity to use for inactivation and updates to track character modifications
```sql
INSERT INTO public.c_activity
(id, value, cc, diversion)
VALUES(21, 'MOD_CHARACTER', NULL, false);
```

### `guilds`
:white_check_mark: Add `max_characters` (int4) column to track max number of allowed characters on the server
:white_check_mark: Add `div_limit` (int4) column to track diversion CC limits for the server
:white_check_mark: Add `reset_message` (varchar) column to set the reset announcement description
:white_check_mark: Add `weekly_announcement` (_varchar) column to set a additional field(s) in the announcment embed
:white_check_mark: Add a `server_date` (int4) column to track server date
:white_check_mark: Add a `first_character_message` (varchar) Column to say when first character is made for a player
:white_check_mark: Add a 'epoch_notation' (varchar) Column

```sql
ALTER TABLE public.guilds
ADD COLUMN max_characters int4 DEFAULT 1 NOT NULL,
ADD COLUMN div_limit int4 DEFAULT 10 NOT NULL,
ADD COLUMN reset_message varchar NULL,
ADD COLUMN weekly_announcement _varchar NULL,
ADD COLUMN first_character_message varchar NULL,
ADD COLUMN epoch_notation varchar NULL,
ADD COLUMN server_date int4 NULL;
```

### `players`
:white_check_mark: Add `cc` (int4) and `div_cc` (int4) columns
:white_check_mark: Backfill `cc` and `div_cc` from current active characters

```sql
ALTER TABLE public.players
ADD COLUMN cc int4 DEFAULT 0 NOT NULL,
ADD COLUMN div_cc int4 DEFAULT 0 NOT NULL,
```

```sql
insert into players as p (id, guild_id, handicap_amount, cc, div_cc)
select c.player_id, '831690964140687440', 0, c.cc, c.div_cc
from "characters" as c
where c.active = true
on conflict (id, guild_id) 
do update
set (cc, div_cc) = (SELECT c.cc, c.div_cc from "characters" as c where c.player_id = p.id and c.active=true)
```

### `characters`
:white_check_mark:  Deprecate `cc`, `div_cc` columns and move them to the `players` table

```sql
ALTER TABLE characters
DROP COLUMN cc,
DROP COLUMN div_cc;
```

### `adventures`
:white_check_mark: Track character ID's in an adventure
```sql
ALTER TABLE public.adventures  ADD "characters" _int4 NULL;
```

### `arenas`
:white_check_mark: Track character ID's in an arena
```sql
ALTER TABLE public.arenas ADD "characters" _int4 NULL;
```

### `log`
:white_check_mark: Add `player_id` (int8) column to track player ID (Not Nullable)
:white_check_mark: Allow `character_id` to be nullable
:white_check_mark: Add `MOD_CHARACTER` lo

```sql
UPDATE log
SET player_id  = characters.player_id
FROM characters
WHERE log.character_id = characters.id;
```

### `c_level_caps`
Delete

### `ref_server_calendar`
```sql
CREATE TABLE public.ref_server_calendar (
	day_start int4 NOT NULL,
	day_end int4 NOT NULL,
	display_name varchar NOT NULL,
	guild_id int8 NULL,
	CONSTRAINT server_calendar_pk PRIMARY KEY (day_start)
);
```
```sql
INSERT INTO public.ref_server_calendar (day_start,day_end,display_name,guild_id) VALUES
	 (1,5,'New Years Fete',831690964140687440),
	 (6,40,'01',831690964140687440),
	 (41,75,'02',831690964140687440),
	 (76,110,'03',831690964140687440),
	 (111,145,'04',831690964140687440),
	 (146,180,'05',831690964140687440),
	 (181,215,'06',831690964140687440),
	 (216,220,'Festival of Life',831690964140687440),
	 (221,255,'07',831690964140687440),
	 (256,290,'08',831690964140687440);
INSERT INTO public.ref_server_calendar (day_start,day_end,display_name,guild_id) VALUES
	 (291,325,'09',831690964140687440),
	 (326,330,'Festival of Stars',831690964140687440),
	 (330,365,'10',831690964140687440);
```

## Cog Updates
### Adventures
:white_check_mark: Update `/adventures` to show breakdown of adventures per characters
:white_check_mark: Update `/adventure add` to prompt user to select appropriate character if multiple characters found per player
:white_check_mark: Update `/adventure close`
:white_check_mark: Update `/adventure status`
:white_check_mark: Update `/adventure reward`
:white_check_mark: Create `/adventure manage` command for all the above

### Arenas && ~~Starship~~ Arenas
:white_check_mark: Update `/arena claim`
:white_check_mark: Update `/arena status`
:white_check_mark: Update `/arena add`
:white_check_mark: Update `/arena phase`

### Characters
:white_check_mark: Update `/get`
:white_check_mark: Merge ~~`/character_admin create`~~, ~~`/character_admin reroll`~~, ~~`/character_admin level`~~, ~~`/character_admin species`~~, ~~`/character_admin archetype`~~, ~~`/character_admin add_multiclass`~~, ~~`/character_admin remove_multiclass`~~, ~~`/character_admin inactivate`~~ into one `/character_admin manage` command
:pencil: Remove draft option from applications since caching to database
:white_check_mark: Add `!approve` blurb on first character creation
:pencil: Add `add_ship`, `upgrade_ship`, `modify_ship`, and `remove_ship` to `character_admin manage`
:pencil: Level up application
:pencil: New character applicaiton
:pencil: Edit application

### Events
:white_check_mark: Update `on_member_remove`
:pencil: Update `on_member_remove` to check arena board as well for cleanup

### Global Events
Need to repoint all helpers to do CC at a player level rather than character. 

### Guilds
:white_check_mark: Merged all setting commands to just a singular interactive `/guild settings` command. This reduces command overhead as well as improves visibility into various settings.
:penwhite_check_mark: Update `weekly_reset` to reset division CC's on players, and disperse stipends
:white_check_mark: Incorporate `div_limit` into `/guild settings`
:pencil: Add `/guild channel_archive` command to move a channel to an archive category, set permissions to read only
:pencil: Manage settings for `greeting`, ~~`reset_message`~~, ~~`weekly_announcement`~~, `first_character_message`, and ~~`server_date`~~
:white_check_mark: Add way to preview reset message

### Log
:pencil: Update `/log get_history`
:white_check_mark: Update `/log rp`
:white_check_mark: Update `/log bonus`
:white_check_mark: Update `/log null`
:white_check_mark: Update `/log buy`
:white_check_mark: Update `/log sell`
:white_check_mark: Update `/log convert`
:pencil: Update `/log stats`

### Dashboards
:pencil: Update

### Holdings
:pencil: Update

### Rooms
:white_check_mark: Update

## Misc
:pencil: Validate query utilization

## Post Live Tasks:
1. Update active arenas with characters
2. Update active adventures with characters