"""Compatibility layer exposing admin functions from command_center."""

from command_center import handle_command, live_feed, start_command_center


def start_admin_tools(bot):
    """Start admin tools via the command center."""
    start_command_center(bot)


__all__ = ["start_admin_tools", "handle_command", "live_feed"]
