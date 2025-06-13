import threading
import asyncio
import os
import sys
import time
import discord
from datetime import datetime, timezone
from config import gcfg

# ────────────────────────────────────────────────────────────
# Live Feed Manager
# ────────────────────────────────────────────────────────────

class LiveFeed:
    def __init__(self):
        self.enabled = False
        self._queue = asyncio.Queue()
        self._task = None
        self._lock = threading.Lock()
        self._shutdown = False

    def log(self, action: str, details: str = "", guild: discord.Guild = None, channel: discord.TextChannel = None):
        if not self.enabled or self._shutdown:
            return
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "action": action,
            "details": details,
            "guild": guild.name if guild else None,
            "channel": f"#{channel.name}" if channel else None
        }
        try:
            asyncio.run_coroutine_threadsafe(self._queue.put(entry), asyncio.get_event_loop())
        except:
            pass

    async def _process_queue(self):
        while not self._shutdown:
            try:
                entry = await self._queue.get()
                if not self.enabled or self._shutdown:
                    self._queue.task_done()
                    continue
                print(f"\n[{entry['timestamp']}]", end="")
                if entry['guild']:
                    print(f" [{entry['guild']}]", end="")
                if entry['channel']:
                    print(f" {entry['channel']}", end="")
                print(f"\n• {entry['action']}")
                if entry['details']:
                    print(f"  → {entry['details']}")
            except asyncio.CancelledError:
                self._shutdown = True
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                        self._queue.task_done()
                    except:
                        pass
                raise
            except Exception as e:
                print(f"❌ Live feed error: {e}")
                if not self._queue.empty():
                    self._queue.task_done()
            else:
                if not self._queue.empty():
                    self._queue.task_done()

    def start(self, loop: asyncio.AbstractEventLoop):
        with self._lock:
            if self._task is None:
                self._shutdown = False
                self._task = loop.create_task(self._process_queue())

    def stop(self):
        with self._lock:
            if self._task:
                self._shutdown = True
                self._task.cancel()
                self._task = None
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                        self._queue.task_done()
                    except:
                        pass

    def toggle(self, enabled: bool = None) -> bool:
        with self._lock:
            self.enabled = not self.enabled if enabled is None else enabled
            return self.enabled

live_feed = LiveFeed()

# ────────────────────────────────────────────────────────────
# Command Center Entry
# ────────────────────────────────────────────────────────────

def start_command_center(bot):
    live_feed.start(bot.loop)

    def file_input_loop():
        print("\n🧠 Command Center (File Mode) Started\nType commands into 'command_center_input.txt' (one per line). File will be cleared after reading.")
        input_file = "command_center_input.txt"
        while True:
            try:
                if os.path.exists(input_file):
                    with open(input_file, "r+") as f:
                        lines = [line.strip() for line in f if line.strip()]
                        if lines:
                            for raw in lines:
                                print(f"\n🧠 (file) >> {raw}")
                                args = raw.split()
                                cmd = args[0].lower()
                                handle_command(bot, cmd, args)
                            f.seek(0)
                            f.truncate()
                time.sleep(2)
            except Exception as e:
                print(f"❌ File input error: {e}")
                time.sleep(2)

    threading.Thread(target=file_input_loop, daemon=True).start()

# ────────────────────────────────────────────────────────────
# Command Dispatcher
# ────────────────────────────────────────────────────────────

def handle_command(bot, cmd, args):
    loop = bot.loop
    dispatch = {
        "/showservers": lambda: asyncio.run_coroutine_threadsafe(show_servers(bot), loop),
        "/showbears": lambda: asyncio.run_coroutine_threadsafe(show_bears(bot), loop),
        "/showevents": lambda: asyncio.run_coroutine_threadsafe(show_events(bot), loop),
        "/reloadcogs": lambda: asyncio.run_coroutine_threadsafe(reload_all_cogs(bot), loop),
        "/status": lambda: asyncio.run_coroutine_threadsafe(bot_status(bot), loop),
        "/ping": lambda: asyncio.run_coroutine_threadsafe(show_ping(bot), loop),
        "/auditroles": lambda: asyncio.run_coroutine_threadsafe(audit_roles(bot), loop),
        "/livefeedon": lambda: print(f"🔊 Live feed {'already ' if live_feed.toggle(True) else ''}ENABLED"),
        "/livefeedoff": lambda: print(f"🔇 Live feed {'already ' if not live_feed.toggle(False) else ''}DISABLED"),
        "/help": print_help
    }

    if cmd == "/reload" and len(args) >= 2:
        asyncio.run_coroutine_threadsafe(reload_cog(bot, args[1]), loop)
    elif cmd == "/serverdetails" and len(args) >= 2:
        print(gcfg.get(args[1], "⚠️ Not found."))
    elif cmd == "/send" and len(args) >= 4:
        asyncio.run_coroutine_threadsafe(send_message(bot, args[1], args[2], " ".join(args[3:])), loop)
    elif cmd == "/channels" and len(args) >= 2:
        asyncio.run_coroutine_threadsafe(show_channels(bot, args[1]), loop)
    elif cmd == "/stop":
        print("\n🛑 Stopping bot...")
        asyncio.run_coroutine_threadsafe(bot.close(), loop)
        return
    elif cmd == "/restart":
        print("\n🔁 Restarting bot...")
        live_feed.stop()
        asyncio.run_coroutine_threadsafe(bot.close(), loop)
        time.sleep(2)
        os._exit(0)
    elif cmd in dispatch:
        dispatch[cmd]()
    else:
        print("❌ Unknown command. Type /help for available commands")

