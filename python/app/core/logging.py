"""Log lines for the agent, so ``docker compose logs -f python`` shows each ticket being worked on.

Every line starts with the ticket id, so one ticket's story can be found with ``grep T-1006``.
"""
from __future__ import annotations

import logging
import os


def setup_logging() -> None:
    """Send the app's log lines to the terminal. LOG_LEVEL=DEBUG also shows each tool's full result."""
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s", datefmt="%H:%M:%S")
