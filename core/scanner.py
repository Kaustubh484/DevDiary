"""
Repository scanning service for DevDiary.

Provides a clean interface for scanning Git repositories, extracting commits,
and building structured summaries with progress tracking.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from core.types import (
    ScanResult,
    RepositorySummary,
    ScanMode,
    ScanProgress,
    CommitSummary,
    WorkType,
)
from core.config import DevDiaryConfig, get_config
from journal.multi_repo_git_utils import (
    find_git_repos,
    get_commits_from_repo,
    get_today_date,
    get_past_days_date,
    get_first_day_of_month,
)

logger = logging.getLogger(__name__)


def get_commit_stats(repo_path: Path, commit_hash: str) -> Optional[dict]:
    """
    Get commit statistics (files changed, insertions, deletions).

    Args:
        repo_path: Path to the Git repository
        commit_hash: Commit hash to analyze

    Returns:
        Dictionary with 'files_changed', 'insertions', 'deletions', or None on error
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "show", "--shortstat", "--oneline", commit_hash],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            return None

        # Parse shortstat line like: "3 files changed, 45 insertions(+), 12 deletions(-)"
        output = result.stdout
        stats = {"files_changed": 0, "insertions": 0, "deletions": 0}

        # Extract files changed
        files_match = re.search(r'(\d+) files? changed', output)
        if files_match:
            stats["files_changed"] = int(files_match.group(1))

        # Extract insertions
        insertions_match = re.search(r'(\d+) insertions?\(\+\)', output)
        if insertions_match:
            stats["insertions"] = int(insertions_match.group(1))

        # Extract deletions
        deletions_match = re.search(r'(\d+) deletions?\(-\)', output)
        if deletions_match:
            stats["deletions"] = int(deletions_match.group(1))

        return stats

    except Exception as e:
        logger.warning(f"Failed to get commit stats for {commit_hash}: {e}")
        return None


