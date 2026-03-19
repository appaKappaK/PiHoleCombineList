"""Centralised logging setup — import ``setup_logging`` once at app startup."""

import logging
from logging.handlers import RotatingFileHandler

from .database import _DATA_DIR


def setup_logging() -> None:
    """Configure the ``phlist`` logger hierarchy.

    * **Session file** (``phlist.log``): truncated on each start — what the in-app viewer reads.
    * **History file** (``phlist_history.log``): appends across sessions, 512 KB cap, 1 backup.
    * **Console**: WARNING level (errors still print to terminal).
    """
    root = logging.getLogger("phlist")
    if root.handlers:
        return  # already configured (e.g. tests importing twice)
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                            datefmt="%-m/%-d/%y %-I:%M %p")

    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Session log — truncated on each start; shown in the in-app log viewer
    fh = logging.FileHandler(_DATA_DIR / "phlist.log", mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # History log — appends across sessions; rotates at 512 KB with 1 backup
    hh = RotatingFileHandler(
        _DATA_DIR / "phlist_history.log",
        mode="a", maxBytes=512 * 1024, backupCount=1, encoding="utf-8",
    )
    hh.setLevel(logging.DEBUG)
    hh.setFormatter(fmt)
    root.addHandler(hh)

    # Console handler — only warnings and above
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)
