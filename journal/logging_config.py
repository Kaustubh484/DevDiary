"""
Platform-aware logging configuration for DevDiary.

Provides cross-platform logging setup with appropriate default log file locations
for Linux, macOS, and Windows.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def get_default_log_file() -> Path:
    """
    Get the default log file path based on the current platform.

    Returns:
        Path: Platform-specific log file path
            - Linux: ~/.local/state/devdiary/devdiary.log
            - macOS: ~/Library/Logs/DevDiary/devdiary.log
            - Windows: %LOCALAPPDATA%\DevDiary\devdiary.log
    """
    if sys.platform == "darwin":  # macOS
        log_dir = Path.home() / "Library" / "Logs" / "DevDiary"
    elif sys.platform == "win32":  # Windows
        app_data = Path.home() / "AppData" / "Local"
        log_dir = app_data / "DevDiary"
    else:  # Linux and other Unix-like systems
        log_dir = Path.home() / ".local" / "state" / "devdiary"

    # Ensure the directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir / "devdiary.log"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """
    Set up logging with file and/or console handlers.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
        log_file: Path to log file. If None, uses platform default.
        console: Whether to enable console logging

    Returns:
        logging.Logger: Configured root logger

    Example:
        >>> logger = setup_logging(logging.DEBUG, console=True)
        >>> logger.info("Application started")
    """
    # Get or create root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    if log_file is None:
        log_file = get_default_log_file()

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, warn on console
        print(f"Warning: Could not set up file logging at {log_file}: {e}", file=sys.stderr)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def setup_default_logging(verbose: bool = False) -> logging.Logger:
    """
    Set up logging with sensible defaults for the DevDiary application.

    Args:
        verbose: If True, use DEBUG level; otherwise use INFO level

    Returns:
        logging.Logger: Configured root logger

    Example:
        >>> logger = setup_default_logging(verbose=True)
        >>> logger.debug("Detailed debug information")
    """
    level = logging.DEBUG if verbose else logging.INFO
    return setup_logging(level=level, console=True)


# Convenience function to get a logger for a specific module
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        logging.Logger: Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    return logging.getLogger(name)