def print_help():
    print("\nAvailable commands:")
    print("  /showservers      List all servers")
    print("  /showbears        List all scheduled bears")
    print("  /showevents       List all scheduled events")
    print("  /serverdetails <id>    Show server config")
    print("  /channels <id>    List server channels")
    print("  /reloadcogs       Reload all cogs")
    print("  /reload <cog>     Reload a specific cog")
    print("  /stop             Stop the bot")
    print("  /restart          Restart the bot")
    print("  /status           Show bot status")
    print("  /ping             Show bot latency")
    print("  /livefeedon       Enable live feed")
    print("  /livefeedoff      Disable live feed")
    print("  /send <gid> <channel> <msg> Send message")
    print("  /auditroles       Audit Bear/Arena roles")

# ────────────────────────────────────────────────────────────
# Async Helpers
# ────────────────────────────────────────────────────────────

async def show_servers(bot):
    print("\n📊 Connected Servers:")
    for g in bot.guilds:
        print(f"• {g.name} ({g.id}) • Members: {g.member_count}")

async def show_bears(bot):
    for guild in bot.guilds:
        gid = str(guild.id)
        bears = gcfg.get(gid, {}).get("bears", [])
        if bears:
            print(f"\n🐻 {guild.name} – {len(bears)} bear(s):")
            for b in bears:
                dt = datetime.fromtimestamp(b["epoch"], tz=timezone.utc)
                print(f"  → ID: {b['id']} | Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")

async def show_events(bot):
    for guild in bot.guilds:
        gid = str(guild.id)
        events = gcfg.get(gid, {}).get("events", [])
        if events:
            print(f"\n📅 {guild.name} – {len(events)} event(s):")
            for e in events:
                print(f"  → {e['title']} ({e['id']}) until <t:{e['end_epoch']}:R>")

async def reload_all_cogs(bot):
    print("\n🔄 Reloading all cogs...")
    for cog in list(bot.extensions):
        try:
            await bot.reload_extension(cog)
            print(f"✅ Reloaded: {cog}")
        except Exception as e:
            print(f"❌ Failed to reload {cog}: {e}")

async def reload_cog(bot, cog):
    try:
        await bot.reload_extension(cog)
        print(f"✅ Reloaded {cog}")
    except Exception as e:
        print(f"❌ Error reloading {cog}: {e}")

async def bot_status(bot):
    print(f"\n👑 Bot Status:")
    print(f"• Name: {bot.user} ({bot.user.id})")
    print(f"• Guilds: {len(bot.guilds)}")
    print(f"• Latency: {round(bot.latency * 1000)}ms")
    print(f"• Live Feed: {'🔊 ON' if live_feed.enabled else '🔇 OFF'}")

async def show_ping(bot):
    print(f"🏓 Ping: {round(bot.latency * 1000)}ms")

async def send_message(bot, gid, channel_name, msg):
    try:
        guild = bot.get_guild(int(gid))
        if not guild:
            return print("❌ Guild not found")
        ch = discord.utils.get(guild.text_channels, name=channel_name)
        if not ch:
            return print("❌ Channel not found")
        await ch.send(msg)
        print(f"✅ Message sent to #{channel_name} in {guild.name}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

async def show_channels(bot, gid):
    try:
        guild = bot.get_guild(int(gid))
        if not guild:
            return print("❌ Guild not found")
        print(f"\n📺 Channels in {guild.name}:")
        for ch in sorted(guild.text_channels, key=lambda c: c.position):
            print(f"#{ch.name} ({ch.id})")
    except Exception as e:
        print(f"❌ Error listing channels: {e}")

async def audit_roles(bot):
    print("\n🔍 Role Audit:")
    for guild in bot.guilds:
        bot_top = guild.me.top_role.position
        print(f"\n{guild.name}:")
        print(f"• Bot's highest role: {guild.me.top_role.name} (pos: {bot_top})")
        found_issues = False
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if role.name.startswith(("Bear", "Arena")) and role.position >= bot_top:
                found_issues = True
                print(f"⚠️ {role.name} is ABOVE bot role! (pos: {role.position})")
        if not found_issues:
            print("✅ All roles properly configured")
