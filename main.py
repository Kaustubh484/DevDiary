import logging
import sys
import click
from pathlib import Path

from journal.git_utils import get_today_git_summary
from journal.multi_repo_git_utils import (
    get_all_commits_across_repos,
    get_today_date,
    get_past_days_date,
    get_first_day_of_month
)
from journal.summarize import summarize_git_log, get_ollama_client
from journal.logging_config import setup_default_logging

logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help="Enable verbose (DEBUG level) logging")
@click.option('--quiet', '-q', is_flag=True, help="Suppress all logging output")
@click.pass_context
def cli(ctx, verbose, quiet):
    """DevDiary - Automated Developer Activity Summarizer with LLM Integration."""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Set up logging based on flags
    if quiet:
        logging.disable(logging.CRITICAL)
        ctx.obj['logging_enabled'] = False
    else:
        setup_default_logging(verbose=verbose)
        ctx.obj['logging_enabled'] = True

    logger.debug(f"CLI initialized (verbose={verbose}, quiet={quiet})")

def resolve_since_date(mode: str) -> str:
    """Convert mode string to actual since_date."""
    mode = mode.lower()
    logger.debug(f"Resolving since_date for mode: {mode}")

    if mode == "today":
        return get_today_date()
    elif mode == "weekly":
        return get_past_days_date(7)
    elif mode == "monthly":
        return get_first_day_of_month()
    elif mode.startswith("custom:"):
        return mode.split("custom:")[1].strip()
    else:
        logger.error(f"Invalid mode specified: {mode}")
        raise click.BadParameter("Invalid --mode. Use today, weekly, monthly, or custom:YYYY-MM-DD")

@cli.command()
@click.option('--all-projects', is_flag=True, help="Scan all Git projects under ~/dev")
@click.option('--root', default="~/dev", help="Root folder to scan for Git repos")
@click.option('--mode', default="today", help="Mode of operation: today, weekly, monthly, or custom:YYYY-MM-DD")
@click.option('--summarize', is_flag=True, help="Use LLM to summarize activity")
@click.option('--output', type=click.Path(), help="Optional: Path to save summary output")
def summarize(all_projects, root, mode, summarize, output):
    """Summarize Git activity with optional LLM summarization."""
    logger.info(f"Starting summarize command (mode={mode}, all_projects={all_projects}, summarize={summarize})")

    try:
        since_date = resolve_since_date(mode)
        logger.info(f"Resolved since_date: {since_date}")

        if all_projects:
            logger.info(f"Scanning all projects under {root}")
            summary = get_all_commits_across_repos(
                since_date=since_date,
                root=root,
                summarize_with_llm=summarize,
                mode=mode
            )
            click.echo("=== Git Activity Across Projects ===\n")
            click.echo(summary)

            if output:
                logger.info(f"Saving summary to {output}")
                Path(output).write_text(summary)
                click.echo(f"\n✅ Summary saved to {output}")
        else:
            logger.info("Processing current repository only")
            raw_log = get_today_git_summary()
            click.echo("=== Git Activity (Current Repo) ===\n")
            if summarize:
                logger.info("Generating LLM summary for current repo")
                click.echo(summarize_git_log(raw_log))
            else:
                click.echo(raw_log)

            if output:
                logger.info(f"Saving summary to {output}")
                content = summarize_git_log(raw_log) if summarize else raw_log
                Path(output).write_text(content)
                click.echo(f"\n✅ Summary saved to {output}")

        logger.info("Summarize command completed successfully")

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        click.echo(f"\n❌ Error: {e}", err=True)
        click.echo("\nRun 'devdiary check' to verify your Ollama setup.", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in summarize command: {type(e).__name__}: {e}", exc_info=True)
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def check():
    """Check Ollama connection and verify llama3 model availability."""
    logger.info("Running Ollama connection check")
    click.echo("🔍 Checking Ollama setup...\n")

    try:
        # Test connection and get client
        client = get_ollama_client()
        click.echo("✅ Successfully connected to Ollama server")
        logger.info("Ollama connection successful")

        # List available models
        click.echo("\n📦 Available models:")
        try:
            models_response = client.list()

            # Extract model names
            available_models = []
            if hasattr(models_response, 'models'):
                available_models = [model.model for model in models_response.models]
            elif isinstance(models_response, dict) and 'models' in models_response:
                available_models = [m.get('name', m.get('model', '')) for m in models_response['models']]

            if not available_models:
                click.echo("   (No models found)")
                logger.warning("No models found in Ollama")
            else:
                # Highlight llama3 model
                for model in available_models:
                    if 'llama3' in model.lower():
                        click.echo(f"   ✓ {model} (required)")
                        logger.info(f"Found required model: {model}")
                    else:
                        click.echo(f"   - {model}")

                # Check if llama3 is present
                has_llama3 = any('llama3' in m.lower() for m in available_models)
                if has_llama3:
                    click.echo("\n✅ All requirements met! You're ready to use DevDiary.")
                    logger.info("Ollama check passed: llama3 model available")
                else:
                    click.echo("\n⚠️  Warning: llama3 model not found")
                    click.echo("   Run: ollama pull llama3")
                    logger.warning("llama3 model not found")
                    sys.exit(1)

        except Exception as e:
            logger.error(f"Error listing models: {e}", exc_info=True)
            click.echo(f"\n⚠️  Could not list models: {e}", err=True)
            sys.exit(1)

    except RuntimeError as e:
        logger.error(f"Ollama check failed: {e}")
        click.echo(f"\n❌ Ollama check failed:\n{e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during Ollama check: {type(e).__name__}: {e}", exc_info=True)
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
