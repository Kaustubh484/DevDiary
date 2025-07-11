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

def get_commits_from_repo(repo_path, since_date):
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_date} 00:00", "--pretty=format:%h %s", "--name-only"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"# 📁 {repo_path}:\n" + result.stdout.strip()
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

