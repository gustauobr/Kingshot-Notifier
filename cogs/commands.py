# cogs/commands.py

import logging
import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction, Embed

from config import EMBED_COLOR_PRIMARY
from helpers import ensure_channel, update_guild_count, update_role_counts
from admin_tools import live_feed

log = logging.getLogger("kingshot")


class Core(commands.Cog):
    """Core listeners and admin sync command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        log.info(f"Joined guild: {guild.name} ({guild.id})")
        live_feed.log(
            "Bot joined new guild",
            f"Guild: {guild.name} • Members: {guild.member_count}",
            guild,
            None,
        )
        # Send a welcome embed in the system channel or first writable channel
        dest = guild.system_channel or next(
            (
                c
                for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ),
            None,
        )
        if not dest:
            live_feed.log(
                "Failed to send welcome message",
                f"Guild: {guild.name} • Error: No suitable channel found",
                guild,
                None,
            )
            await update_guild_count(self.bot)
            await update_role_counts(self.bot)
            return

        embed = Embed(
            title="👑 Kingshot Bot Has Arrived!",
            description=(
                "Thanks for inviting **Kingshot Bot** to your server!\n\n"
                "To get started, run `/install auto` and I'll create everything you need.\n"
                "Prefer to choose your own channels? Use `/install manual` instead.\n\n"
                "Need help? Use `/help` for a full list of commands."
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_thumbnail(
            url=(
                self.bot.user.avatar.url
                if self.bot.user.avatar
                else discord.Embed.Empty
            )
            url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        embed.set_footer(
            text="made by ninjardx 🏆",
            icon_url=(
                self.bot.user.avatar.url
                if self.bot.user.avatar
                else discord.Embed.Empty
            ),
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None,
        )
        await dest.send(embed=embed)
        live_feed.log(
            "Sent welcome message",
            f"Guild: {guild.name} • Channel: #{dest.name}",
            guild,
            dest,
        )
        await update_guild_count(self.bot)
        await update_role_counts(self.bot)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        log.info(f"Left guild: {guild.name} ({guild.id})")
        live_feed.log(
            "Bot removed from guild",
            f"Guild: {guild.name}",
            guild,
            None,
        )
        await update_guild_count(self.bot)
        await update_role_counts(self.bot)

    @app_commands.command(
        name="synccommands", description="🔧 Force sync of slash commands (Admins only)"
@@ -233,55 +225,51 @@ class EmbedModal(ui.Modal, title="Create an Embed"):
            label="Footer (optional)", required=False, max_length=256
        )
        self.thumbnail_input = ui.TextInput(
            label="Thumbnail URL (optional)", required=False
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.footer_input)
        self.add_item(self.thumbnail_input)

    async def on_submit(self, interaction: Interaction):
        live_feed.log(
            "Embed created",
            f"Guild: {interaction.guild.name} • By: {interaction.user} • Title: {self.title_input.value[:30]}...",
            interaction.guild,
            interaction.channel,
        )
        embed = Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=EMBED_COLOR_PRIMARY,
        )
        if self.footer_input.value:
            embed.set_footer(
                text=self.footer_input.value,
                icon_url=(
                    self.bot.user.avatar.url
                    if self.bot.user.avatar
                    else discord.Embed.Empty
                ),
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None,
            )
        if self.thumbnail_input.value:
            embed.set_thumbnail(url=self.thumbnail_input.value)
        await interaction.response.send_message(embed=embed, ephemeral=False)


class Utility(commands.Cog):
    """Utility commands that require mod/admin permissions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="embed",
        description="📄 Open a popup to create an embedded message (Admins only)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(self, interaction: Interaction):
        """Show the Embed creation modal."""
        live_feed.log(
            "Embed creation started",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel,
        )
