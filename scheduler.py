"""
Simple file-based 15-day scheduler.

Tracks the last run timestamp in data/last_run.json.
`should_run()` returns True when SCHEDULE_DAYS days have elapsed.
`run_loop()` polls hourly and fires the analysis callback when due.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from config import LAST_RUN_FILE, SCHEDULE_DAYS


def _load_state() -> dict:
    if os.path.exists(LAST_RUN_FILE):
        try:
            with open(LAST_RUN_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict) -> None:
    with open(LAST_RUN_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_last_run() -> Optional[datetime]:
    state = _load_state()
    ts = state.get("last_run")
    if ts:
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            pass
    return None


def get_next_run() -> Optional[datetime]:
    last = get_last_run()
    if last:
        return last + timedelta(days=SCHEDULE_DAYS)
    return None


def mark_run_complete() -> None:
    state = _load_state()
    state["last_run"] = datetime.now().isoformat()
    _save_state(state)


def should_run() -> bool:
    """Returns True if SCHEDULE_DAYS have elapsed since the last run."""
    last = get_last_run()
    if last is None:
        return True  # Never run before — run now
    return datetime.now() >= last + timedelta(days=SCHEDULE_DAYS)


def status_summary() -> str:
    """Human-readable status string."""
    last = get_last_run()
    next_run = get_next_run()

    if last is None:
        return "No previous run found. Analysis will run immediately."

    last_str = last.strftime("%B %d, %Y at %I:%M %p")
    if next_run:
        now = datetime.now()
        if now >= next_run:
            return f"Last run: {last_str}\nNext run: OVERDUE — run `python main.py run` now"
        delta = next_run - now
        days = delta.days
        hours = delta.seconds // 3600
        next_str = next_run.strftime("%B %d, %Y at %I:%M %p")
        return (
            f"Last run:  {last_str}\n"
            f"Next run:  {next_str}  (in {days}d {hours}h)"
        )
    return f"Last run: {last_str}"


def run_loop(callback: Callable[[], None], check_interval_seconds: int = 3600) -> None:
    """
    Blocking loop that calls `callback()` whenever SCHEDULE_DAYS days have passed.

    callback   — zero-arg function that runs the full analysis
    check_interval_seconds — how often to check (default: every hour)
    """
    print(f"Scheduler started. Checking every {check_interval_seconds // 60} minute(s).")
    print(f"Analysis fires every {SCHEDULE_DAYS} days.")
    print("Press Ctrl+C to stop.\n")

    while True:
        if should_run():
            print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] Due date reached — running analysis...")
            try:
                callback()
                mark_run_complete()
            except Exception as e:
                print(f"Analysis failed: {e}")
                print("Will retry at next check interval.")
        else:
            next_run = get_next_run()
            if next_run:
                print(
                    f"[{datetime.now():%Y-%m-%d %H:%M}] "
                    f"Next run scheduled for {next_run:%Y-%m-%d %H:%M}",
                    end="\r",
                )

        time.sleep(check_interval_seconds)
