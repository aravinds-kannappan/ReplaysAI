"""
Live refresh scheduler — runs continuously after backfill is complete.
Only handles live / upcoming games (not historical).

Usage:
  python -m backend.ingestion.scheduler

Polls every 60s during game hours, 5min otherwise.
"""
import signal
import time
from datetime import datetime

_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n[Scheduler] Shutting down gracefully…")
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def _is_game_hours() -> bool:
    """Roughly 10 am – 1 am ET = 14:00 – 06:00 UTC."""
    h = datetime.utcnow().hour
    return h >= 14 or h < 6


def _poll_interval_seconds() -> int:
    return 60 if _is_game_hours() else 300


def run_scheduler() -> None:
    from ingestion.nba_ingester import run_live_refresh as nba_refresh
    from ingestion.nfl_ingester import run_live_refresh as nfl_refresh

    print("[Scheduler] Live refresh scheduler started. Ctrl-C to stop.")
    print("[Scheduler] Note: run seed_data.py first for historical backfill.\n")

    while _running:
        tick = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        interval = _poll_interval_seconds()
        print(f"[{tick}] Polling (next in {interval}s)…")

        try:
            nba_refresh(days_back=2)
        except Exception as e:
            print(f"  NBA refresh error: {e}")

        try:
            nfl_refresh()
        except Exception as e:
            print(f"  NFL refresh error: {e}")

        # Sleep in short chunks so SIGINT is responsive
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    print("[Scheduler] Stopped.")


if __name__ == "__main__":
    run_scheduler()
