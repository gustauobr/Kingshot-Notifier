# bot.py
import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from config import DEFAULT_ACTIVITY, DEFAULT_ACTIVITY_TYPE, DEFAULT_STATUS
from command_center import start_command_center
import sys


load_dotenv()  # ⬅️ This loads variables from .env into os.environ

# Validate token
token = os.getenv("KINGSHOT_BOT_TOKEN")
if not token:
    raise ValueError("❌ Bot token is missing. Set KINGSHOT_BOT_TOKEN in Railway.")

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("kingshot")

# ─── Intents & Bot ───────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned, help_command=None, intents=intents)
bot.role_message_ids = {}

# ─── Cogs List ───
COGS = [    
    "cogs.reaction",
    "cogs.arena",
    "cogs.bear",
    "cogs.commands",
    "cogs.events",
    "cogs.installer"
]

# ─── Main Entrypoint ───
async def main():
    log.info("Starting Kingshot Bot...")
    try:
        for cog in COGS:
            await bot.load_extension(cog)
            log.info(f"Loaded cog: {cog}")
        
        log.info("All cogs loaded. Connecting to Discord...")
        await bot.start(token)  # Use validated token
    except Exception as e:
        log.exception("Bot encountered an exception:", exc_info=e)
        # Exit with error code if we crashed
        sys.exit(1)
    finally:
        log.info("Shutting down bot...")
        try:
            await bot.close()
        except Exception as e:
            log.error(f"Error during shutdown: {e}")
        # Don't exit here - let the watchdog handle it

@bot.event
async def on_ready():
    activity = discord.Activity(type=DEFAULT_ACTIVITY_TYPE, name=DEFAULT_ACTIVITY)
    await bot.change_presence(status=DEFAULT_STATUS, activity=activity)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    log.info(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")

    # Start command center after bot is ready
    start_command_center(bot)
    log.info("Command center started")

    # Optional: Only sync globally unless debugging
    synced = await bot.tree.sync()
    log.info(f"✅ Globally synced {len(synced)} commands.")

    for guild in bot.guilds:
        log.info(f"Available in: {guild.name} ({guild.id})")
        
if __name__ == "__main__":
    asyncio.run(main())