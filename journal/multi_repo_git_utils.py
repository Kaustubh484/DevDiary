import os
import subprocess
from datetime import datetime
from pathlib import Path


def find_git_repos(root_path):
    git_repos = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        if '.git' in dirnames:
            git_repos.append(Path(dirpath))
            dirnames[:] = []  # stop recursing into that repo
    return git_repos


EXCLUDED_PATTERNS = [
    "venv/", ".venv/", "__pycache__",
    ".git/", "env/", "site-packages", "/bin/", "/lib/", "dist-info"
]


def should_exclude(line):
    normalized = Path(line.strip()).as_posix().lower()  # normalize and lowercase
    return any(pattern in normalized for pattern in EXCLUDED_PATTERNS)


def get_commits_from_repo(repo_path, since_date):
    since_date = datetime.now().strftime("%Y-%m-%d")
    try:
        # Add delimiters between commits
        result = subprocess.run(
            ["git", "log", f"--since={since_date} 00:00", "--pretty=format:===COMMIT===%n%h %s", "--name-only"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None

        blocks = result.stdout.strip().split("===COMMIT===")
        included_blocks = []

        for block in blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue

            commit_header = lines[0]
            file_lines = lines[1:]

            # Only keep files not matching the exclude list
            filtered_files = [
                f for f in file_lines
                if not should_exclude(f)
            ]

            if filtered_files:
                included_blocks.append(commit_header + "\n" + "\n".join(filtered_files))

        if included_blocks:
            return f"# 📁 {repo_path}:\n" + "\n\n".join(included_blocks)

    except Exception as e:
        return f"# 📁 {repo_path}:\nError: {e}"

    return None




def get_all_today_commits_across_repos(root="~/dev"):
    since = datetime.now().strftime("%Y-%m-%d")
    root_path = Path(os.path.expanduser(root))
    repos = find_git_repos(root_path)

    all_logs = []
    for repo in repos:
        log = get_commits_from_repo(repo, since)
        if log:
            all_logs.append(log)

    return "\n\n".join(all_logs) if all_logs else "No commits found today."

