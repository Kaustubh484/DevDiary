from journal.multi_repo_git_utils import get_all_commits_across_repos,get_today_date, get_past_days_date, get_first_day_of_month
import click

def resolve_since_date(mode: str) -> str:
    """Convert mode string to actual since_date."""
    mode = mode.lower()
    if mode == "today":
        return get_today_date()
    elif mode == "weekly":
        return get_past_days_date(7)
    elif mode == "monthly":
        return get_first_day_of_month()
    elif mode.startswith("custom:"):
        return mode.split("custom:")[1].strip()
    else:
        raise click.BadParameter("Invalid --mode. Use today, weekly, monthly, or custom:YYYY-MM-DD")