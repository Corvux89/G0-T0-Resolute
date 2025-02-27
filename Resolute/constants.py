import json
import os

# Bot Configuration Stuff
BOT_OWNERS = (
    json.loads(os.environ["BOT_OWNERS"]) if "BOT_OWNERS" in os.environ else None
)
ADMIN_GUILDS = (
    json.loads(os.environ["ADMIN_GUILDS"]) if "ADMIN_GUILDS" in os.environ else None
)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEFAULT_PREFIX = os.environ.get("COMMAND_PREFIX", ">")
DEBUG_GUILDS = json.loads(os.environ["GUILD"]) if "GUILD" in os.environ else None
DASHBOARD_REFRESH_INTERVAL = float(os.environ.get("DASHBOARD_REFRESH_INTERVAL", 15))
ERROR_CHANNEL = os.environ.get("ERROR_CHANNEL")

# Database Stuff
DB_URL = os.environ.get("DATABASE_URL", "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
PORT = int(os.getenv("PORT", 8080))

# Misc
THUMBNAIL = "https://cdn.discordapp.com/attachments/1069074273190285353/1070477277852340339/image.png"
DAYS_OF_WEEK = [
    ("None", "None"),
    ("Monday", "0"),
    ("Tuesday", "1"),
    ("Wednesday", "2"),
    ("Thursday", "3"),
    ("Friday", "4"),
    ("Saturday", "5"),
    ("Sunday", "6"),
]
CHANNEL_BREAK = "```\n​ \n```"
ZWSP3 = "\u200b \u200b \u200b "
APPROVAL_EMOJI = ["✅", "greencheck"]
DENIED_EMOJI = ["❌"]
NULL_EMOJI = ["◀️", "⏪"]
EDIT_EMOJI = ["📝", "✏️"]
ACTIVITY_POINT_MINIMUM = os.environ.get("ACTIVITY_POINT_MINIMUM", 250)

# Sheet Stuff
STAT_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

STAT_ABBREVIATIONS = ("str", "dex", "con", "int", "wis", "cha")

STAT_ABBR_MAP = {
    "str": "Strength",
    "dex": "Dexterity",
    "con": "Constitution",
    "int": "Intelligence",
    "wis": "Wisdom",
    "cha": "Charisma",
}

SKILL_NAMES = (
    "acrobatics",
    "animalHandling",
    "technology",
    "athletics",
    "deception",
    "lore",
    "initiative",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "piloting",
    "sleightOfHand",
    "stealth",
    "survival",
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

SAVE_NAMES = (
    "strengthSave",
    "dexteritySave",
    "constitutionSave",
    "intelligenceSave",
    "wisdomSave",
    "charismaSave",
)

SKILL_MAP = {
    "acrobatics": "dexterity",
    "animalHandling": "wisdom",
    "technology": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "lore": "intelligence",
    "initiative": "dexterity",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "piloting": "intelligence",
    "sleightOfHand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
    "strengthSave": "strength",
    "dexteritySave": "dexterity",
    "constitutionSave": "constitution",
    "intelligenceSave": "intelligence",
    "wisdomSave": "wisdom",
    "charismaSave": "charisma",
    "strength": "strength",
    "dexterity": "dexterity",
    "constitution": "constitution",
    "intelligence": "intelligence",
    "wisdom": "wisdom",
    "charisma": "charisma",
}
