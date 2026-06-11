"""Scheduler — the autonomous loop that keeps the channel publishing.

Runs a cycle, then sleeps until the next slot based on ``content.cadence_hours``
(measured from the last publish so restarts don't double-post). Errors in one
cycle are logged and the loop continues — autonomy shouldn't be brittle.
"""

from __future__ import annotations

import time

from .config import Config
from .pipeline import Pipeline
from .utils import get_logger

log = get_logger("viralagent.scheduler")


class Scheduler:
    def __init__(self, config: Config, *, dry_run: bool = False, no_upload: bool = False):
        self.config = config
        self.pipeline = Pipeline(config, dry_run=dry_run, no_upload=no_upload)

    def run_forever(self, *, max_cycles: int | None = None) -> None:
        cadence = float(self.config.content.get("cadence_hours", 12)) * 3600.0
        cycles = 0
        log.info("Daemon started. Cadence: %.1fh.", cadence / 3600.0)
        while True:
            wait = self._seconds_until_next(cadence)
            if wait > 0:
                log.info("Next cycle in %.1f min.", wait / 60.0)
                time.sleep(wait)
            try:
                self.pipeline.run_once()
            except Exception as exc:  # pragma: no cover - keep the loop alive
                log.exception("Cycle failed: %s", exc)
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                log.info("Reached max_cycles=%d; stopping.", max_cycles)
                return

    def _seconds_until_next(self, cadence: float) -> float:
        last = self.pipeline.state.last_published_ts()
        if last <= 0:
            return 0.0  # never published — go now
        elapsed = time.time() - last
        return max(cadence - elapsed, 0.0)
