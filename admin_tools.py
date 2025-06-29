from command_center import handle_command, live_feed, start_command_center

# Compatibility layer for legacy imports


def start_admin_tools(bot):
    """Start the admin tools via the command center."""
    start_command_center(bot)


__all__ = ["start_admin_tools", "handle_command", "live_feed"]
