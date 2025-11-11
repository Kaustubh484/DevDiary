"""
DevDiary Streamlit Application
===============================

Modern web UI for DevDiary using the service layer architecture.
Provides interactive repository scanning, LLM summarization, and export functionality.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st

from journal.logging_config import setup_default_logging
from core import (
    RepositoryScanner,
    LLMSummarizer,
    Exporter,
    ScanMode,
    ExportOptions,
    ScanProgress,
    ScanResult,
    get_config,
)

# Initialize logging
setup_default_logging(verbose=False)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="DevDiary",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .commit-bullet {
        padding: 4px 0;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
    }
    .commit-bullet code {
        background-color: rgba(175, 184, 193, 0.2);
        padding: 2px 6px;
        border-radius: 3px;
    }
    .stat-card {
        background-color: rgba(0, 0, 0, 0.05);
        padding: 16px;
        border-radius: 8px;
        margin: 8px 0;
    }
    .success-box {
        background-color: rgba(34, 197, 94, 0.1);
        border-left: 4px solid rgb(34, 197, 94);
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    }
    .error-box {
        background-color: rgba(239, 68, 68, 0.1);
        border-left: 4px solid rgb(239, 68, 68);
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state with default values."""
    if "initialized" not in st.session_state:
        logger.info("Initializing session state")

        # Get configuration
        st.session_state.config = get_config()

        # Initialize services
        st.session_state.scanner = RepositoryScanner(st.session_state.config)
        st.session_state.summarizer = LLMSummarizer(st.session_state.config)
        st.session_state.exporter = Exporter(st.session_state.config)

        # Application state
        st.session_state.last_scan = None
        st.session_state.scanning = False
        st.session_state.show_settings = False
        st.session_state.progress_text = ""
        st.session_state.progress_value = 0.0

        st.session_state.initialized = True
        logger.debug("Session state initialized")


def render_header():
    """Render the application header."""
    col1, col2 = st.columns([6, 1])

    with col1:
        st.title("📝 DevDiary — Developer Journal Assistant")
        st.caption(
            "Private-first developer journaling from your local Git activity. "
            "Summaries powered by Ollama LLM."
        )

    with col2:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.show_settings


def render_settings_panel():
    """Render expandable settings panel."""
    if not st.session_state.show_settings:
        return

    with st.expander("⚙️ Configuration Settings", expanded=True):
        st.subheader("Scanning Settings")

        col1, col2 = st.columns(2)

        with col1:
            new_root = st.text_input(
                "Root Path",
                value=st.session_state.config.scanning.root_path,
                help="Root directory to scan for Git repositories",
            )

            max_repos = st.number_input(
                "Max Repositories",
                value=st.session_state.config.scanning.max_repos or 0,
                min_value=0,
                help="Maximum number of repositories to scan (0 = unlimited)",
            )

        with col2:
            include_hidden = st.checkbox(
                "Include Hidden Directories",
                value=st.session_state.config.scanning.include_hidden,
            )

        st.divider()
        st.subheader("LLM Settings")

        col1, col2 = st.columns(2)

        with col1:
            ollama_enabled = st.checkbox(
                "Enable LLM Summarization",
                value=st.session_state.config.ollama.enabled,
            )

            ollama_model = st.text_input(
                "Model",
                value=st.session_state.config.ollama.model,
                help="Ollama model name (e.g., llama3)",
            )

        with col2:
            ollama_endpoint = st.text_input(
                "Ollama Endpoint",
                value=st.session_state.config.ollama.endpoint,
                help="Ollama server URL",
            )

        if st.button("💾 Save Settings"):
            # Update configuration
            st.session_state.config.scanning.root_path = new_root
            st.session_state.config.scanning.max_repos = max_repos if max_repos > 0 else None
            st.session_state.config.scanning.include_hidden = include_hidden
            st.session_state.config.ollama.enabled = ollama_enabled
            st.session_state.config.ollama.model = ollama_model
            st.session_state.config.ollama.endpoint = ollama_endpoint

            # Save to file
            try:
                st.session_state.config.save()
                st.success("✅ Settings saved successfully!")
                logger.info("Configuration saved")
            except Exception as e:
                st.error(f"❌ Failed to save settings: {e}")
                logger.error(f"Failed to save config: {e}")


