"""
utils/logger.py
~~~~~~~~~~~~~~~
Structured logging setup for the recon pipeline.

CONTRACT
--------
setup_logging(verbose=False, log_file=None)
    Configure the root ``recon_node`` logger.
    - verbose=False → INFO level
    - verbose=True  → DEBUG level
    - log_file supplied → also writes to that file (append mode)
    Idempotent — safe to call multiple times.

get_logger(name)
    Convenience wrapper for ``logging.getLogger(name)``.
    Returns a child logger under ``recon_node``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


# Module-level flag to prevent double-init
_initialized = False


def setup_logging(
    verbose:  bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure structured logging for the entire recon pipeline.

    Parameters
    ----------
    verbose:
        If True, set level to DEBUG.  Otherwise INFO.
    log_file:
        Optional path to a log file.  Logs are appended (not truncated).
        Parent directories are created if needed.

    Returns
    -------
    logging.Logger
        The root ``recon_node`` logger.
    """
    global _initialized

    logger = logging.getLogger("recon_node")
    level  = logging.DEBUG if verbose else logging.INFO

    if _initialized:
        # Just update level on re-call
        logger.setLevel(level)
        return logger

    logger.setLevel(level)

    # Console handler (stderr)
    fmt = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # always DEBUG in file
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for name in ("urllib3", "asyncio", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _initialized = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under ``recon_node``.

    Usage::

        from recon_node.utils.logger import get_logger
        log = get_logger(__name__)
        log.info("Starting scan")
    """
    if not name.startswith("recon_node"):
        name = f"recon_node.{name}"
    return logging.getLogger(name)


def reset_logging() -> None:
    """
    Reset the logging state (for testing only).

    Removes all handlers from the recon_node logger and clears
    the _initialized flag.
    """
    global _initialized
    logger = logging.getLogger("recon_node")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    _initialized = False
