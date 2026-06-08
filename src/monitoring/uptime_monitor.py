from datetime import datetime

class UptimeMonitor:
    """Tracks and calculates the bot's operational uptime."""
    
    def __init__(self):
        self.start_time = datetime.now()

    def get_uptime(self) -> str:
        """Returns a human-readable uptime string."""
        delta = datetime.now() - self.start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        if minutes > 0: parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        
        return " ".join(parts)

# Global monitor instance
uptime_monitor = UptimeMonitor()