def render_controls() -> Optional[Dict[str, Any]]:
    """Render sidebar controls and return scan parameters if 'Run' clicked."""
    st.sidebar.header("Controls")

    # Mode selection
    mode_str = st.sidebar.selectbox(
        "Mode",
        options=["today", "weekly", "monthly", "custom"],
        index=1,  # Default to weekly
    )

    # Custom date range (shown only for custom mode)
    if mode_str == "custom":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            since_date = st.date_input("From", value=date.today())
        with col2:
            to_date = st.date_input("To", value=date.today())

        since_iso = since_date.isoformat()
        to_iso = to_date.isoformat()
    else:
        since_iso = None
        to_iso = None

    st.sidebar.divider()

    # Scan options
    all_projects = st.sidebar.checkbox("Scan all projects", value=True)
    summarize_llm = st.sidebar.checkbox(
        "Summarize with LLM",
        value=st.session_state.config.ollama.enabled,
    )

    st.sidebar.divider()

    # Run button
    run_clicked = st.sidebar.button(
        "🚀 Run Scan",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.scanning,
    )

    if run_clicked:
        logger.info(f"Scan initiated: mode={mode_str}, summarize={summarize_llm}")
        return {
            "mode": ScanMode(mode_str),
            "since_date": since_iso,
            "to_date": to_iso,
            "all_projects": all_projects,
            "summarize": summarize_llm,
        }

    return None


def render_llm_status():
    """Render LLM connection status in sidebar."""
    st.sidebar.header("LLM Status")

    if not st.session_state.config.ollama.enabled:
        st.sidebar.info("ℹ️ LLM summarization disabled in settings")
        return

    # Test connection
    status = st.session_state.summarizer.test_connection()

    if status["available"]:
        st.sidebar.markdown('<div class="success-box">✅ LLM Available</div>', unsafe_allow_html=True)

        with st.sidebar.expander("Model Details"):
            st.write(f"**Endpoint:** {st.session_state.config.ollama.endpoint}")
            st.write(f"**Model:** {st.session_state.config.ollama.model}")
            st.write("**Available Models:**")
            for model in status["models"]:
                if "llama3" in model.lower():
                    st.write(f"  ✓ {model} (configured)")
                else:
                    st.write(f"  - {model}")
    else:
        st.sidebar.markdown(
            f'<div class="error-box">❌ LLM Unavailable<br/><small>{status["error"]}</small></div>',
            unsafe_allow_html=True,
        )

        with st.sidebar.expander("Troubleshooting"):
            st.markdown("""
            **To fix:**
            1. Install Ollama from https://ollama.com/
            2. Start Ollama service
            3. Pull model: `ollama pull llama3`
            """)


def render_progress_section():
    """Render progress bar and status during scanning."""
    if st.session_state.scanning:
        st.info(st.session_state.progress_text)
        st.progress(st.session_state.progress_value / 100.0)


def render_charts(scan_result: ScanResult):
    """Render visualization charts for scan results."""
    st.subheader("📊 Overview")

    col1, col2 = st.columns(2)

    # Commits per repository chart
    with col1:
        st.markdown("**Commits per Repository**")

        repo_data = []
        for repo in scan_result.repositories:
            repo_data.append({
                "repository": repo.repo_name,
                "commits": repo.commit_count,
            })

        if repo_data:
            df_repos = pd.DataFrame(repo_data).sort_values("commits", ascending=False)
            st.bar_chart(df_repos.set_index("repository"))
        else:
            st.caption("No data to display")

    # Work type distribution chart
    with col2:
        st.markdown("**Work Type Distribution**")

        work_types = scan_result.work_type_distribution
        if work_types:
            wt_data = [
                {"work_type": wt.value, "count": count}
                for wt, count in work_types.items()
            ]
            df_wt = pd.DataFrame(wt_data).sort_values("count", ascending=False)
            st.bar_chart(df_wt.set_index("work_type"))
        else:
            st.caption("No work type data available")

    st.divider()


def render_repository(repo):
    """Render a single repository's summary."""
    with st.expander(f"📁 {repo.repo_name}", expanded=True):
        # Repository statistics
        st.markdown(
            f"**{repo.commit_count} commits** | "
            f"**{repo.total_files_changed} files** | "
            f"**+{repo.total_insertions}** / **-{repo.total_deletions}**"
        )

        st.divider()

        # Commit bullets
        if repo.bullets:
            st.markdown("**Commits:**")
            for bullet in repo.bullets:
                st.markdown(f'<div class="commit-bullet">{bullet}</div>', unsafe_allow_html=True)

        # Standup summary
        if repo.standup_summary:
            st.divider()
            st.markdown("**Standup Summary:**")
            st.markdown(repo.standup_summary)


