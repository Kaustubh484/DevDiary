"""
DevDiary Core Module
====================

Provides the core functionality for DevDiary including:
- Type definitions and data structures
- Configuration management
- Repository scanning
- LLM-powered summarization
- Multi-format export

Version: 2.0.0
"""

__version__ = "2.0.0"

# Type definitions
from .types import (
    WorkType,
    ScanMode,
    CommitSummary,
    RepositorySummary,
    ScanResult,
    ScanProgress,
    ExportOptions,
)

# Configuration management
from .config import (
    OllamaConfig,
    ScanningConfig,
    CacheConfig,
    UIConfig,
    ExportConfig,
    DevDiaryConfig,
    get_config,
    reload_config,
    reset_config,
)

# Repository scanner
from .scanner import (
    RepositoryScanner,
)

# LLM summarizer
from .summarizer import (
    LLMSummarizer,
    SummarizationError,
)

# Export service
from .exporter import (
    Exporter,
)

__all__ = [
    # Version
    "__version__",
    # Types
    "WorkType",
    "ScanMode",
    "CommitSummary",
    "RepositorySummary",
    "ScanResult",
    "ScanProgress",
    "ExportOptions",
    # Config
    "OllamaConfig",
    "ScanningConfig",
    "CacheConfig",
    "UIConfig",
    "ExportConfig",
    "DevDiaryConfig",
    "get_config",
    "reload_config",
    "reset_config",
    # Scanner
    "RepositoryScanner",
    # Summarizer
    "LLMSummarizer",
    "SummarizationError",
    # Exporter
    "Exporter",
]
