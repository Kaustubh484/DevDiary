import os
from pathlib import Path
from datetime import date
from typing import List, Optional, Dict, Any

import streamlit as st

# Optional charts
import pandas as pd

from journal.multi_repo_git_utils import (
    find_git_repos,
    get_all_commits_across_repos_structured,
)
from journal.date_utils import resolve_since_date


# ---------------------------
# Page setup
# ---------------------------
st.set_page_config(page_title="DevDiary", layout="wide")
st.title("📝 DevDiary — Developer Journal Assistant")
st.caption("Private-first developer journaling from your local Git activity. Summaries powered by an open LLM via Ollama.")

# Keep a little state
if "last_data" not in st.session_state:
    st.session_state.last_data = None


# ---------------------------
# Sidebar controls
# ---------------------------
st.sidebar.header("Controls")

root_default = os.path.expanduser("~/dev")
root = st.sidebar.text_input("Root folder", root_default)

mode = st.sidebar.selectbox("Mode", ["today", "weekly", "monthly", "custom"])

if mode == "custom":
    col1, col2 = st.sidebar.columns(2)
    since_date = col1.date_input("From", value=date.today())
    to_date = col2.date_input("To", value=date.today())
    since_iso = since_date.isoformat()
    to_iso = to_date.isoformat()
else:
    since_iso = resolve_since_date(mode)
    to_iso = None

all_projects = st.sidebar.checkbox("Scan all projects", value=True)
summarize = st.sidebar.checkbox("Summarize with LLM", value=True)

# Repo picker if not scanning all
selected_repos: Optional[List[Path]] = None
if not all_projects:
    repos = find_git_repos(Path(os.path.expanduser(root)))
    repo_choices = [str(p) for p in repos]
    picked = st.sidebar.multiselect("Select repositories", repo_choices, default=repo_choices)
    selected_repos = [Path(p) for p in picked]

st.sidebar.markdown("---")
export_md = st.sidebar.checkbox("Prepare Markdown export")
run = st.sidebar.button("Run")


# ---------------------------
# Helpers
# ---------------------------
def _collect_export_lines(data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for r in data.get("repos", []):
        lines.append(f"### 📁 {r['repo_name']}")
        for b in r.get("bullets", []):
            lines.append(b)
        if r.get("standup_summary"):
            lines.append(f"\n**Standup Summary:** {r['standup_summary']}\n")
    team_para = data.get("team_summary") or ""
    if team_para:
        lines.append("### 🧠 Scrum Summary")
        lines.append(team_para)
    return lines


def _repos_table(data: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for r in data.get("repos", []):
        n_commits = len(r.get("bullets") or [])
        rows.append({"repo": r["repo_name"], "commits": n_commits})
    return pd.DataFrame(rows).sort_values("commits", ascending=False)


def _worktype_table(data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    # If your summarize pipeline exposes work types, you can attach them in the structured output
    # as r["work_types"] = ["feature","refactor",...]. If absent, we skip.
    buckets = {}
    has_any = False
    for r in data.get("repos", []):
        wtypes = r.get("work_types")  # Optional extension from your summarize.py
        if not wtypes:
            continue
        has_any = True
        for w in wtypes:
            buckets[w] = buckets.get(w, 0) + 1
    if not has_any:
        return None
    df = pd.DataFrame([{"work_type": k, "count": v} for k, v in buckets.items()])
    return df.sort_values("count", ascending=False)


# ---------------------------
# Main action
# ---------------------------
if run:
    with st.spinner("Scanning repositories and summarizing…"):
        data = get_all_commits_across_repos_structured(
            since_date=since_iso,
            to_date=to_iso,
            root=root,
            summarize_with_llm=summarize,
            mode=mode,
            selected_repos=selected_repos,
        )
        st.session_state.last_data = data

# ---------------------------
# Render results
# ---------------------------
data = st.session_state.last_data
if not data:
    st.info("Set your options in the sidebar, then click **Run**.")
else:
    repos = data.get("repos", [])
    if not repos:
        st.warning("No commits found in the selected period.")
    else:
        # Top-level analytics
        st.subheader("📊 Overview")
        colA, colB = st.columns([1, 1])

        with colA:
            df_repos = _repos_table(data)
            st.markdown("**Commits per repository**")
            st.bar_chart(df_repos.set_index("repo"))

        with colB:
            df_wt = _worktype_table(data)
            if df_wt is not None and not df_wt.empty:
                st.markdown("**Work types (if available)**")
                st.bar_chart(df_wt.set_index("work_type"))
            else:
                st.caption("Work type chart will appear when your summarizer returns `work_types` per repo.")

        st.markdown("---")

        # Per-repo sections
        for r in repos:
            with st.expander(f"📁 {r['repo_name']}", expanded=True):
                bullets = r.get("bullets") or []
                if bullets:
                    st.markdown("**Commits**")
                    # Bullets are already Markdown-like, render natively
                    st.markdown("\n".join(bullets))
                if r.get("standup_summary"):
                    st.markdown("**Standup Summary**")
                    st.write(r["standup_summary"])

        # Team-level scrum summary
        team_para = data.get("team_summary", "") or ""
        if team_para:
            st.subheader("🧠 Scrum Summary")
            st.write(team_para)

        # Export
        if export_md:
            export_lines = _collect_export_lines(data)
            if export_lines:
                md = "\n\n".join(export_lines).encode("utf-8")
                st.download_button("⬇️ Download Markdown", data=md, file_name="devdiary_summary.md", mime="text/markdown")
