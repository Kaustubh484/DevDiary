# journal/multi_repo_git_utils.py  (only the parts that change)
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from datetime import datetime,timedelta
from typing import List, Dict, Any, Optional

from .summarize import summarize_repo_text_block, generate_team_scrum_paragraph  # NEW

# ... (keep your existing EXCLUDED_PATTERNS, should_exclude, find_git_repos, get_commit_diff_stats)

# Patterns to exclude from file logs
EXCLUDED_PATTERNS = [
    "venv/", ".venv/", "__pycache__",
    ".git/", "env/", "site-packages", "/bin/", "/lib/", "dist-info"
]

def get_today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_past_days_date(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def get_first_day_of_month() -> str:
    today = datetime.now()
    return today.replace(day=1).strftime("%Y-%m-%d")

def should_exclude(line: str) -> bool:
    normalized = Path(line.strip()).as_posix().lower()
    return any(pattern in normalized for pattern in EXCLUDED_PATTERNS)

def find_git_repos(root_path: Path) -> list[Path]:
    git_repos = []
    for dirpath, dirnames, _ in os.walk(root_path):
        if ".git" in dirnames:
            git_repos.append(Path(dirpath))
            dirnames[:] = []  # Don't recurse into subfolders
    return git_repos

def get_commit_diff_stats(repo_path: Path, commit_hash: str) -> str:
    """Return git diff --stat output for a commit."""
    try:
        result = subprocess.run(
            ["git", "show", "--stat", "--oneline", commit_hash],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"[Error fetching diff: {result.stderr.strip()}]"
    except Exception as e:
        return f"[Exception: {e}]"


def get_commits_from_repo(repo_path: Path, since_date: str, to_date: str | None = None) -> str:
    try:
        date_range = ["--since", f"{since_date} 00:00"]
        if to_date:
            date_range += ["--until", f"{to_date} 23:59"]

        result = subprocess.run(
            ["git", "log", *date_range, "--pretty=format:===COMMIT===%n%h %s", "--name-only"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0 or not result.stdout.strip():
            return ""

        blocks = result.stdout.strip().split("===COMMIT===")
        included_blocks = []

        for block in blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue

            commit_header = lines[0]
            file_lines = lines[1:]
            filtered_files = [f for f in file_lines if not should_exclude(f)]

            if filtered_files:
                commit_hash = commit_header.split()[0]
                diff = get_commit_diff_stats(repo_path, commit_hash)
                included_blocks.append(
                    commit_header + "\n" + "\n".join(filtered_files) + "\n\n" + diff
                )

        if included_blocks:
            # IMPORTANT: we will keep COMMIT separators for summarizer splitting
            return "\n\n===COMMIT===\n\n".join(included_blocks)

    except Exception as e:
        return f"[Error reading repo {repo_path}]: {e}"

    return ""

def get_all_commits_across_repos(
    since_date: str,
    to_date: Optional[str] = None,
    root: str = "~/dev",
    summarize_with_llm: bool = True,
    mode: str = "today",
    selected_repos: Optional[List[Path]] = None,
) -> str:
    root_path = Path(os.path.expanduser(root))
    repos = selected_repos if selected_repos is not None else find_git_repos(root_path)

    repo_outputs: List[str] = []
    repo_summaries: List[Dict[str, Any]] = []

    for repo in repos:
        raw_log = get_commits_from_repo(repo, since_date, to_date=to_date)
        if not raw_log:
            continue

        if summarize_with_llm:
            repo_name = repo.name
            # existing classification creates bullets + team_snippets
            # NEW: it now also returns a natural standup paragraph
            summary_obj = summarize_repo_text_block(
                repo_name=repo_name,
                since_date=since_date,
                to_date=to_date,
                mode=mode,
                full_repo_block_text=raw_log,
            )
            repo_summaries.append(summary_obj)

            # build pretty section
            section = [f"### 📁 {repo_name}"]
            section += summary_obj["bullets"]
            if summary_obj.get("standup_summary"):
                section.append(f"\n**Standup Summary:** {summary_obj['standup_summary']}")
            repo_outputs.append("\n".join(section))
        else:
            # raw passthrough
            repo_outputs.append(f"### 📁 {repo.name}\n{raw_log}")

    if not repo_outputs:
        return "No commits found in the selected period."

    final = []
    final.extend(repo_outputs)

    # NEW: cohesive team-level scrum paragraph
    team_para = generate_team_scrum_paragraph(
        repo_summaries=repo_summaries,
        since_date=since_date,
        to_date=to_date,
        mode=mode,
    )
    if team_para:
        final.append("\n### 🧠 Scrum Summary\n" + team_para)

    return "\n\n".join(final)


def get_all_commits_across_repos_structured(
    since_date: str,
    to_date: Optional[str] = None,
    root: str = "~/dev",
    summarize_with_llm: bool = True,
    mode: str = "today",
    selected_repos: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    root_path = Path(os.path.expanduser(root))
    repos = selected_repos if selected_repos is not None else find_git_repos(root_path)

    repo_summaries: List[Dict[str, Any]] = []
    for repo in repos:
        raw_log = get_commits_from_repo(repo, since_date, to_date=to_date)
        if not raw_log:
            continue

        if summarize_with_llm:
            summary_obj = summarize_repo_text_block(
                repo_name=repo.name,
                since_date=since_date,
                to_date=to_date,
                mode=mode,
                full_repo_block_text=raw_log,
            )
            summary_obj["path"] = str(repo)
            repo_summaries.append(summary_obj)
        else:
            # fallback minimal shape
            repo_summaries.append({
                "repo_name": repo.name,
                "path": str(repo),
                "bullets": [raw_log],
                "team_snippets": [],
                "standup_summary": "",
            })

    team_para = generate_team_scrum_paragraph(
        repo_summaries=repo_summaries,
        since_date=since_date,
        to_date=to_date,
        mode=mode,
    )
    return {"repos": repo_summaries, "team_summary": team_para}