# journal/git_utils.py
import subprocess
from datetime import datetime

def get_today_git_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    cmd = [
        "git", "log",
        f"--since={today} 00:00",
        "--pretty=format:%h %s",
        "--name-only",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        return f"Error running Git command:\n{result.stderr}"

    return result.stdout.strip()

