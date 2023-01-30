import json
import os
from typing import Dict

# Bot Configuration Stuff
BOT_OWNERS = json.loads(os.environ["BOT_OWNERS"]) if "BOT_OWNERS" in os.environ else None
ADMIN_GUILDS = json.loads(os.environ["ADMIN_GUILDS"]) if "ADMIN_GUILDS" in os.environ else None
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEFAULT_PREFIX = os.environ.get("COMMAND_PREFIX", ">")
DEBUG_GUILDS = json.loads(os.environ["GUILD"]) if "GUILD" in os.environ else None
DASHBOARD_REFRESH_INTERVAL = float(os.environ.get("DASHBOARD_REFRESH_INTERVAL", 15))

# Database Stuff
DB_URL = os.environ.get("DATABASE_URL", "")

# Misc
THUMBNAIL = "https://cdn.discordapp.com/attachments/794989941690990602/972998353103233124/IMG_2177.jpg"
