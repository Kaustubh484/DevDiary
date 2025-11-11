"""
Configuration management system for DevDiary.

Provides YAML-based configuration with environment variable overrides,
automatic config file discovery, and sensible defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)

# Default excluded patterns from Phase 1
DEFAULT_EXCLUDED_PATTERNS = [
    "venv/",
    ".venv/",
    "__pycache__",
    ".git/",
    "env/",
    "site-packages",
    "/bin/",
    "/lib/",
    "dist-info",
]


@dataclass
class OllamaConfig:
    """
    Configuration for Ollama LLM integration.

    Attributes:
        enabled: Whether to use Ollama for summarization
        model: Model name to use (e.g., "llama3")
        endpoint: Ollama server endpoint URL
        timeout: Request timeout in seconds
    """
    enabled: bool = True
    model: str = "llama3"
    endpoint: str = "http://localhost:11434"
    timeout: int = 120


@dataclass
class ScanningConfig:
    """
    Configuration for repository scanning behavior.

    Attributes:
        root_path: Root directory to scan for Git repositories
        excluded_patterns: Patterns to exclude from file analysis
        max_repos: Maximum number of repositories to scan (None = unlimited)
        include_hidden: Whether to include hidden directories (starting with .)
    """
    root_path: str = "~/dev"
    excluded_patterns: List[str] = field(default_factory=lambda: DEFAULT_EXCLUDED_PATTERNS.copy())
    max_repos: Optional[int] = None
    include_hidden: bool = False


@dataclass
class CacheConfig:
    """
    Configuration for commit summary caching.

    Attributes:
        enabled: Whether to enable caching
        path: Cache file path (None = use default location)
        max_age_days: Maximum age of cache entries in days
    """
    enabled: bool = True
    path: Optional[str] = None
    max_age_days: int = 30


@dataclass
class UIConfig:
    """
    Configuration for user interface preferences.

    Attributes:
        theme: UI theme ("dark" or "light")
        default_mode: Default scan mode (today, weekly, monthly, custom)
        show_diff_stats: Show diff statistics in UI
        show_charts: Show charts and visualizations
        page_layout: Page layout ("wide" or "centered")
    """
    theme: str = "dark"
    default_mode: str = "weekly"
    show_diff_stats: bool = True
    show_charts: bool = True
    page_layout: str = "wide"


@dataclass
class ExportConfig:
    """
    Configuration for exporting summaries.

    Attributes:
        default_format: Default export format (markdown, html, json, pdf)
        output_directory: Directory to save exported files
        filename_pattern: Pattern for export filenames (supports {mode}, {date})
    """
    default_format: str = "markdown"
    output_directory: str = "~/Downloads"
    filename_pattern: str = "devdiary_{mode}_{date}"


@dataclass
class DevDiaryConfig:
    """
    Complete DevDiary configuration.

    Aggregates all configuration sections and provides methods for
    loading, saving, and managing configuration files.
    """
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    scanning: ScanningConfig = field(default_factory=ScanningConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> DevDiaryConfig:
        """
        Load configuration from a YAML file or discover default config file.

        Args:
            config_path: Explicit path to config file. If None, searches default locations.

        Returns:
            DevDiaryConfig instance with loaded settings

        Raises:
            FileNotFoundError: If explicit config_path is provided but doesn't exist
            ImportError: If PyYAML is not installed
        """
        if yaml is None:
            logger.warning("PyYAML not installed, using default configuration")
            return cls()

        # If explicit path provided, use it
        if config_path is not None:
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            logger.info(f"Loading configuration from: {config_path}")
            return cls._load_from_file(config_path)

        # Otherwise, search for config file
        found_config = cls._find_config_file()
        if found_config:
            logger.info(f"Found configuration file: {found_config}")
            return cls._load_from_file(found_config)

        logger.info("No configuration file found, using defaults")
        return cls()

    @classmethod
    def _find_config_file(cls) -> Optional[Path]:
        """
        Search for configuration file in default locations.

        Search order:
            1. ./config.yaml
            2. ./devdiary.yaml
            3. ~/.devdiary/config.yaml
            4. ~/.config/devdiary/config.yaml

        Returns:
            Path to first found config file, or None
        """
        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "devdiary.yaml",
            Path.home() / ".devdiary" / "config.yaml",
            Path.home() / ".config" / "devdiary" / "config.yaml",
        ]

        for path in search_paths:
            if path.exists() and path.is_file():
                logger.debug(f"Found config file at: {path}")
                return path

        logger.debug("No config file found in default locations")
        return None

    @classmethod
    def _load_from_file(cls, config_path: Path) -> DevDiaryConfig:
        """
        Parse YAML configuration file and create config instance.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            DevDiaryConfig instance populated from file
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            logger.debug(f"Loaded configuration data: {data}")

            # Apply environment variable overrides
            data = cls._apply_env_overrides(data)

            # Create config objects from nested dicts
            config = cls(
                ollama=OllamaConfig(**data.get('ollama', {})),
                scanning=ScanningConfig(**data.get('scanning', {})),
                cache=CacheConfig(**data.get('cache', {})),
                ui=UIConfig(**data.get('ui', {})),
                export=ExportConfig(**data.get('export', {})),
            )

            logger.info("Configuration loaded successfully")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            raise ValueError(f"Invalid YAML configuration: {e}") from e
        except TypeError as e:
            logger.error(f"Invalid configuration structure: {e}")
            raise ValueError(f"Configuration has invalid fields: {e}") from e

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """
        Override configuration values with environment variables.

        Supported environment variables:
            - DEVDIARY_ROOT: Overrides scanning.root_path
            - DEVDIARY_MODEL: Overrides ollama.model
            - DEVDIARY_OLLAMA_ENDPOINT: Overrides ollama.endpoint

        Args:
            data: Configuration dictionary

        Returns:
            Modified configuration dictionary with env var overrides
        """
        # Ensure nested dicts exist
        if 'scanning' not in data:
            data['scanning'] = {}
        if 'ollama' not in data:
            data['ollama'] = {}

        # Apply overrides
        if 'DEVDIARY_ROOT' in os.environ:
            data['scanning']['root_path'] = os.environ['DEVDIARY_ROOT']
            logger.debug(f"Applied DEVDIARY_ROOT override: {os.environ['DEVDIARY_ROOT']}")

        if 'DEVDIARY_MODEL' in os.environ:
            data['ollama']['model'] = os.environ['DEVDIARY_MODEL']
            logger.debug(f"Applied DEVDIARY_MODEL override: {os.environ['DEVDIARY_MODEL']}")

        if 'DEVDIARY_OLLAMA_ENDPOINT' in os.environ:
            data['ollama']['endpoint'] = os.environ['DEVDIARY_OLLAMA_ENDPOINT']
            logger.debug(f"Applied DEVDIARY_OLLAMA_ENDPOINT override: {os.environ['DEVDIARY_OLLAMA_ENDPOINT']}")

        return data

    def save(self, config_path: Optional[Path] = None) -> None:
        """
        Save configuration to a YAML file.

        Args:
            config_path: Path to save config file. If None, saves to ~/.devdiary/config.yaml

        Raises:
            ImportError: If PyYAML is not installed
        """
        if yaml is None:
            raise ImportError("PyYAML is required to save configuration files. Install with: pip install pyyaml")

        # Determine save path
        if config_path is None:
            config_path = Path.home() / ".devdiary" / "config.yaml"

        # Create directory if needed
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and save
        data = asdict(self)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Configuration saved to: {config_path}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", exc_info=True)
            raise

    def get_expanded_root_path(self) -> Path:
        """
        Get the scanning root path with ~ expansion.

        Returns:
            Fully expanded Path object
        """
        return Path(os.path.expanduser(self.scanning.root_path))

    def get_cache_path(self) -> Path:
        """
        Get the cache file path or default location.

        Returns:
            Path to cache file
        """
        if self.cache.path:
            return Path(os.path.expanduser(self.cache.path))

        # Default cache location (platform-aware)
        import sys
        if sys.platform == "darwin":  # macOS
            cache_dir = Path.home() / "Library" / "Caches" / "DevDiary"
        elif sys.platform == "win32":  # Windows
            cache_dir = Path.home() / "AppData" / "Local" / "DevDiary" / "Cache"
        else:  # Linux/Unix
            cache_dir = Path.home() / ".cache" / "devdiary"

        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "commit_cache.json"

    def get_export_directory(self) -> Path:
        """
        Get the export directory with ~ expansion.

        Returns:
            Fully expanded Path object
        """
        export_dir = Path(os.path.expanduser(self.export.output_directory))
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir


# Global configuration instance
_global_config: Optional[DevDiaryConfig] = None


def get_config() -> DevDiaryConfig:
    """
    Get or create the global configuration instance.

    Returns:
        Global DevDiaryConfig instance
    """
    global _global_config

    if _global_config is None:
        logger.debug("Initializing global configuration")
        _global_config = DevDiaryConfig.load()

    return _global_config


def reload_config(config_path: Optional[Path] = None) -> DevDiaryConfig:
    """
    Reload the global configuration from file.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Reloaded DevDiaryConfig instance
    """
    global _global_config

    logger.info("Reloading configuration")
    _global_config = DevDiaryConfig.load(config_path)

    return _global_config


def reset_config() -> DevDiaryConfig:
    """
    Reset the global configuration to defaults.

    Returns:
        New DevDiaryConfig instance with default values
    """
    global _global_config

    logger.info("Resetting configuration to defaults")
    _global_config = DevDiaryConfig()

    return _global_config
