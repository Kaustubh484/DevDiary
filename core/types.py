"""
Type definitions and data structures for DevDiary.

This module provides strongly-typed data structures for representing
Git commit summaries, repository analysis, and scan results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict


class WorkType(Enum):
    """Categories of work represented by commits."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"
    PERF = "perf"
    BUILD = "build"
    CI = "ci"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value


class ScanMode(Enum):
    """Time window modes for scanning Git repositories."""
    TODAY = "today"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value


@dataclass
class CommitSummary:
    """
    Summary of a single Git commit with classification and statistics.

    Attributes:
        commit_hash: Short or full Git commit hash
        work_type: Classification of the work type
        bullet: Formatted bullet point summary
        team_snippet: Short phrase for team-level aggregation
        message: Original commit message
        files_changed: Number of files modified in this commit
        insertions: Number of lines added
        deletions: Number of lines removed
    """
    commit_hash: str
    work_type: WorkType
    bullet: str
    team_snippet: str
    message: str = ""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0

    def __post_init__(self):
        """Ensure work_type is a WorkType enum."""
        if isinstance(self.work_type, str):
            try:
                self.work_type = WorkType(self.work_type.lower())
            except ValueError:
                self.work_type = WorkType.OTHER


@dataclass
class RepositorySummary:
    """
    Summary of all activity within a single Git repository.

    Attributes:
        repo_name: Name of the repository
        repo_path: Filesystem path to the repository
        commits: List of individual commit summaries
        bullets: Formatted bullet points for all commits
        team_snippets: Short phrases for team-level aggregation
        standup_summary: Natural language summary paragraph
        work_type_counts: Dictionary mapping WorkType to count
    """
    repo_name: str
    repo_path: Path
    commits: List[CommitSummary] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)
    team_snippets: List[str] = field(default_factory=list)
    standup_summary: str = ""
    work_type_counts: Dict[WorkType, int] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure repo_path is a Path object."""
        if not isinstance(self.repo_path, Path):
            self.repo_path = Path(self.repo_path)

    @property
    def commit_count(self) -> int:
        """Return the total number of commits in this repository."""
        return len(self.commits)

    @property
    def total_files_changed(self) -> int:
        """Return the total number of files changed across all commits."""
        return sum(commit.files_changed for commit in self.commits)

    @property
    def total_insertions(self) -> int:
        """Return the total number of lines inserted across all commits."""
        return sum(commit.insertions for commit in self.commits)

    @property
    def total_deletions(self) -> int:
        """Return the total number of lines deleted across all commits."""
        return sum(commit.deletions for commit in self.commits)


@dataclass
class ScanResult:
    """
    Complete results from a DevDiary repository scan.

    Attributes:
        repositories: List of repository summaries
        team_summary: Natural language summary across all repositories
        scan_mode: Mode used for this scan (today, weekly, etc.)
        since_date: Start date for the scan (ISO format)
        to_date: End date for the scan (ISO format), if applicable
        scan_time: Timestamp when the scan was performed
    """
    repositories: List[RepositorySummary] = field(default_factory=list)
    team_summary: str = ""
    scan_mode: ScanMode = ScanMode.TODAY
    since_date: Optional[str] = None
    to_date: Optional[str] = None
    scan_time: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Ensure scan_mode is a ScanMode enum."""
        if isinstance(self.scan_mode, str):
            try:
                self.scan_mode = ScanMode(self.scan_mode.lower())
            except ValueError:
                self.scan_mode = ScanMode.TODAY

    @property
    def total_repos(self) -> int:
        """Return the total number of repositories scanned."""
        return len(self.repositories)

    @property
    def total_commits(self) -> int:
        """Return the total number of commits across all repositories."""
        return sum(repo.commit_count for repo in self.repositories)

    @property
    def work_type_distribution(self) -> Dict[WorkType, int]:
        """
        Return the distribution of work types across all repositories.

        Returns:
            Dictionary mapping WorkType to total count across all repos
        """
        distribution: Dict[WorkType, int] = {}
        for repo in self.repositories:
            for commit in repo.commits:
                distribution[commit.work_type] = distribution.get(commit.work_type, 0) + 1
        return distribution

    def get_repos_with_activity(self) -> List[RepositorySummary]:
        """
        Return only repositories that have commits.

        Returns:
            List of RepositorySummary objects with at least one commit
        """
        return [repo for repo in self.repositories if repo.commit_count > 0]


@dataclass
class ScanProgress:
    """
    Progress tracking for repository scanning operations.

    Attributes:
        total_repos: Total number of repositories to scan
        current_repo: Index of the current repository being processed
        current_repo_name: Name of the repository being processed
        phase: Current phase of the scan (scanning, summarizing, complete)
        message: Optional status message
    """
    total_repos: int
    current_repo: int
    current_repo_name: str
    phase: str  # "scanning", "summarizing", "complete"
    message: str = ""

    @property
    def percentage(self) -> float:
        """
        Return the completion percentage (0-100).

        Returns:
            Float representing percentage complete
        """
        if self.total_repos == 0:
            return 100.0
        return (self.current_repo / self.total_repos) * 100.0

    @property
    def is_complete(self) -> bool:
        """
        Check if the scan is complete.

        Returns:
            True if phase is "complete"
        """
        return self.phase == "complete"


@dataclass
class ExportOptions:
    """
    Configuration options for exporting scan results.

    Attributes:
        format: Export format (markdown, html, json, pdf)
        include_bullets: Include commit bullet points
        include_standup: Include standup summaries
        include_team_summary: Include team-level summary
        include_stats: Include commit statistics
        include_diffs: Include diff information
    """
    format: str = "markdown"
    include_bullets: bool = True
    include_standup: bool = True
    include_team_summary: bool = True
    include_stats: bool = False
    include_diffs: bool = False

    @property
    def file_extension(self) -> str:
        """
        Return the file extension for the selected format.

        Returns:
            File extension string without the leading dot
        """
        format_map = {
            "markdown": "md",
            "html": "html",
            "json": "json",
            "pdf": "pdf",
            "text": "txt",
            "txt": "txt",
        }
        return format_map.get(self.format.lower(), "md")
