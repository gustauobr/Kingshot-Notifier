# config.py

import json
from pathlib import Path

import discord

#  ─── Game-Wide Constants ───────────────────────────────────

GAME_TIMEZONE     = "UTC"
ARENA_OPEN_TIME   = "23:50"   # always UTC
ARENA_RESET_TIME  = "00:00"   # always UTC


# ─── Bear Phase Offsets ────────────────────────────────────
# Offsets in minutes relative to scheduled bear time:
#   negative = minutes before, zero = at time, positive = minutes after
BEAR_PHASE_OFFSETS = {
    "incoming":   -60,   # 60 min before event
    "pre_attack": -10,   # 10 min before event
    "attack":      0,    # exactly at event time
    "victory":    30     # 30 min after event
}
# ─── Embed Colors ───────────────────────────────────────────
EMBED_COLOR_PRIMARY     = 0x7289DA  # deep blurple (scheduled)
EMBED_COLOR_INCOMING    = 0x5DADE2  # lighter sky-blue (incoming)
EMBED_COLOR_PREATTACK   = 0xF39C12  # warning-orange      (pre-attack)
EMBED_COLOR_ATTACK      = 0xE74C3C  # strong red          (attack)
EMBED_COLOR_VICTORY     = 0x2ECC71  # fresh green         (victory)
EMBED_COLOR_SUCCESS   = 0x2ECC71 #green
EMBED_COLOR_WARNING   = 0xE74C3C #red
EMBED_COLOR_INFO      = 0x3498DB #blue?
EMBED_COLOR_EVENT     = 0xF1C40F #yellow

DEFAULT_ACTIVITY    = "Kingshot"
DEFAULT_ACTIVITY_TYPE = discord.ActivityType.playing   # ← use the enum, not a string
DEFAULT_STATUS        = discord.Status.online          # green dot (or idle, dnd, invisible)

# ─── Emoji thumbnails ───────────────────────────────────────────
EMOJI_THUMBNAILS = {
    "scheduled": "https://cdn.discordapp.com/emojis/1375520846407270561.png",
    "incoming": "https://cdn.discordapp.com/emojis/1375525056725258302.png",
    "pre_attack": "https://cdn.discordapp.com/emojis/1375525056725258302.png",
    "attack": "https://cdn.discordapp.com/emojis/1375525984723275967.png",
    "victory": "https://cdn.discordapp.com/emojis/1375519513738481756.png",
}

# Emoji thumbnails for event templates
EMOJI_THUMBNAILS_EVENTS = {
    "hall_of_governors": "https://cdn.discordapp.com/emojis/1375519513738481756.png",
    "all_out_event": "https://cdn.discordapp.com/emojis/1375519529479704677.png",
    "viking_vengeance": "https://cdn.discordapp.com/emojis/1375581618093166653.png",
    "swordland_showdown": "https://cdn.discordapp.com/emojis/1375519488568459274.png",
    "kingdom_v_kingdom": "https://cdn.discordapp.com/emojis/1375519564862853171.png"
}

# ─── Date/Time Formats ──────────────────────────────────────
DT_FORMAT_LONG        = "%A, %B %d, %Y %I:%M %p"  # e.g. "Tuesday, May 20, 2025 07:30 PM"
DT_FORMAT_SHORT       = "%Y-%m-%d %H:%M:%S"

# ─── Log format ─────────────────────────────────────────────
LOG_FORMAT            = "[%(asctime)s] %(levelname)8s: %(message)s"


# ─── UI Constants ───────────────────────────────────────────
CATEGORY_NAME     = "👑 Kingshot Bot"
REACTION_CHANNEL  = "📜｜reaction-roles"
BEAR_CHANNEL      = "🐻｜bear"
BEAR_LOG_CHANNEL  = "🐾｜bear-log"
ARENA_CHANNEL     = "⚔｜arena"
EVENT_CHANNEL     = "🏆｜events"
ROLE_EMOJIS       = {
    "🐻": "Bear 🐻",
    "⚔️": "Arena ⚔️",
    "🏆": "Events 🏆"
}

# ─── Scheduler ─────────────────────────────────────────────────────
SCHEDULER_INTERVAL_SEC = 60

#  ─── Load per-guild channels & IDs ─────────────────────────
CONFIG_PATH = Path(__file__).parent / "bot_config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    gcfg = json.load(f)

