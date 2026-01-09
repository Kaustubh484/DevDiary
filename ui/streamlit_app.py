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

try:
    from journal.logging_config import setup_default_logging
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    # When run via some runners (like Streamlit) the package root
    # may not be on sys.path. Add the project root so absolute
    # imports like `journal.*` resolve correctly.
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

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
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern, dark-themed design
st.markdown("""
<style>
    /* Global dark theme */
    .main {
        background: linear-gradient(135deg, #1a1d29 0%, #0f1117 100%);
    }

    /* Modern commit bullets with hover effect */
    .commit-bullet {
        padding: 8px 12px;
        margin: 4px 0;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
        font-size: 0.9rem;
        line-height: 1.7;
        background: linear-gradient(135deg, #252837 0%, #1f2230 100%);
        border-radius: 6px;
        border-left: 3px solid #4f46e5;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        color: #e2e8f0;
    }
    .commit-bullet:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 16px rgba(79, 70, 229, 0.4);
        border-left-color: #6366f1;
    }
    .commit-bullet code {
        background: linear-gradient(135deg, #4338ca 0%, #3730a3 100%);
        color: #e0e7ff;
        padding: 4px 10px;
        border-radius: 5px;
        font-weight: 600;
        font-size: 0.85rem;
        box-shadow: 0 2px 6px rgba(67, 56, 202, 0.5);
    }

    /* Elevated stat cards with dark gradient */
    .stat-card {
        background: linear-gradient(135deg, #1e2230 0%, #181c28 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid rgba(79, 70, 229, 0.2);
        margin: 12px 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
    }
    .stat-card:hover {
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5), 0 3px 6px rgba(79, 70, 229, 0.3);
        transform: translateY(-2px);
    }

    /* Success indicator */
    .success-box {
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.15) 0%, rgba(4, 120, 87, 0.12) 100%);
        border-left: 4px solid #059669;
        padding: 16px 20px;
        border-radius: 8px;
        margin: 12px 0;
        font-weight: 500;
        box-shadow: 0 4px 8px rgba(5, 150, 105, 0.2);
        color: #a7f3d0;
    }

    /* Error indicator */
    .error-box {
        background: linear-gradient(135deg, rgba(220, 38, 38, 0.15) 0%, rgba(185, 28, 28, 0.12) 100%);
        border-left: 4px solid #dc2626;
        padding: 16px 20px;
        border-radius: 8px;
        margin: 12px 0;
        font-weight: 500;
        box-shadow: 0 4px 8px rgba(220, 38, 38, 0.2);
        color: #fca5a5;
    }

    /* Stylish headings */
    h1 {
        font-weight: 700;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #818cf8 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    h2 {
        font-weight: 600;
        letter-spacing: -0.02em;
        margin-top: 2rem;
        color: #e2e8f0;
        border-bottom: 2px solid #334155;
        padding-bottom: 8px;
    }

    h3 {
        font-weight: 600;
        letter-spacing: -0.01em;
        color: #cbd5e1;
    }

    /* Modern buttons with dark gradients */
    .stButton button {
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: none;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
        background: linear-gradient(135deg, #374151 0%, #1f2937 100%);
        color: #e2e8f0;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
        background: linear-gradient(135deg, #4b5563 0%, #374151 100%);
    }

    /* Primary button styling */
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #4338ca 0%, #3730a3 100%);
        box-shadow: 0 4px 12px rgba(67, 56, 202, 0.5);
        color: white;
    }
    .stButton button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        box-shadow: 0 8px 24px rgba(79, 70, 229, 0.6);
    }

    /* Enhanced expanders */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1.05rem;
        background: linear-gradient(90deg, #1e2230 0%, #252837 100%);
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #374151;
        transition: all 0.2s ease;
        color: #e2e8f0;
    }
    .streamlit-expanderHeader:hover {
        background: linear-gradient(90deg, #252837 0%, #2d3348 100%);
        border-color: #4f46e5;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1d29 0%, #13151f 100%);
        border-right: 1px solid #334155;
    }

    /* Info boxes with dark styling */
    .stAlert {
        border-radius: 8px;
        border: 1px solid #374151;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        background: #1e2230;
    }

    /* Modern input fields */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        border-radius: 8px;
        border: 1.5px solid #374151;
        background: #1e2230;
        color: #e2e8f0;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stSelectbox select:focus, .stNumberInput input:focus {
        border-color: #4f46e5;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
    }

    /* Progress bar styling */
    .stProgress > div > div {
        background: linear-gradient(90deg, #4338ca 0%, #6366f1 100%);
        border-radius: 10px;
    }

    /* Divider styling */
    hr {
        margin: 2rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, #334155 50%, transparent 100%);
    }

    /* Metrics styling */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2230 0%, #181c28 100%);
        padding: 16px;
        border-radius: 10px;
        border: 1px solid #374151;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    }

    /* Chart containers */
    .element-container:has(.stPlotlyChart) {
        background: #1e2230;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        border: 1px solid #374151;
    }

    /* Text colors */
    p, span, label {
        color: #cbd5e1;
    }

    /* Checkbox and radio styling */
    .stCheckbox, .stRadio {
        color: #e2e8f0;
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
    # Add a styled header container with dark theme
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1e1b4b 0%, #18153a 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
        border: 1px solid #312e81;
    ">
        <h1 style="
            color: #c7d2fe;
            margin: 0;
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #a5b4fc 0%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        ">DevDiary</h1>
        <p style="
            color: #a5b4fc;
            margin: 0.5rem 0 0 0;
            font-size: 1.1rem;
        ">Developer Journal Assistant</p>
        <p style="
            color: #cbd5e1;
            margin: 0.5rem 0 0 0;
            font-size: 0.95rem;
        ">Private-first developer journaling from your local Git activity. Summaries powered by Ollama LLM.</p>
    </div>
    """, unsafe_allow_html=True)

    # Settings button below header
    col1, col2, col3 = st.columns([5, 1, 5])
    with col2:
        if st.button("Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.show_settings


def render_settings_panel():
    """Render expandable settings panel."""
    if not st.session_state.show_settings:
        return

    with st.expander("Configuration Settings", expanded=True):
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

        if st.button("Save Settings"):
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
                st.success("Settings saved successfully!")
                logger.info("Configuration saved")
            except Exception as e:
                st.error(f"Failed to save settings: {e}")
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
        "Run Scan",
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
        st.sidebar.info("LLM summarization disabled in settings")
        return

    # Test connection
    status = st.session_state.summarizer.test_connection()

    if status["available"]:
        st.sidebar.markdown('<div class="success-box">LLM Available</div>', unsafe_allow_html=True)

        with st.sidebar.expander("Model Details"):
            st.write(f"**Endpoint:** {st.session_state.config.ollama.endpoint}")
            st.write(f"**Model:** {st.session_state.config.ollama.model}")
            st.write("**Available Models:**")
            for model in status["models"]:
                if "llama3" in model.lower():
                    st.write(f"  • {model} (configured)")
                else:
                    st.write(f"  • {model}")
    else:
        st.sidebar.markdown(
            f'<div class="error-box">LLM Unavailable<br/><small>{status["error"]}</small></div>',
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
    st.subheader("Overview")

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
    with st.expander(f"{repo.repo_name}", expanded=True):
        # Repository statistics with dark-themed cards
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
                padding: 16px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
                border: 1px solid #2563eb;
            ">
                <div style="color: #93c5fd; font-size: 0.85rem; margin-bottom: 4px; font-weight: 500;">Commits</div>
                <div style="color: #dbeafe; font-size: 1.8rem; font-weight: 700;">{repo.commit_count}</div>
            </div>
            """, unsafe_allow_html=True)

        with cols[1]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%);
                padding: 16px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
                border: 1px solid #7c3aed;
            ">
                <div style="color: #c4b5fd; font-size: 0.85rem; margin-bottom: 4px; font-weight: 500;">Files</div>
                <div style="color: #e9d5ff; font-size: 1.8rem; font-weight: 700;">{repo.total_files_changed}</div>
            </div>
            """, unsafe_allow_html=True)

        with cols[2]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
                padding: 16px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
                border: 1px solid #059669;
            ">
                <div style="color: #6ee7b7; font-size: 0.85rem; margin-bottom: 4px; font-weight: 500;">Insertions</div>
                <div style="color: #d1fae5; font-size: 1.8rem; font-weight: 700;">+{repo.total_insertions}</div>
            </div>
            """, unsafe_allow_html=True)

        with cols[3]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
                padding: 16px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
                border: 1px solid #dc2626;
            ">
                <div style="color: #fca5a5; font-size: 0.85rem; margin-bottom: 4px; font-weight: 500;">Deletions</div>
                <div style="color: #fee2e2; font-size: 1.8rem; font-weight: 700;">-{repo.total_deletions}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

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
        st.info("Configure your options in the sidebar, then click **Run Scan**.")
        return

    repos = scan_result.repositories

    if not repos:
        st.warning("No commits found in the selected period.")
        return

    # Show charts
    if show_stats and st.session_state.config.ui.show_charts:
        render_charts(scan_result)

    # Per-repository sections
    st.subheader("Repositories")

    for repo in repos:
        render_repository(repo)

    # Team summary
    if scan_result.team_summary:
        st.divider()
        st.subheader("Team Summary")
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

    if st.sidebar.button("Export", use_container_width=True):
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
                label=f"Download {export_format.upper()}",
                data=content.encode("utf-8"),
                file_name=filename,
                mime=mime_type,
                use_container_width=True,
            )

            st.sidebar.success(f"{export_format.upper()} export ready!")
            logger.info(f"Export generated: {filename}")

        except Exception as e:
            st.sidebar.error(f"Export failed: {e}")
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
        status_placeholder.info("Scanning repositories...")

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
            status_placeholder.info("Generating LLM summaries...")

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
            f"Scan complete! Found {scan_result.total_commits} commits "
            f"across {len(scan_result.get_repos_with_activity())} repositories."
        )

        logger.info("Scan workflow completed successfully")

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        progress_placeholder.empty()
        status_placeholder.error(f"Scan failed: {e}")

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
