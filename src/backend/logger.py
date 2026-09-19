"""
logger.py

Timestamped file logging with auto-rotation and 14-day retention. All backend
steps write to a per-run log file; older logs are pruned daily.

The discount date range is logged prominently at the start of each run so failures
can be traced to the specific week. Verbose mapping details (item -> ref resolution,
confidence, method, failures) are logged for post-mortem analysis.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
RETENTION_DAYS = 14


def _prune_old_logs():
    """Delete logs older than RETENTION_DAYS, idempotent."""
    if not LOG_DIR.exists():
        return
    cutoff = time.time() - (RETENTION_DAYS * 86400)
    for logfile in LOG_DIR.glob("discount-map-*.log"):
        if logfile.stat().st_mtime < cutoff:
            try:
                logfile.unlink()
            except Exception:
                pass


class DiscountLogger:
    """Timestamped logger for a single discount-week mapping run."""

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        self.path = LOG_DIR / f"discount-map-{timestamp}.log"
        self.file = open(self.path, "w", encoding="utf-8", buffering=1)
        _prune_old_logs()
        self._log(f"=== WRFrontiers Discount Mapping Pipeline ===")
        self._log(f"Log: {self.path}")
        self._log(f"Started: {datetime.now().isoformat()}")

    def _log(self, msg: str):
        ts = datetime.now().isoformat()
        line = f"[{ts}] {msg}\n"
        self.file.write(line)
        sys.stdout.write(line)  # also to stdout for immediate visibility

    def start_run(self, items_str: str, date_range_str: str):
        """Log the start of a mapping run with prominent date range."""
        self._log("")
        self._log("=" * 72)
        self._log(f"TARGET DISCOUNT WEEK: {date_range_str}")
        self._log(f"ITEMS TO MAP ({len([i for i in items_str.split(',') if i.strip()])}): {items_str}")
        self._log("=" * 72)
        self._log("")

    def step(self, step_name: str):
        """Log the start of a processing step."""
        self._log(f"[STEP] {step_name}")

    def info(self, msg: str):
        """Log an info-level message."""
        self._log(f"[INFO] {msg}")

    def mapping(self, name: str, refs: list[str], method: str, confidence: float, detail: str = ""):
        """Log a successful mapping resolution."""
        refs_str = ", ".join(refs)
        detail_str = f" | {detail}" if detail else ""
        self._log(f"[MAP] {name:20} -> {refs_str:50} ({method}, conf={confidence:.2f}){detail_str}")

    def mapping_fail(self, name: str, best_guess: str, confidence: float, reason: str = ""):
        """Log a failed mapping (below confidence threshold or unmappable)."""
        reason_str = f" | {reason}" if reason else ""
        self._log(f"[FAIL] {name:20} -> best={best_guess:50} (conf={confidence:.2f}){reason_str}")

    def warning(self, msg: str):
        """Log a warning."""
        self._log(f"[WARN] {msg}")

    def error(self, msg: str):
        """Log an error."""
        self._log(f"[ERROR] {msg}")

    def result(self, summary: str):
        """Log the final result."""
        self._log("")
        self._log(f"[RESULT] {summary}")
        self._log(f"Finished: {datetime.now().isoformat()}")
        self._log(f"Log file: {self.path}")

    def close(self):
        """Flush and close the log file."""
        if self.file:
            self.file.close()