class RepositoryScanner:
    """
    Service for scanning Git repositories and building structured summaries.

    Provides methods for finding repositories, scanning commits, and tracking
    progress through multi-repository scans.
    """

    def __init__(self, config: Optional[DevDiaryConfig] = None):
        """
        Initialize the repository scanner.

        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config if config is not None else get_config()
        logger.info("RepositoryScanner initialized")
        logger.debug(f"Using root_path: {self.config.scanning.root_path}")

    def find_repositories(self, root_path: Optional[Path] = None) -> List[Path]:
        """
        Find all Git repositories under the given root path.

        Args:
            root_path: Root directory to search. If None, uses config root_path.

        Returns:
            List of Path objects pointing to Git repositories
        """
        if root_path is None:
            root_path = self.config.get_expanded_root_path()

        logger.info(f"Finding repositories under {root_path}")

        repos = find_git_repos(root_path)
        logger.debug(f"Found {len(repos)} repositories")

        # Apply max_repos limit if configured
        if self.config.scanning.max_repos is not None:
            original_count = len(repos)
            repos = repos[: self.config.scanning.max_repos]
            if len(repos) < original_count:
                logger.info(
                    f"Limited to {len(repos)} repositories (max_repos={self.config.scanning.max_repos})"
                )

        logger.info(f"Returning {len(repos)} repositories")
        return repos

    def scan_repository(
        self,
        repo_path: Path,
        since_date: str,
        to_date: Optional[str] = None,
    ) -> Optional[RepositorySummary]:
        """
        Scan a single repository for commits within the date range.

        Args:
            repo_path: Path to the Git repository
            since_date: Start date (ISO format YYYY-MM-DD)
            to_date: End date (ISO format YYYY-MM-DD), optional

        Returns:
            RepositorySummary with commits, or None if no commits found
        """
        logger.info(f"Scanning repository: {repo_path.name}")
        logger.debug(f"Date range: {since_date} to {to_date or 'now'}")

        # Get raw commit log
        raw_log = get_commits_from_repo(repo_path, since_date, to_date)

        if not raw_log:
            logger.debug(f"No commits found in {repo_path.name}")
            return None

        # Parse commits
        commits = self._parse_commits(raw_log, repo_path)

        if not commits:
            logger.debug(f"No valid commits parsed from {repo_path.name}")
            return None

        logger.info(f"Found {len(commits)} commits in {repo_path.name}")

        # Build work type counts
        work_type_counts = {}
        for commit in commits:
            work_type_counts[commit.work_type] = (
                work_type_counts.get(commit.work_type, 0) + 1
            )

        # Create repository summary
        return RepositorySummary(
            repo_name=repo_path.name,
            repo_path=repo_path,
            commits=commits,
            bullets=[],  # Will be populated by summarizer
            team_snippets=[],  # Will be populated by summarizer
            standup_summary="",  # Will be populated by summarizer
            work_type_counts=work_type_counts,
        )

    def _parse_commits(self, raw_log: str, repo_path: Path) -> List[CommitSummary]:
        """
        Parse raw commit log into structured CommitSummary objects.

        Args:
            raw_log: Raw log string with commits separated by ===COMMIT===
            repo_path: Path to repository (for fetching stats)

        Returns:
            List of CommitSummary objects
        """
        logger.debug("Parsing commit blocks")

        blocks = [b.strip() for b in raw_log.split("===COMMIT===") if b.strip()]
        commits = []

        for block in blocks:
            commit = self._parse_commit_block(block, repo_path)
            if commit:
                commits.append(commit)

        logger.debug(f"Parsed {len(commits)} commits from {len(blocks)} blocks")
        return commits

    def _parse_commit_block(
        self, block: str, repo_path: Path
    ) -> Optional[CommitSummary]:
        """
        Parse a single commit block into a CommitSummary.

        Args:
            block: Raw commit block text
            repo_path: Path to repository (for fetching stats)

        Returns:
            CommitSummary object or None if parsing failed
        """
        lines = block.strip().splitlines()
        if not lines:
            return None

        # First line is "hash message"
        first_line = lines[0]
        parts = first_line.split(maxsplit=1)

        if not parts:
            return None

        commit_hash = parts[0]
        message = parts[1] if len(parts) > 1 else ""

        # Heuristic work type classification (will be refined by LLM)
        work_type = self._heuristic_work_type(message)

        # Get commit statistics
        stats = get_commit_stats(repo_path, commit_hash)
        if stats:
            files_changed = stats["files_changed"]
            insertions = stats["insertions"]
            deletions = stats["deletions"]
        else:
            files_changed = 0
            insertions = 0
            deletions = 0

        return CommitSummary(
            commit_hash=commit_hash,
            work_type=work_type,
            bullet=f"- `{commit_hash}`: {message}",  # Simple bullet, will be enhanced by LLM
            team_snippet=message[:60].rstrip("."),
            message=message,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
        )

    def _heuristic_work_type(self, message: str) -> WorkType:
        """
        Classify commit work type using heuristic keyword matching.

        Args:
            message: Commit message

        Returns:
            WorkType enum value
        """
        msg_lower = message.lower()

        if any(k in msg_lower for k in ("fix", "bug", "hotfix", "patch")):
            return WorkType.BUGFIX
        if any(k in msg_lower for k in ("feat", "feature", "add", "implement")):
            return WorkType.FEATURE
        if any(k in msg_lower for k in ("refactor", "cleanup", "restructure")):
            return WorkType.REFACTOR
        if any(k in msg_lower for k in ("doc", "readme", "changelog")):
            return WorkType.DOCS
        if any(k in msg_lower for k in ("test", "spec", "unit test", "unittest")):
            return WorkType.TEST
        if any(k in msg_lower for k in ("perf", "optimiz")):
            return WorkType.PERF
        if any(k in msg_lower for k in ("build", "packag")):
            return WorkType.BUILD
        if any(k in msg_lower for k in ("ci", "pipeline", "workflow")):
            return WorkType.CI
        if any(k in msg_lower for k in ("chore", "deps", "dependency", "bump")):
            return WorkType.CHORE

        return WorkType.OTHER

    def scan_all(
        self,
        mode: ScanMode,
        since_date: Optional[str] = None,
        to_date: Optional[str] = None,
        selected_repos: Optional[List[Path]] = None,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
    ) -> ScanResult:
        """
        Scan all repositories and build a complete ScanResult.

        Args:
            mode: Scan mode (TODAY, WEEKLY, MONTHLY, CUSTOM)
            since_date: Optional explicit start date (required for CUSTOM mode)
            to_date: Optional end date
            selected_repos: Optional list of specific repos to scan
            progress_callback: Optional callback for progress updates

        Returns:
            ScanResult with all scanned repositories
        """
        logger.info(f"Starting scan_all with mode: {mode}")

        # Determine date range
        if since_date is None:
            since_date = self._get_since_date(mode)

        logger.info(f"Scan date range: {since_date} to {to_date or 'now'}")

        # Find repositories
        if selected_repos is not None:
            repos = selected_repos
            logger.info(f"Using {len(repos)} selected repositories")
        else:
            repos = self.find_repositories()

        total_repos = len(repos)
        logger.info(f"Scanning {total_repos} repositories")

        # Scan each repository
        summaries: List[RepositorySummary] = []

        for idx, repo_path in enumerate(repos, start=1):
            # Send progress update
            if progress_callback:
                progress = ScanProgress(
                    total_repos=total_repos,
                    current_repo=idx,
                    current_repo_name=repo_path.name,
                    phase="scanning",
                    message=f"Scanning {repo_path.name}...",
                )
                progress_callback(progress)

            # Scan repository
            summary = self.scan_repository(repo_path, since_date, to_date)
            if summary:
                summaries.append(summary)

        # Final progress update
        if progress_callback:
            progress = ScanProgress(
                total_repos=total_repos,
                current_repo=total_repos,
                current_repo_name="",
                phase="complete",
                message=f"Scan complete: {len(summaries)} repositories with commits",
            )
            progress_callback(progress)

        logger.info(
            f"Scan complete: {len(summaries)} of {total_repos} repositories have commits"
        )

        # Build result
        return ScanResult(
            repositories=summaries,
            team_summary="",  # Will be populated by summarizer
            scan_mode=mode,
            since_date=since_date,
            to_date=to_date,
            scan_time=datetime.now(),
        )

    def _get_since_date(self, mode: ScanMode) -> str:
        """
        Determine the since_date based on scan mode.

        Args:
            mode: Scan mode enum

        Returns:
            ISO date string (YYYY-MM-DD)
        """
        if mode == ScanMode.TODAY:
            return get_today_date()
        elif mode == ScanMode.WEEKLY:
            return get_past_days_date(7)
        elif mode == ScanMode.MONTHLY:
            return get_first_day_of_month()
        else:
            # CUSTOM mode requires explicit since_date
            logger.warning(f"CUSTOM mode requires explicit since_date, using today")
            return get_today_date()
