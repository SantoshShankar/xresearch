"""Generate static dashboard from history.json."""

from src.core.history import load_history
from src.dashboard.generate import generate_dashboard

history = load_history()
generate_dashboard(history)
