import click
from journal.git_utils import get_today_git_summary
from journal.multi_repo_git_utils import get_all_today_commits_across_repos

@click.group()
def cli():
    pass

@cli.command()
@click.option('--all-projects', is_flag=True, help="Scan all Git projects under ~/dev")
@click.option('--root', default="~/dev", help="Root folder to scan for Git repos")
def summarize(all_projects, root):
    """Summarize today's Git activity."""
    if all_projects:
        summary = get_all_today_commits_across_repos(root)
    else:
        summary = get_today_git_summary()

    click.echo("=== Git Activity ===")
    click.echo(summary)

if __name__ == "__main__":
    cli()

