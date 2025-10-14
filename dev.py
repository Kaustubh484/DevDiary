import os
from pathlib import Path
from datetime import date
import dev as ft
import pandas as pd

from journal.multi_repo_git_utils import (
    find_git_repos,
    get_all_commits_across_repos_structured,
)
from journal.date_utils import resolve_since_date


def app(page: ft.Page):
    page.title = "DevDiary"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = "stretch"
    page.vertical_alignment = "start"

    # --- Controls ---
    root = ft.TextField(label="Root folder", value=os.path.expanduser("~/dev"), expand=True)
    mode = ft.Dropdown(
        label="Mode",
        value="weekly",
        options=[ft.dropdown.Option(v) for v in ["today", "weekly", "monthly", "custom"]],
        width=200,
    )
    since_dp = ft.DatePicker()
    to_dp = ft.DatePicker()
    pick_since_btn = ft.ElevatedButton("From…", on_click=lambda e: page.open(since_dp))
    pick_to_btn = ft.ElevatedButton("To…", on_click=lambda e: page.open(to_dp))
    since_dp.on_change = lambda e: since_label.update()
    to_dp.on_change = lambda e: to_label.update()
    since_label = ft.Text("Not set")
    to_label = ft.Text("Not set")

    all_projects = ft.Checkbox(label="Scan all projects", value=True)
    summarize = ft.Checkbox(label="Summarize with LLM", value=True)
    show_diff_stats = ft.Checkbox(label="Show diff stats per commit", value=True)

    repos_list = ft.Dropdown(label="Repos (when not scanning all)", options=[], expand=True, multi_select=True)

    def refresh_repos(_=None):
        repos = find_git_repos(Path(os.path.expanduser(root.value)))
        repos_list.options = [ft.dropdown.Option(str(p)) for p in repos]
        repos_list.update()

    refresh_btn = ft.OutlinedButton("Refresh Repos", on_click=refresh_repos)

    run_btn = ft.FilledButton("Run")
    export_btn = ft.OutlinedButton("Export Markdown", disabled=True)

    header_row = ft.Row(
        controls=[
            root,
            mode,
            pick_since_btn, since_label,
            pick_to_btn, to_label,
            all_projects, summarize, show_diff_stats,
            refresh_btn,
            run_btn, export_btn,
        ],
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
    )

    # auto-hide date pickers unless custom
    def on_mode_change(e):
        custom = (mode.value == "custom")
        pick_since_btn.visible = pick_to_btn.visible = since_label.visible = to_label.visible = custom
        page.update()
    mode.on_change = on_mode_change
    on_mode_change(None)

    # repos panel
    repos_panel = ft.Column([repos_list], visible=not all_projects.value)
    def toggle_all_projects(e):
        repos_panel.visible = not all_projects.value
        page.update()
    all_projects.on_change = toggle_all_projects

    # results area
    results = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # state
    last_data = {"repos": [], "team_summary": ""}

    # helpers
    def _collect_export_lines(data: dict) -> str:
        lines = []
        for r in data.get("repos", []):
            lines.append(f"### 📁 {r['repo_name']}")
            lines.extend(r.get("bullets") or [])
            if r.get("standup_summary"):
                lines.append(f"\n**Standup Summary:** {r['standup_summary']}\n")
        team = data.get("team_summary") or ""
        if team:
            lines.append("### 🧠 Scrum Summary")
            lines.append(team)
        return "\n\n".join(lines)

    def _since_iso():
        if mode.value == "custom":
            s = since_dp.value or date.today()
            return s.isoformat()
        return resolve_since_date(mode.value)

    def _to_iso():
        if mode.value == "custom":
            t = to_dp.value or date.today()
            return t.isoformat()
        return None

    def render_results(data: dict):
        results.controls.clear()

        # small overview
        rows = []
        for r in data.get("repos", []):
            rows.append({"repo": r["repo_name"], "commits": len(r.get("bullets") or [])})
        if rows:
            df = pd.DataFrame(rows).sort_values("commits", ascending=False)
            results.controls.append(ft.Text("📊 Commits per repository", weight=ft.FontWeight.BOLD))
            results.controls.append(ft.DataTable(
                columns=[ft.DataColumn(ft.Text("Repo")), ft.DataColumn(ft.Text("Commits"))],
                rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(a["repo"])), ft.DataCell(ft.Text(str(a["commits"])))]) for a in df.to_dict("records")]
            ))

        # per-repo expanders
        for r in data.get("repos", []):
            bullets = r.get("bullets") or []
            standup = r.get("standup_summary") or ""
            repo_path = Path(r.get("path", ""))

            commit_md = "\n".join(bullets) if bullets else "_No commits in range_"

            body = [
                ft.Text("Commits", weight=ft.FontWeight.BOLD),
                ft.Markdown(commit_md, selectable=True),
            ]
            if standup:
                body += [ft.Text("Standup Summary", weight=ft.FontWeight.BOLD),
                         ft.Markdown(standup)]

            # optional: diff stats table per commit
            if show_diff_stats.value and bullets:
                import re as _re
                from journal.multi_repo_git_utils import get_commit_stats
                stat_rows = []
                for b in bullets:
                    m = _re.search(r"`([0-9a-f]{6,40})`", b, _re.IGNORECASE)
                    if not m:
                        continue
                    chash = m.group(1)
                    stats = get_commit_stats(repo_path, chash)
                    if stats:
                        stat_rows.append(stats)
                if stat_rows:
                    results.controls.append(ft.Divider())
                    results.controls.append(ft.Text(f"Diff stats — {r['repo_name']}", weight=ft.FontWeight.BOLD))
                    results.controls.append(
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("Hash")),
                                ft.DataColumn(ft.Text("Date")),
                                ft.DataColumn(ft.Text("Author")),
                                ft.DataColumn(ft.Text("Files")),
                                ft.DataColumn(ft.Text("Ins")),
                                ft.DataColumn(ft.Text("Del")),
                            ],
                            rows=[
                                ft.DataRow(
                                    cells=[
                                        ft.DataCell(ft.Text(s["hash"][:10])),
                                        ft.DataCell(ft.Text(s["date"])),
                                        ft.DataCell(ft.Text(s["author"])),
                                        ft.DataCell(ft.Text(str(s["files_changed"]))),
                                        ft.DataCell(ft.Text(str(s["insertions"]))),
                                        ft.DataCell(ft.Text(str(s["deletions"]))),
                                    ]
                                )
                                for s in stat_rows
                            ],
                        )
                    )

            results.controls.append(ft.ExpansionTile(
                title=ft.Text(f"📁 {r['repo_name']}"),
                initially_expanded=True,
                controls=body
            ))

        # team summary
        team = data.get("team_summary") or ""
        if team:
            results.controls.append(ft.Divider())
            results.controls.append(ft.Text("🧠 Scrum Summary", weight=ft.FontWeight.BOLD))
            results.controls.append(ft.Markdown(team))

        page.update()

    def on_run(e):
        run_btn.disabled = True
        run_btn.text = "Running…"
        page.update()

        try:
            sel_repos = None
            if not all_projects.value:
                sel = repos_list.value or []
                sel_repos = [Path(x) for x in (sel if isinstance(sel, list) else [sel])]

            data = get_all_commits_across_repos_structured(
                since_date=_since_iso(),
                to_date=_to_iso(),
                root=root.value,
                summarize_with_llm=summarize.value,
                mode=mode.value,
                selected_repos=sel_repos,
            )
        finally:
            run_btn.disabled = False
            run_btn.text = "Run"
        nonlocal last_data
        last_data = data
        render_results(data)
        export_btn.disabled = False
        page.update()

    def on_export(e):
        if not last_data:
            return
        md = _collect_export_lines(last_data)
        # Save to a temp file and open folder, or just prompt download:
        # In Flet desktop, we can use FilePicker to save:
        def save_result(result: ft.FilePickerResultEvent):
            if result.path:
                Path(result.path).write_text(md, encoding="utf-8")
        fp = ft.FilePicker(on_result=save_result)
        page.overlay.append(fp)
        page.update()
        fp.save_file(file_name="devdiary_summary.md")

    run_btn.on_click = on_run
    export_btn.on_click = on_export

    page.overlay.extend([since_dp, to_dp])
    page.add(header_row, repos_panel, ft.Divider(), results)

    # initial
    refresh_repos()


if __name__ == "__main__":
    ft.app(target=app)