def render_results(scan_result: Optional[ScanResult], show_stats: bool = True):
    """Render scan results."""
    if scan_result is None:
        st.info("👈 Configure your options in the sidebar, then click **Run Scan**.")
        return

    repos = scan_result.repositories

    if not repos:
        st.warning("⚠️ No commits found in the selected period.")
        return

    # Show charts
    if show_stats and st.session_state.config.ui.show_charts:
        render_charts(scan_result)

    # Per-repository sections
    st.subheader("📂 Repositories")

    for repo in repos:
        render_repository(repo)

    # Team summary
    if scan_result.team_summary:
        st.divider()
        st.subheader("🧠 Team Summary")
        st.markdown(scan_result.team_summary)


def render_export_section(scan_result: Optional[ScanResult]):
    """Render export options in sidebar."""
    if scan_result is None:
        return

    st.sidebar.divider()
    st.sidebar.header("Export")

    export_format = st.sidebar.selectbox(
        "Format",
        options=["markdown", "html", "json"],
        index=0,
    )

    include_stats = st.sidebar.checkbox("Include Statistics", value=True)
    include_diffs = st.sidebar.checkbox("Include Diff Details", value=False)

    if st.sidebar.button("📥 Export", use_container_width=True):
        try:
            # Create export options
            options = ExportOptions(
                format=export_format,
                include_bullets=True,
                include_standup=True,
                include_team_summary=True,
                include_stats=include_stats,
                include_diffs=include_diffs,
            )

            # Generate export
            content = st.session_state.exporter.export(scan_result, options)

            # Determine filename and MIME type
            filename = st.session_state.exporter.generate_filename(scan_result, options)

            mime_types = {
                "markdown": "text/markdown",
                "html": "text/html",
                "json": "application/json",
            }
            mime_type = mime_types.get(export_format, "text/plain")

            # Provide download button
            st.sidebar.download_button(
                label=f"⬇️ Download {export_format.upper()}",
                data=content.encode("utf-8"),
                file_name=filename,
                mime=mime_type,
                use_container_width=True,
            )

            st.sidebar.success(f"✅ {export_format.upper()} export ready!")
            logger.info(f"Export generated: {filename}")

        except Exception as e:
            st.sidebar.error(f"❌ Export failed: {e}")
            logger.error(f"Export error: {e}", exc_info=True)


def run_scan(params: Dict[str, Any]):
    """Execute repository scan with progress tracking."""
    st.session_state.scanning = True
    st.session_state.progress_value = 0.0
    st.session_state.progress_text = "Initializing scan..."

    # Create progress placeholder
    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    def update_progress(progress: ScanProgress):
        """Update progress UI."""
        st.session_state.progress_value = progress.percentage
        st.session_state.progress_text = progress.message

        # Update UI
        with progress_placeholder:
            st.progress(progress.percentage / 100.0)
        with status_placeholder:
            st.info(f"[{progress.phase}] {progress.message}")

    try:
        logger.info("Starting repository scan")
        status_placeholder.info("🔍 Scanning repositories...")

        # Scan repositories
        scan_result = st.session_state.scanner.scan_all(
            mode=params["mode"],
            since_date=params["since_date"],
            to_date=params["to_date"],
            selected_repos=None,  # Use all repos for now
            progress_callback=update_progress,
        )

        logger.info(f"Scan complete: {len(scan_result.repositories)} repositories")

        # Summarize if enabled
        if params["summarize"] and st.session_state.summarizer.is_available():
            status_placeholder.info("🧠 Generating LLM summaries...")

            scan_result = st.session_state.summarizer.summarize_scan_result(
                scan_result,
                progress_callback=update_progress,
            )

            logger.info("Summarization complete")

        # Store results
        st.session_state.last_scan = scan_result

        # Clear progress
        progress_placeholder.empty()
        status_placeholder.success(
            f"✅ Scan complete! Found {scan_result.total_commits} commits "
            f"across {len(scan_result.get_repos_with_activity())} repositories."
        )

        logger.info("Scan workflow completed successfully")

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        progress_placeholder.empty()
        status_placeholder.error(f"❌ Scan failed: {e}")

        with status_placeholder.expander("Error Details"):
            st.exception(e)

    finally:
        st.session_state.scanning = False


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()

    # Render header
    render_header()

    # Render settings panel
    render_settings_panel()

    # Render sidebar controls
    params = render_controls()

    # Render LLM status
    render_llm_status()

    # Handle scan request
    if params:
        run_scan(params)
        st.rerun()

    # Render progress
    render_progress_section()

    # Render results
    render_results(
        st.session_state.last_scan,
        show_stats=st.session_state.config.ui.show_charts,
    )

    # Render export options
    render_export_section(st.session_state.last_scan)


if __name__ == "__main__":
    main()
