# cogs/installer.py

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from helpers import ensure_channel, save_config, ensure_role
from config import (
    gcfg,
    BEAR_CHANNEL,
    ARENA_CHANNEL,
    EVENT_CHANNEL,
    CATEGORY_NAME,
    ROLE_EMOJIS,
    REACTION_CHANNEL,
    BEAR_LOG_CHANNEL,
)
from admin_tools import live_feed
from welcome_embeds import (
    make_bear_welcome_embed,
    make_arena_welcome_embed,
    make_event_welcome_embed,
    get_all_welcome_embeds,
    WELCOME_EMBED_VERSION,
)
from cogs.reaction import ReactionRole


def locked_channel_perms(bot_member: discord.Member, restrict_reactions=False):
    overwrites = {
        bot_member.guild.default_role: discord.PermissionOverwrite(
            send_messages=False,
            add_reactions=not restrict_reactions,
            manage_messages=False,
            create_public_threads=False,
            create_private_threads=False,
        ),
        bot_member: discord.PermissionOverwrite(
            send_messages=True,
            add_reactions=True,
            manage_messages=True,
            read_message_history=True,
            embed_links=True,
        ),
    }
    return overwrites


class SimpleChannelSelector:
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, cfg: dict):
        self.bot = bot
        self.interaction = interaction
        self.cfg = cfg
        self.all_channels = interaction.guild.text_channels
        self.channel_ids = {
            "bear": None,
            "bear_log": None,
            "arena": None,
            "event": None,
            "reaction": None,
        }

        self.labels = {
            "bear": "🐻 Bear Channel",
            "bear_log": "🐾 Bear Log Channel",
            "arena": "⚔️ Arena Channel",
            "event": "🏆 Event Channel",
            "reaction": "📜 Reaction Role Channel",
        }

        self.current_step = 0
        self.steps = list(self.labels.keys())

    async def start_selection(self):
        """Start the channel selection process"""
        await self.show_current_step()

    async def show_current_step(self):
        """Show the current step's channel selection"""
        if self.current_step >= len(self.steps):
            await self.complete_installation()
            return

        key = self.steps[self.current_step]
        label = self.labels[key]

        # Get accessible channels
        bot_member = self.interaction.guild.get_member(self.bot.user.id)
        accessible_channels = [
            ch
            for ch in self.all_channels
            if bot_member and ch.permissions_for(bot_member).send_messages
        ]

        # Limit to 25 options total for Discord's select menu limit
        max_options = 25
        # Reserve one slot for the search option when there are more channels
        limit = (
            max_options - 1 if len(accessible_channels) > max_options else max_options
        )
        limited_channels = accessible_channels[:limit]

        # Create options
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in limited_channels
        ]

        # Add search option if there are more channels than we displayed
        if len(accessible_channels) > max_options:
            options.append(
                discord.SelectOption(
                    label=f"🔍 Search more channels ({len(accessible_channels)} total)",
                    value="search",
                )
            )

        # Create select menu
        select = discord.ui.Select(
            placeholder=f"Select {label}",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"select_{key}",
        )

        # Create view
        view = discord.ui.View(timeout=300)
        view.add_item(select)

        # Add cancel button
        cancel_button = discord.ui.Button(
            label="❌ Cancel", style=discord.ButtonStyle.danger, custom_id="cancel"
        )
        view.add_item(cancel_button)

        # Set up callback
        async def select_callback(interaction: discord.Interaction):
            if interaction.data["custom_id"] == "cancel":
                await interaction.response.send_message(
                    "❌ Installation cancelled.", ephemeral=True
                )
                return

            if interaction.data["custom_id"] == f"select_{key}":
                value = interaction.data["values"][0]

                if value == "search":
                    # Show search modal
                    await interaction.response.send_modal(
                        SimpleSearchModal(self, key, label)
                    )
                else:
                    # Store selection and move to next step
                    self.channel_ids[key] = int(value)
                    self.current_step += 1

                    await interaction.response.send_message(
                        f"✅ Selected {label}: <#{value}>\n\nContinuing to next channel...",
                        ephemeral=True,
                    )

                    # Show next step
                    await self.show_current_step()

        # Set the callback
        select.callback = select_callback
        cancel_button.callback = lambda i: (
            select_callback(i) if i.data["custom_id"] == "cancel" else None
        )

        # Send the message
        if self.current_step == 0:
            await self.interaction.followup.send(
                f"⚙️ **Manual Installation - Step {self.current_step + 1}/{len(self.steps)}**\n"
                f"Please select the {label}:",
                view=view,
                ephemeral=True,
            )
        else:
            # For subsequent steps, we need to send a new message
            await self.interaction.followup.send(
                f"⚙️ **Step {self.current_step + 1}/{len(self.steps)}**\n"
                f"Please select the {label}:",
                view=view,
                ephemeral=True,
            )

    async def complete_installation(self):
        """Complete the installation process"""
        guild_id = str(self.interaction.guild.id)
        guild_cfg = gcfg.setdefault(guild_id, {})

        # Move selected channels to the category
        category = await ensure_category(self.interaction.guild)
        if category:
            for key, channel_id in self.channel_ids.items():
                if channel := self.interaction.guild.get_channel(channel_id):
                    try:
                        await channel.edit(category=category)
                    except discord.Forbidden:
                        live_feed.log(
                            "Failed to move channel to category",
                            f"Guild: {self.interaction.guild.name} • Channel: {channel.name} • Error: No permission",
                            self.interaction.guild,
                            self.interaction.channel,
                        )

        # Save channel IDs
        guild_cfg.setdefault("bear", {})["channel_id"] = self.channel_ids["bear"]
        guild_cfg.setdefault("bear", {})["log_channel_id"] = self.channel_ids[
            "bear_log"
        ]
        guild_cfg.setdefault("arena", {})["channel_id"] = self.channel_ids["arena"]
        guild_cfg.setdefault("event", {})["channel_id"] = self.channel_ids["event"]
        guild_cfg.setdefault("reaction", {})["channel_id"] = self.channel_ids[
            "reaction"
        ]
        save_config(gcfg)

        # Send welcome embeds to channels
        bear_ch = self.interaction.guild.get_channel(self.channel_ids["bear"])
        arena_ch = self.interaction.guild.get_channel(self.channel_ids["arena"])
        event_ch = self.interaction.guild.get_channel(self.channel_ids["event"])

        if bear_ch:
            bm = await bear_ch.send(embed=make_bear_welcome_embed(guild_id))
            guild_cfg["bear"]["welcome_message_id"] = bm.id

        if arena_ch:
            am = await arena_ch.send(embed=make_arena_welcome_embed(guild_id))
            guild_cfg["arena"]["welcome_message_id"] = am.id

        if event_ch:
            em = await event_ch.send(embed=make_event_welcome_embed(guild_id))
            guild_cfg["event"]["message_id"] = em.id

        # Set welcome embed version
        guild_cfg["welcome_embed_version"] = WELCOME_EMBED_VERSION

        # Create roles and save their IDs
        bear_role = await ensure_role(
            self.interaction.guild, "Bear 🐻", discord.Color.orange()
        )
        arena_role = await ensure_role(
            self.interaction.guild, "Arena ⚔️", discord.Color.red()
        )
        event_role = await ensure_role(
            self.interaction.guild, "Event 🏆", discord.Color.gold()
        )
        guild_cfg["bear"]["role_id"] = bear_role.id
        guild_cfg["arena"]["role_id"] = arena_role.id
        guild_cfg["event"]["role_id"] = event_role.id
        save_config(gcfg)

        # Trigger immediate setup
        if c := self.bot.get_cog("ReactionRole"):
            await c.setup_reactions(
                self.interaction.guild,
                self.interaction.guild.get_channel(guild_cfg["reaction"]["channel_id"]),
            )
        if a := self.bot.get_cog("ArenaScheduler"):
            await a.sync_now(self.interaction.guild)

        await self.interaction.followup.send(
            "✅ Manual install complete!", ephemeral=True
        )


