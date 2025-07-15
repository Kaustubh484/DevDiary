import click
from journal.git_utils import get_today_git_summary
from journal.multi_repo_git_utils import get_all_today_commits_across_repos
from journal.summarize import summarize_git_log

@click.group()
def cli():
    pass

@cli.command()
@click.option('--all-projects', is_flag=True, help="Scan all Git projects under ~/dev")
@click.option('--root', default="~/dev", help="Root folder to scan for Git repos")
@click.option('--summarize', is_flag=True, help="Use LLM to summarize activity")
def summarize(all_projects, root, summarize):
    """Summarize today's Git activity with optional LLM summarization."""
    
    # Fetch Git activity
    if all_projects:
        summary = get_all_today_commits_across_repos(root)
    else:
        summary = get_today_git_summary()

    click.echo("=== Git Activity ===\n")

    # Optional LLM summarization
    if summarize:
        llm_output = summarize_git_log(summary)
        click.echo(llm_output)
    else:
        click.echo(summary)

if __name__ == "__main__":
    cli()
