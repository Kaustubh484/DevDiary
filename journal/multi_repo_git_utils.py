import os
import subprocess
from datetime import datetime
from pathlib import Path
from journal.summarize import summarize_chunk , summarize_git_log # Ollama-based
from datetime import datetime, timedelta
from typing import Optional
def get_today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_past_days_date(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def get_first_day_of_month() -> str:
    today = datetime.now()
    return today.replace(day=1).strftime("%Y-%m-%d")


# Patterns to exclude from file logs
EXCLUDED_PATTERNS = [
    "venv/", ".venv/", "__pycache__",
    ".git/", "env/", "site-packages", "/bin/", "/lib/", "dist-info"
]

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


def get_commits_from_repo(repo_path: Path, since_date: str) -> str:
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_date} 00:00", "--pretty=format:===COMMIT===%n%h %s", "--name-only"],
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
                included_blocks.append(commit_header + "\n" + "\n".join(filtered_files))

        if included_blocks:
            return "\n\n".join(included_blocks)

    except Exception as e:
        return f"[Error reading repo {repo_path}]: {e}"

    return None


def get_all_commits_across_repos(since_date: str, root="~/dev", summarize_with_llm=True, mode: str = "today") -> str:
    # Expand ~ and convert to Path
    root_path = Path(os.path.expanduser(root))
    repos = find_git_repos(root_path)

    all_summaries = []

    for repo in repos:
        raw_log = get_commits_from_repo(repo, since_date)
        if not raw_log:
            continue

        if summarize_with_llm:
            repo_name = repo.name
            summary = summarize_git_log(raw_log, repo_name=repo_name, date=since_date, mode=mode)
            all_summaries.append(f"### 📁 {repo_name}\n{summary}")
        else:
            all_summaries.append(f"# 📁 {repo}\n{raw_log}")

    return "\n\n".join(all_summaries) if all_summaries else "No commits found today."