class SimpleSearchModal(discord.ui.Modal, title="🔍 Search Channels"):
    def __init__(self, parent: SimpleChannelSelector, key: str, label: str):
        super().__init__()
        self.parent = parent
        self.key = key
        self.label = label

        self.search_term = discord.ui.TextInput(
            label="Channel name (partial match)",
            placeholder="e.g., 'general' or 'bot'",
            min_length=1,
            max_length=32,
            required=True,
        )
        self.add_item(self.search_term)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Get the bot's member object in this guild
        bot_member = interaction.guild.get_member(self.parent.bot.user.id)

        # Filter channels by search term
        search_term = self.search_term.value.lower()
        matching_channels = [
            ch
            for ch in self.parent.all_channels
            if bot_member
            and ch.permissions_for(bot_member).send_messages
            and search_term in ch.name.lower()
        ]

        if not matching_channels:
            await interaction.followup.send(
                f"❌ No accessible channels found matching '{search_term}'",
                ephemeral=True,
            )
            return

        # Create options for search results (max 25)
        limited_channels = matching_channels[:25]
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in limited_channels
        ]

        # Create select menu
        select = discord.ui.Select(
            placeholder=f"Select {self.label} from search results",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"search_{self.key}",
        )

        # Create view
        view = discord.ui.View(timeout=300)
        view.add_item(select)

        # Set up callback
        async def search_callback(interaction: discord.Interaction):
            if interaction.data["custom_id"] == f"search_{self.key}":
                value = interaction.data["values"][0]

                # Store selection and move to next step
                self.parent.channel_ids[self.key] = int(value)
                self.parent.current_step += 1

                await interaction.response.send_message(
                    f"✅ Selected {self.label}: <#{value}>\n\nContinuing to next channel...",
                    ephemeral=True,
                )

                # Show next step
                await self.parent.show_current_step()

        # Set the callback
        select.callback = search_callback

        await interaction.followup.send(
            f"🔍 Found {len(matching_channels)} channels matching '{search_term}':",
            view=view,
            ephemeral=True,
        )


