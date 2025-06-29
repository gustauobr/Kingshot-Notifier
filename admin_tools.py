<<<<<<< codex/rodar-projeto-no-railway
"""Compatibility layer exposing admin functions from command_center."""

from command_center import handle_command, live_feed, start_command_center


def start_admin_tools(bot):
    """Start admin tools via the command center."""
=======
from command_center import handle_command, live_feed, start_command_center

# Compatibility layer for legacy imports


def start_admin_tools(bot):
    """Start the admin tools via the command center."""
>>>>>>> main
    start_command_center(bot)


__all__ = ["start_admin_tools", "handle_command", "live_feed"]
