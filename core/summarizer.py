"""
LLM summarization service for DevDiary.

Provides intelligent summarization of commits, repositories, and scan results
using Ollama-powered language models with graceful fallbacks.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, Dict, Any, List

from core.types import (
    ScanResult,
    RepositorySummary,
    CommitSummary,
    WorkType,
    ScanProgress,
)
from core.config import DevDiaryConfig, get_config
from journal.summarize import (
    classify_and_summarize_commit,
    generate_repo_standup_paragraph,
    generate_team_scrum_paragraph,
    get_ollama_client,
    _time_window_phrase,
)

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """Exception raised when summarization fails."""
    pass


class LLMSummarizer:
    """
    Service for LLM-powered summarization of Git activity.

    Provides methods for summarizing individual commits, repositories,
    and complete scan results with progress tracking and graceful fallbacks.
    """

    def __init__(self, config: Optional[DevDiaryConfig] = None):
        """
        Initialize the LLM summarizer.

        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config if config is not None else get_config()
        self._ollama_available: Optional[bool] = None
        logger.info("LLMSummarizer initialized")
        logger.debug(f"Ollama enabled in config: {self.config.ollama.enabled}")
        logger.debug(f"Ollama model: {self.config.ollama.model}")

    def is_available(self) -> bool:
        """
        Check if LLM summarization is available.

        Returns:
            True if Ollama is enabled and accessible, False otherwise
        """
        # Return cached result if available
        if self._ollama_available is not None:
            return self._ollama_available

        # Check if disabled in config
        if not self.config.ollama.enabled:
            logger.info("LLM summarization disabled in config")
            self._ollama_available = False
            return False

        # Test Ollama connection
        try:
            logger.debug("Testing Ollama connection...")
            get_ollama_client()
            logger.info("LLM is available and ready")
            self._ollama_available = True
            return True
        except Exception as e:
            logger.warning(f"LLM is not available: {e}")
            self._ollama_available = False
            return False

    def summarize_commit(
        self,
        commit: CommitSummary,
        repo_name: str,
        since_date: str,
        to_date: Optional[str],
        mode: str,
    ) -> CommitSummary:
        """
        Summarize a single commit using LLM.

        Args:
            commit: CommitSummary to enhance
            repo_name: Name of the repository
            since_date: Start date for context
            to_date: End date for context
            mode: Scan mode for context

        Returns:
            Enhanced CommitSummary with LLM-generated content
        """
        if not self.is_available():
            logger.debug(f"LLM not available, using basic summary for {commit.commit_hash}")
            # Return commit with basic bullet
            commit.bullet = f"- [{commit.work_type.value}] `{commit.commit_hash}`: {commit.message}"
            commit.team_snippet = commit.message[:60].rstrip(".")
            return commit

        try:
            logger.debug(f"Summarizing commit {commit.commit_hash} with LLM")

            # Build commit block for classifier (mimicking raw git log format)
            commit_block = f"{commit.commit_hash} {commit.message}"

            # Call LLM classifier
            result = classify_and_summarize_commit(
                commit_block=commit_block,
                repo_name=repo_name,
                since_date=since_date,
                to_date=to_date,
                mode=mode,
            )

            # Update commit with LLM results
            commit.work_type = WorkType(result.get("work_type", "other"))
            commit.bullet = result.get("bullet", commit.bullet)
            commit.team_snippet = result.get("team_snippet", commit.team_snippet)

            logger.debug(f"Successfully summarized {commit.commit_hash} as {commit.work_type.value}")
            return commit

        except Exception as e:
            logger.warning(f"Failed to summarize commit {commit.commit_hash}: {e}")
            # Fallback to basic summary
            commit.bullet = f"- [{commit.work_type.value}] `{commit.commit_hash}`: {commit.message}"
            commit.team_snippet = commit.message[:60].rstrip(".")
            return commit

    def summarize_repository(
        self,
        repo_summary: RepositorySummary,
        since_date: str,
        to_date: Optional[str],
        mode: str,
    ) -> RepositorySummary:
        """
        Summarize all commits in a repository using LLM.

        Args:
            repo_summary: RepositorySummary to enhance
            since_date: Start date for context
            to_date: End date for context
            mode: Scan mode for context

        Returns:
            Enhanced RepositorySummary with LLM-generated summaries
        """
        logger.info(f"Summarizing repository: {repo_summary.repo_name}")

        if not self.is_available():
            logger.debug(f"LLM not available, using basic summaries for {repo_summary.repo_name}")
            # Create basic bullets from commit messages
            repo_summary.bullets = [
                f"- [{c.work_type.value}] `{c.commit_hash}`: {c.message}"
                for c in repo_summary.commits
            ]
            repo_summary.team_snippets = [
                c.message[:60].rstrip(".") for c in repo_summary.commits
            ]
            repo_summary.standup_summary = (
                f"In {repo_summary.repo_name}, made {repo_summary.commit_count} commits."
            )
            return repo_summary

        try:
            # Summarize each commit with LLM
            logger.debug(f"Summarizing {len(repo_summary.commits)} commits in {repo_summary.repo_name}")

            summarized_commits: List[CommitSummary] = []
            for commit in repo_summary.commits:
                summarized = self.summarize_commit(
                    commit, repo_summary.repo_name, since_date, to_date, mode
                )
                summarized_commits.append(summarized)

            # Update repository with summarized commits
            repo_summary.commits = summarized_commits

            # Extract bullets and snippets
            repo_summary.bullets = [c.bullet for c in summarized_commits]
            repo_summary.team_snippets = [c.team_snippet for c in summarized_commits]

            # Recalculate work type counts
            work_type_counts: Dict[WorkType, int] = {}
            for commit in summarized_commits:
                work_type_counts[commit.work_type] = (
                    work_type_counts.get(commit.work_type, 0) + 1
                )
            repo_summary.work_type_counts = work_type_counts

            # Generate standup paragraph
            time_window = _time_window_phrase(mode, since_date, to_date)
            repo_summary.standup_summary = generate_repo_standup_paragraph(
                repo_name=repo_summary.repo_name,
                time_window=time_window,
                bullets=repo_summary.bullets,
                team_snips=repo_summary.team_snippets,
            )

            logger.info(f"Successfully summarized {repo_summary.repo_name} ({len(summarized_commits)} commits)")
            return repo_summary

        except Exception as e:
            logger.error(f"Failed to summarize repository {repo_summary.repo_name}: {e}", exc_info=True)
            # Fallback to basic summaries
            repo_summary.bullets = [
                f"- [{c.work_type.value}] `{c.commit_hash}`: {c.message}"
                for c in repo_summary.commits
            ]
            repo_summary.team_snippets = [
                c.message[:60].rstrip(".") for c in repo_summary.commits
            ]
            repo_summary.standup_summary = (
                f"In {repo_summary.repo_name}, made {repo_summary.commit_count} commits."
            )
            return repo_summary

    def summarize_scan_result(
        self,
        scan_result: ScanResult,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
    ) -> ScanResult:
        """
        Summarize an entire scan result using LLM.

        Args:
            scan_result: ScanResult to enhance with summaries
            progress_callback: Optional callback for progress updates

        Returns:
            Enhanced ScanResult with LLM-generated summaries
        """
        logger.info(f"Summarizing scan result with {len(scan_result.repositories)} repositories")

        if not self.is_available():
            logger.info("LLM not available, returning scan result without summaries")
            return scan_result

        try:
            total_repos = len(scan_result.repositories)
            summarized_repos: List[RepositorySummary] = []

            # Summarize each repository
            for idx, repo in enumerate(scan_result.repositories, start=1):
                # Send progress update
                if progress_callback:
                    progress = ScanProgress(
                        total_repos=total_repos,
                        current_repo=idx,
                        current_repo_name=repo.repo_name,
                        phase="summarizing",
                        message=f"Summarizing {repo.repo_name}...",
                    )
                    progress_callback(progress)

                # Summarize repository
                summarized_repo = self.summarize_repository(
                    repo,
                    since_date=scan_result.since_date or "",
                    to_date=scan_result.to_date,
                    mode=str(scan_result.scan_mode),
                )
                summarized_repos.append(summarized_repo)

            # Update scan result with summarized repos
            scan_result.repositories = summarized_repos

            # Generate team-level summary
            logger.info("Generating team-level summary")

            # Convert repositories to dict format for team summary
            repo_summaries = [
                {
                    "repo_name": r.repo_name,
                    "standup_summary": r.standup_summary,
                }
                for r in summarized_repos
            ]

            scan_result.team_summary = generate_team_scrum_paragraph(
                repo_summaries=repo_summaries,
                since_date=scan_result.since_date or "",
                to_date=scan_result.to_date,
                mode=str(scan_result.scan_mode),
            )

            # Final progress update
            if progress_callback:
                progress = ScanProgress(
                    total_repos=total_repos,
                    current_repo=total_repos,
                    current_repo_name="",
                    phase="complete",
                    message=f"Summarization complete: {total_repos} repositories",
                )
                progress_callback(progress)

            logger.info(f"Successfully summarized scan result ({total_repos} repositories)")
            return scan_result

        except Exception as e:
            logger.error(f"Failed to summarize scan result: {e}", exc_info=True)
            raise SummarizationError(f"Summarization failed: {e}") from e

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Ollama connection and return status information.

        Returns:
            Dictionary with:
                - available (bool): Whether LLM is available
                - models (list): List of available model names
                - error (str|None): Error message if unavailable
        """
        logger.info("Testing Ollama connection")

        if not self.config.ollama.enabled:
            logger.info("Ollama disabled in config")
            return {
                "available": False,
                "models": [],
                "error": "LLM summarization disabled in configuration",
            }

        try:
            client = get_ollama_client()
            logger.debug("Successfully connected to Ollama")

            # Get list of models
            models_response = client.list()
            available_models: List[str] = []

            if hasattr(models_response, "models"):
                available_models = [model.model for model in models_response.models]
            elif isinstance(models_response, dict) and "models" in models_response:
                available_models = [
                    m.get("name", m.get("model", ""))
                    for m in models_response["models"]
                ]

            logger.info(f"Ollama connection successful, {len(available_models)} models available")

            return {
                "available": True,
                "models": available_models,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return {
                "available": False,
                "models": [],
                "error": str(e),
            }