async def ensure_category(guild: discord.Guild) -> discord.CategoryChannel:
    """Ensure a category exists, create if it doesn't"""
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)
    return category


class Installer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start welcome message update task
        self._update_task = asyncio.create_task(self._update_welcome_messages())

    def cog_unload(self):
        # Cancel the update task
        if hasattr(self, "_update_task"):
            self._update_task.cancel()

    async def _update_welcome_messages(self):
        """Update welcome messages on startup with new formatting"""
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            guild_cfg = gcfg.get(guild_id, {})

            if not guild_cfg.get("mode"):
                continue  # Not installed

            # Check if welcome messages need updating
            current_version = guild_cfg.get("welcome_embed_version", "1.0")
            if current_version == WELCOME_EMBED_VERSION:
                # Already up to date, skip
                continue

            live_feed.log(
                "Updating welcome messages",
                f"Guild: {guild.name} • Version: {current_version} → {WELCOME_EMBED_VERSION}",
                guild,
                None,
            )

            updated_count = 0

            # Update bear welcome message
            bear_cfg = guild_cfg.get("bear", {})
            if bear_cfg.get("welcome_message_id") and bear_cfg.get("channel_id"):
                bear_ch = guild.get_channel(bear_cfg["channel_id"])
                if bear_ch:
                    try:
                        msg = await bear_ch.fetch_message(
                            bear_cfg["welcome_message_id"]
                        )
                        new_embed = make_bear_welcome_embed(guild_id)
                        await msg.edit(embed=new_embed)
                        updated_count += 1
                        live_feed.log(
                            "Updated bear welcome message",
                            f"Guild: {guild.name} • Channel: #{bear_ch.name}",
                            guild,
                            bear_ch,
                        )
                    except (discord.NotFound, discord.Forbidden):
                        live_feed.log(
                            "Failed to update bear welcome message",
                            f"Guild: {guild.name} • Message not found or no permission",
                            guild,
                            None,
                        )

            # Update arena welcome message
            arena_cfg = guild_cfg.get("arena", {})
            if arena_cfg.get("welcome_message_id") and arena_cfg.get("channel_id"):
                arena_ch = guild.get_channel(arena_cfg["channel_id"])
                if arena_ch:
                    try:
                        msg = await arena_ch.fetch_message(
                            arena_cfg["welcome_message_id"]
                        )
                        new_embed = make_arena_welcome_embed(guild_id)
                        await msg.edit(embed=new_embed)
                        updated_count += 1
                        live_feed.log(
                            "Updated arena welcome message",
                            f"Guild: {guild.name} • Channel: #{arena_ch.name}",
                            guild,
                            arena_ch,
                        )
                    except (discord.NotFound, discord.Forbidden):
                        live_feed.log(
                            "Failed to update arena welcome message",
                            f"Guild: {guild.name} • Message not found or no permission",
                            guild,
                            None,
                        )

            # Update event welcome message
            event_cfg = guild_cfg.get("event", {})
            if event_cfg.get("message_id") and event_cfg.get("channel_id"):
                event_ch = guild.get_channel(event_cfg["channel_id"])
                if event_ch:
                    try:
                        msg = await event_ch.fetch_message(event_cfg["message_id"])
                        new_embed = make_event_welcome_embed(guild_id)
                        await msg.edit(embed=new_embed)
                        updated_count += 1
                        live_feed.log(
                            "Updated event welcome message",
                            f"Guild: {guild.name} • Channel: #{event_ch.name}",
                            guild,
                            event_ch,
                        )
                    except (discord.NotFound, discord.Forbidden):
                        live_feed.log(
                            "Failed to update event welcome message",
                            f"Guild: {guild.name} • Message not found or no permission",
                            guild,
                            None,
                        )

            # Update version in config if any messages were updated
            if updated_count > 0:
                guild_cfg["welcome_embed_version"] = WELCOME_EMBED_VERSION
                save_config(gcfg)
                live_feed.log(
                    "Welcome messages updated",
                    f"Guild: {guild.name} • Updated: {updated_count} messages • Version: {WELCOME_EMBED_VERSION}",
                    guild,
                    None,
                )
            else:
                live_feed.log(
                    "No welcome messages to update",
                    f"Guild: {guild.name} • Version: {WELCOME_EMBED_VERSION}",
                    guild,
                    None,
                )

    @app_commands.command(
        name="install", description="⚙️ Set up the bot (auto or manual mode)"
    )
    @app_commands.describe(mode="Choose 'auto' or 'manual'")
    async def install(self, interaction: discord.Interaction, mode: str):
        guild = interaction.guild
        if not guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admins only.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)

        guild_id = str(guild.id)
        cfg = gcfg.setdefault(guild_id, {})

        # Check if already installed - more strict check
        if cfg.get("mode"):
            current_mode = cfg.get("mode")
            live_feed.log(
                "Install attempt (already installed)",
                f"Guild: {guild.name} • Current mode: {current_mode} • Attempted mode: {mode} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            return await interaction.followup.send(
                f"❌ Already installed in {current_mode} mode. Use `/uninstall` first to change modes.",
                ephemeral=True,
            )

        if mode not in ("auto", "manual"):
            live_feed.log(
                "Invalid install mode attempted",
                f"Guild: {guild.name} • Mode: {mode} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            return await interaction.followup.send(
                "❌ Unknown mode. Use `auto` or `manual`.", ephemeral=True
            )

        # Set the mode first so ensure_channel works correctly
        cfg["mode"] = mode
        save_config(gcfg)

        if mode == "auto":
            live_feed.log(
                "Starting auto-install",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            await interaction.followup.send("⚙️ Auto-installing...", ephemeral=True)
            bot_member = guild.get_member(self.bot.user.id)

            # Ensure category once
            category = await ensure_category(guild)

            # Create all channels inside the same category
            bear_ch = await ensure_channel(
                guild,
                BEAR_CHANNEL,
                overwrites=locked_channel_perms(bot_member),
                category=category,
            )
            bear_log = await ensure_channel(
                guild,
                BEAR_LOG_CHANNEL,
                overwrites=locked_channel_perms(bot_member),
                category=category,
            )
            arena_ch = await ensure_channel(
                guild,
                ARENA_CHANNEL,
                overwrites=locked_channel_perms(bot_member),
                category=category,
            )
            event_ch = await ensure_channel(
                guild,
                EVENT_CHANNEL,
                overwrites=locked_channel_perms(bot_member),
                category=category,
            )
            react_ch = await ensure_channel(
                guild,
                REACTION_CHANNEL,
                overwrites=locked_channel_perms(bot_member, True),
                category=category,
            )

            live_feed.log(
                "Created channels",
                f"Guild: {guild.name} • Category: {CATEGORY_NAME} • Channels: Bear, Bear Log, Arena, Event, Reaction",
                guild,
                interaction.channel,
            )

            # Persist IDs
            cfg["bear"] = {"channel_id": bear_ch.id, "log_channel_id": bear_log.id}
            cfg["arena"] = {"channel_id": arena_ch.id}
            cfg["event"] = {"channel_id": event_ch.id}
            cfg["reaction"] = {"channel_id": react_ch.id}

            # Create roles
            bear_role = await ensure_role(guild, "Bear 🐻", discord.Color.orange())
            arena_role = await ensure_role(guild, "Arena ⚔️", discord.Color.red())
            event_role = await ensure_role(guild, "Event 🏆", discord.Color.gold())
            cfg["bear"]["role_id"] = bear_role.id
            cfg["arena"]["role_id"] = arena_role.id
            cfg["event"]["role_id"] = event_role.id

            live_feed.log(
                "Created roles",
                f"Guild: {guild.name} • Roles: Bear, Arena, Event",
                guild,
                interaction.channel,
            )

            # Send welcome messages
            bm = await bear_ch.send(embed=make_bear_welcome_embed(guild_id))
            am = await arena_ch.send(embed=make_arena_welcome_embed(guild_id))
            em = await event_ch.send(embed=make_event_welcome_embed(guild_id))

            # Store message IDs
            cfg["bear"]["welcome_message_id"] = bm.id
            cfg["arena"]["welcome_message_id"] = am.id
            cfg["event"]["message_id"] = em.id
            cfg["welcome_embed_version"] = WELCOME_EMBED_VERSION

            live_feed.log(
                "Sent welcome messages",
                f"Guild: {guild.name} • Channels: Bear, Arena, Event",
                guild,
                interaction.channel,
            )

            if a := self.bot.get_cog("ArenaScheduler"):
                await a.sync_now(guild)
            if c := self.bot.get_cog("ReactionRole"):
                await c.setup_reactions(guild, react_ch)

            save_config(gcfg)
            live_feed.log(
                "Auto-install complete",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            await interaction.followup.send("✅ Installation complete.", ephemeral=True)

        else:  # manual mode
            live_feed.log(
                "Starting manual install",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            selector = SimpleChannelSelector(self.bot, interaction, gcfg)
            await selector.start_selection()

    @app_commands.command(
        name="uninstall", description="🗑️ Remove all bot channels, roles, and settings"
    )
    async def uninstall(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            if not guild or not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "❌ Admins only.", ephemeral=True
                )
            await interaction.response.defer(ephemeral=True)

            live_feed.log(
                "Starting uninstall",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel,
            )

            guild_id = str(guild.id)
            cfg = gcfg.get(guild_id, {})
            deleted_roles, deleted_channels, deleted_categories, purged = 0, 0, 0, 0

            # Delete roles (bear, arena, event)
            for role_key in ("bear", "arena", "event"):
                role_id = cfg.get(role_key, {}).get("role_id")
                if role_id and (role := guild.get_role(role_id)):
                    try:
                        await role.delete(reason="Uninstall")
                        deleted_roles += 1
                        live_feed.log(
                            f"Deleted {role_key} role",
                            f"Guild: {guild.name} • Role: {role.name}",
                            guild,
                            interaction.channel,
                        )
                    except discord.Forbidden:
                        live_feed.log(
                            f"Failed to delete {role_key} role",
                            f"Guild: {guild.name} • Role: {role.name} • Error: No permission",
                            guild,
                            interaction.channel,
                        )

            # Auto mode: delete channels & category
            if cfg.get("mode") == "auto":
                # First try to delete channels by their stored IDs
                channels_to_delete = []

                # Handle bear and bear log channels
                if bear_cfg := cfg.get("bear", {}):
                    if channel_id := bear_cfg.get("channel_id"):
                        if channel := guild.get_channel(channel_id):
                            channels_to_delete.append(channel)
                    if log_channel_id := bear_cfg.get("log_channel_id"):
                        if channel := guild.get_channel(log_channel_id):
                            channels_to_delete.append(channel)

                # Handle other channels
                for sect in ("arena", "event", "reaction"):
                    if channel_id := cfg.get(sect, {}).get("channel_id"):
                        if channel := guild.get_channel(channel_id):
                            channels_to_delete.append(channel)

                # Delete each channel
                for channel in channels_to_delete:
                    try:
                        await channel.delete(reason="Uninstall")
                        deleted_channels += 1
                        live_feed.log(
                            "Deleted channel",
                            f"Guild: {guild.name} • Channel: {channel.name}",
                            guild,
                            interaction.channel,
                        )
                    except discord.Forbidden:
                        live_feed.log(
                            "Failed to delete channel",
                            f"Guild: {guild.name} • Channel: {channel.name} • Error: No permission",
                            guild,
                            interaction.channel,
                        )
                    except discord.NotFound:
                        live_feed.log(
                            "Channel already deleted",
                            f"Guild: {guild.name} • Channel ID: {channel.id}",
                            guild,
                            interaction.channel,
                        )

                # Try to delete the category regardless of whether it's empty
                category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
                if category:
                    try:
                        # First try to move any remaining channels out of the category
                        for channel in category.channels:
                            try:
                                await channel.edit(category=None)
                            except (discord.Forbidden, discord.NotFound):
                                pass

                        # Then delete the category
                        await category.delete(reason="Uninstall")
                        deleted_categories += 1
                        live_feed.log(
                            "Deleted category",
                            f"Guild: {guild.name} • Category: {category.name}",
                            guild,
                            interaction.channel,
                        )
                    except discord.Forbidden:
                        live_feed.log(
                            "Failed to delete category",
                            f"Guild: {guild.name} • Category: {category.name} • Error: No permission",
                            guild,
                            interaction.channel,
                        )
                    except discord.NotFound:
                        live_feed.log(
                            "Category already deleted",
                            f"Guild: {guild.name} • Category: {category.name}",
                            guild,
                            interaction.channel,
                        )
            else:
                # Manual mode: only purge bot messages, DO NOT delete channels
                live_feed.log(
                    "Manual mode uninstall - preserving channels",
                    f"Guild: {guild.name} • Mode: manual",
                    guild,
                    interaction.channel,
                )

                # Only purge bot messages from the selected channels
                for sect in ("bear", "bear_log", "arena", "event", "reaction"):
                    channel_id = cfg.get(sect, {}).get("channel_id")
                    if channel_id and (channel := guild.get_channel(channel_id)):

                        def is_bot(m):
                            return m.author.id == self.bot.user.id

                        try:
                            purged_count = len(
                                await channel.purge(limit=100, check=is_bot)
                            )
                            purged += purged_count
                            if purged_count > 0:
                                live_feed.log(
                                    "Purged bot messages",
                                    f"Guild: {guild.name} • Channel: {channel.name} • Count: {purged_count}",
                                    guild,
                                    interaction.channel,
                                )
                        except discord.Forbidden:
                            live_feed.log(
                                "Failed to purge messages",
                                f"Guild: {guild.name} • Channel: {channel.name} • Error: No permission",
                                guild,
                                interaction.channel,
                            )

            # Cancel any running BearScheduler tasks for this guild
            bear_cog = self.bot.get_cog("BearScheduler")
            if bear_cog:
                for ev in list(bear_cog.bear_events.values()):
                    if ev.guild_id == guild.id and ev.task:
                        ev.task.cancel()
                        try:
                            await ev.task
                        except asyncio.CancelledError:
                            pass

            # Cancel any running ArenaScheduler tasks for this guild
            arena_cog = self.bot.get_cog("ArenaScheduler")
            if arena_cog:
                for ev in list(arena_cog.arena_events.values()):
                    if ev.guild_id == guild.id and ev.task:
                        ev.task.cancel()
                        try:
                            await ev.task
                        except asyncio.CancelledError:
                            pass

            # Cancel any running EventScheduler tasks for this guild
            event_cog = self.bot.get_cog("EventScheduler")
            if event_cog:
                for ev in list(event_cog.events.values()):
                    if ev.guild_id == guild.id and ev.task:
                        ev.task.cancel()
                        try:
                            await ev.task
                        except asyncio.CancelledError:
                            pass

            # Remove from config
            gcfg.pop(guild_id, None)
            save_config(gcfg)

            live_feed.log(
                "Uninstall complete",
                f"Guild: {guild.name} • Deleted: {deleted_roles} roles, {deleted_channels} channels, {deleted_categories} categories, {purged} messages • By: {interaction.user}",
                guild,
                interaction.channel,
            )

            await interaction.followup.send(
                f"✅ Uninstalled! Removed {deleted_roles} roles, {deleted_channels} channels, {deleted_categories} categories, and {purged} messages.",
                ephemeral=True,
            )

        except Exception as e:
            live_feed.log(
                "Uninstall failed",
                f"Guild: {guild.name} • Error: {str(e)} • By: {interaction.user}",
                guild,
                interaction.channel,
            )
            await interaction.followup.send(
                f"❌ Uninstall failed: {str(e)}", ephemeral=True
            )

    @app_commands.command(
        name="updateembeds", description="🔄 Update welcome embeds to latest format"
    )
    async def updateembeds(self, interaction: discord.Interaction):
        """Manually update welcome embeds to the latest format"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admins only.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        guild_cfg = gcfg.get(guild_id, {})

        if not guild_cfg.get("mode"):
            return await interaction.followup.send(
                "❌ Bot not installed in this server.", ephemeral=True
            )

        current_version = guild_cfg.get("welcome_embed_version", "1.0")
        if current_version == WELCOME_EMBED_VERSION:
            return await interaction.followup.send(
                "✅ Welcome embeds are already up to date.", ephemeral=True
            )

        live_feed.log(
            "Manual welcome embed update",
            f"Guild: {guild.name} • Version: {current_version} → {WELCOME_EMBED_VERSION} • By: {interaction.user}",
            guild,
            interaction.channel,
        )

        updated_count = 0

        # Update bear welcome message
        bear_cfg = guild_cfg.get("bear", {})
        if bear_cfg.get("welcome_message_id") and bear_cfg.get("channel_id"):
            bear_ch = guild.get_channel(bear_cfg["channel_id"])
            if bear_ch:
                try:
                    msg = await bear_ch.fetch_message(bear_cfg["welcome_message_id"])
                    new_embed = make_bear_welcome_embed(guild_id)
                    await msg.edit(embed=new_embed)
                    updated_count += 1
                    live_feed.log(
                        "Updated bear welcome message",
                        f"Guild: {guild.name} • Channel: #{bear_ch.name}",
                        guild,
                        bear_ch,
                    )
                except (discord.NotFound, discord.Forbidden):
                    live_feed.log(
                        "Failed to update bear welcome message",
                        f"Guild: {guild.name} • Message not found or no permission",
                        guild,
                        None,
                    )

        # Update arena welcome message
        arena_cfg = guild_cfg.get("arena", {})
        if arena_cfg.get("welcome_message_id") and arena_cfg.get("channel_id"):
            arena_ch = guild.get_channel(arena_cfg["channel_id"])
            if arena_ch:
                try:
                    msg = await arena_ch.fetch_message(arena_cfg["welcome_message_id"])
                    new_embed = make_arena_welcome_embed(guild_id)
                    await msg.edit(embed=new_embed)
                    updated_count += 1
                    live_feed.log(
                        "Updated arena welcome message",
                        f"Guild: {guild.name} • Channel: #{arena_ch.name}",
                        guild,
                        arena_ch,
                    )
                except (discord.NotFound, discord.Forbidden):
                    live_feed.log(
                        "Failed to update arena welcome message",
                        f"Guild: {guild.name} • Message not found or no permission",
                        guild,
                        None,
                    )

        # Update event welcome message
        event_cfg = guild_cfg.get("event", {})
        if event_cfg.get("message_id") and event_cfg.get("channel_id"):
            event_ch = guild.get_channel(event_cfg["channel_id"])
            if event_ch:
                try:
                    msg = await event_ch.fetch_message(event_cfg["message_id"])
                    new_embed = make_event_welcome_embed(guild_id)
                    await msg.edit(embed=new_embed)
                    updated_count += 1
                    live_feed.log(
                        "Updated event welcome message",
                        f"Guild: {guild.name} • Channel: #{event_ch.name}",
                        guild,
                        event_ch,
                    )
                except (discord.NotFound, discord.Forbidden):
                    live_feed.log(
                        "Failed to update event welcome message",
                        f"Guild: {guild.name} • Message not found or no permission",
                        guild,
                        None,
                    )

        # Update version in config
        guild_cfg["welcome_embed_version"] = WELCOME_EMBED_VERSION
        save_config(gcfg)

        await interaction.followup.send(
            f"✅ Updated {updated_count} welcome embed(s) to version {WELCOME_EMBED_VERSION}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Installer(bot))
