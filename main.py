import click
from journal.git_utils import get_today_git_summary
from journal.multi_repo_git_utils import get_all_commits_across_repos,get_today_date, get_past_days_date, get_first_day_of_month
from journal.summarize import summarize_git_log
  # You should implement these in utils

@click.group()
def cli():
    pass

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

@cli.command()
@click.option('--all-projects', is_flag=True, help="Scan all Git projects under ~/dev")
@click.option('--root', default="~/dev", help="Root folder to scan for Git repos")
@click.option('--mode', default="today", help="Mode of operation: today, weekly, monthly, or custom:YYYY-MM-DD")
@click.option('--summarize', is_flag=True, help="Use LLM to summarize activity")
def summarize(all_projects, root, mode, summarize):
    """Summarize Git activity with optional LLM summarization."""
    since_date = resolve_since_date(mode)

    if all_projects:
        summary = get_all_commits_across_repos(since_date=since_date, root=root, summarize_with_llm=summarize,mode=mode)
        click.echo("=== Git Activity Across Projects ===\n")
        click.echo(summary)
    else:
        raw_log = get_today_git_summary()  # You can change this to support since_date if needed
        click.echo("=== Git Activity (Current Repo) ===\n")
        if summarize:
            click.echo(summarize_git_log(raw_log))
        else:
            click.echo(raw_log)

if __name__ == "__main__":
    cli()
