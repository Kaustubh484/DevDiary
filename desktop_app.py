import sys
import os
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QCheckBox, QComboBox, QFileDialog, QLineEdit, QDateEdit,
    QListWidget, QListWidgetItem
)

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QCheckBox, QComboBox, QFileDialog, QLineEdit, QScrollArea, QFrame
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import QDateEdit, QListWidget, QListWidgetItem, QToolButton, QSizePolicy

from PyQt5.QtCore import QDate

from journal.date_utils import resolve_since_date

from journal.multi_repo_git_utils import get_all_commits_across_repos, find_git_repos,get_all_commits_across_repos_structured



def markdown_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]*)`', r'<code>\1</code>', text)
    text = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', text)
    text = text.replace('\n', '<br>')
    return text
class CollapsibleSection(QWidget):
    def __init__(self, title: str, content_widget: QWidget, parent=None):
        super().__init__(parent)
        self.toggle = QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow)
        self.toggle.clicked.connect(self._on_toggled)

        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setWidget(content_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content_area)

    def _on_toggled(self, checked: bool):
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content_area.setVisible(checked)

DARK_QSS = """
QWidget { background: #11151a; color: #e6edf3; }
QLineEdit, QTextEdit, QScrollArea { background: #0b0f14; color: #e6edf3; border: 1px solid #22303a; }
QToolButton { background: #0b0f14; border: 1px solid #22303a; padding: 6px; }
QPushButton { background: #1b2836; color: #e6edf3; border: 1px solid #22303a; padding: 6px 10px; }
QComboBox, QDateEdit { background: #0b0f14; border: 1px solid #22303a; }
QCheckBox { spacing: 6px; }
"""

LIGHT_QSS = """
QWidget { background: #ffffff; color: #111; }
QLineEdit, QTextEdit, QScrollArea { background: #ffffff; color: #111; border: 1px solid #ccc; }
QToolButton { background: #f7f7f7; border: 1px solid #ccc; padding: 6px; }
QPushButton { background: #f0f0f0; color: #111; border: 1px solid #ccc; padding: 6px 10px; }
QComboBox, QDateEdit { background: #ffffff; border: 1px solid #ccc; }
"""

def repo_emoji(repo_path: Path) -> str:
    # very lightweight heuristics
    try:
        files = {p.name for p in repo_path.iterdir()}
    except Exception:
        files = set()

    # indicators
    if "pyproject.toml" in files or any(str(repo_path).endswith(ext) for ext in (".py",)):
        return "🐍"
    if "package.json" in files or "pnpm-lock.yaml" in files or "yarn.lock" in files:
        return "📦"
    if "tests" in files or "test" in files:
        return "🧪"
    return "📁"

class JournalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Developer Journal Assistant")
        self.resize(800, 600)

        layout = QVBoxLayout()

        self.all_projects_checkbox = QCheckBox("Scan all projects (default: ~/dev)")
        layout.addWidget(self.all_projects_checkbox)
        self.dark_mode_checkbox = QCheckBox("Dark mode")
        self.dark_mode_checkbox.stateChanged.connect(self.apply_theme)
        layout.addWidget(self.dark_mode_checkbox)

        layout.addWidget(QLabel("Select repositories to include:"))
        self.repo_list = QListWidget()
        self.repo_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.repo_list)

        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["today", "weekly", "monthly", "custom"])
        layout.addWidget(QLabel("Select Mode:"))
        layout.addWidget(self.mode_dropdown)
        self.mode_dropdown.currentTextChanged.connect(self.toggle_date_range_visibility)

        self.date_range_container = QWidget()
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("From Date:"))
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(self.date_from_edit)

        date_layout.addWidget(QLabel("To Date:"))
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_to_edit)

        self.date_range_container.setLayout(date_layout)
        layout.addWidget(self.date_range_container)
        self.date_range_container.hide()

        

        self.save_checkbox = QCheckBox("Save output to file")
        layout.addWidget(self.save_checkbox)

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Optional: Path to save summary output")
        layout.addWidget(self.output_path)

        self.select_output_button = QPushButton("Browse Output File")
        self.select_output_button.clicked.connect(self.browse_output_file)
        layout.addWidget(self.select_output_button)

        self.root_input = QLineEdit(os.path.expanduser("~/dev"))
        layout.addWidget(QLabel("Root folder to scan:"))
        layout.addWidget(self.root_input)
        self.root_input.editingFinished.connect(self.populate_repo_list)

        self.refresh_button = QPushButton("Refresh Repo List")
        self.refresh_button.clicked.connect(self.populate_repo_list)
        layout.addWidget(self.refresh_button)

        self.run_button = QPushButton("Run Summary")
        self.run_button.clicked.connect(self.run_summary)
        layout.addWidget(self.run_button)

                # Results container (for collapsible sections)
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_host = QWidget()
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(12)
        self.results_scroll.setWidget(self.results_host)
        layout.addWidget(self.results_scroll)

        # Optional raw output fallback (hide by default)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.hide()
        layout.addWidget(self.result_text)

      
        self.setLayout(layout)
        self.apply_theme()
        self.populate_repo_list()
        

    def apply_theme(self):
        if self.dark_mode_checkbox.isChecked():
            self.setStyleSheet(DARK_QSS)
        else:
            self.setStyleSheet(LIGHT_QSS)

    def browse_output_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output File")
        if path:
            self.output_path.setText(path)

    def toggle_date_range_visibility(self, text):
        self.date_range_container.setVisible(text.lower() == "custom")

    def populate_repo_list(self):
        root = self.root_input.text().strip() or "~/dev"
        repos = find_git_repos(Path(os.path.expanduser(root)))

        self.repo_list.clear()
        for repo_path in repos:
            item = QListWidgetItem(str(repo_path))
            item.setCheckState(2)
            self.repo_list.addItem(item)
            
    def clear_results(self):
        # remove existing collapsible sections
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def run_summary(self):
    # inputs
        all_projects = self.all_projects_checkbox.isChecked()
        mode = self.mode_dropdown.currentText()
        save_output = self.save_checkbox.isChecked()
        output_path = self.output_path.text().strip()
        root = self.root_input.text().strip() or "~/dev"

        # date window
        if mode.lower().startswith("custom"):
            since_date = self.date_from_edit.date().toPyDate().isoformat()
            to_date = self.date_to_edit.date().toPyDate().isoformat()
        else:
            since_date = resolve_since_date(mode)
            to_date = None

        # which repos to include
        if all_projects:
            selected_repos = None  # include all repos under root
        else:
            selected_repos = [
                Path(self.repo_list.item(i).text())
                for i in range(self.repo_list.count())
                if self.repo_list.item(i).checkState() == 2  # Qt.Checked
            ]
            if not selected_repos:
                # nothing checked; show a friendly message
                self.clear_results()
                msg = QTextEdit()
                msg.setReadOnly(True)
                msg.setHtml("<i>No repositories selected. Check at least one repo or enable "
                            "<b>Scan all projects</b>.</i>")
                self.results_layout.addWidget(msg)
                return

        # get structured summaries (bullets + repo paragraph + team paragraph)
        from journal.multi_repo_git_utils import get_all_commits_across_repos_structured
        data = get_all_commits_across_repos_structured(
            since_date=since_date,
            to_date=to_date,
            root=root,
            summarize_with_llm=True,
            mode=mode,
            selected_repos=selected_repos
        )

        # render collapsible sections
        self.clear_results()
        export_lines = []  # build a markdown export alongside

        for r in data.get("repos", []):
            title = f"{repo_emoji(Path(r.get('path', '')))}  {r['repo_name']}"

            # content widget per repo
            content = QWidget()
            v = QVBoxLayout(content)

            # bullets
            bullets = r.get("bullets") or []
            if bullets:
                v.addWidget(QLabel("<b>Commits</b>"))
                bullet_html = "<br>".join(
                    # lightweight conversion of backticks to <code>
                    re.sub(r'`([^`]*)`', r'<code>\\1</code>', b)
                    for b in bullets
                )
                bullets_view = QTextEdit()
                bullets_view.setReadOnly(True)
                bullets_view.setHtml(bullet_html)
                bullets_view.setMinimumHeight(min(240, 24 * len(bullets) + 30))
                v.addWidget(bullets_view)

            # repo standup paragraph
            if r.get("standup_summary"):
                v.addWidget(QLabel("<b>Standup Summary</b>"))
                para = QTextEdit()
                para.setReadOnly(True)
                # allow plain text from model; render as HTML safely
                para.setHtml(r["standup_summary"])
                v.addWidget(para)

            section = CollapsibleSection(title, content)
            self.results_layout.addWidget(section)

            # build export
            export_lines.append(f"### 📁 {r['repo_name']}")
            export_lines.extend(bullets)
            if r.get("standup_summary"):
                export_lines.append(f"\n**Standup Summary:** {r['standup_summary']}\n")

        # team scrum paragraph
        team_para = data.get("team_summary", "") or ""
        if team_para:
            team_widget = QTextEdit()
            team_widget.setReadOnly(True)
            team_widget.setHtml(team_para)
            team_section = CollapsibleSection("🧠 Scrum Summary", team_widget)
            self.results_layout.addWidget(team_section)
            export_lines.append("### 🧠 Scrum Summary")
            export_lines.append(team_para)

        # spacer so bottom has breathing room
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_layout.addWidget(spacer)

        # optional file export (Markdown)
        if save_output and output_path:
            try:
                Path(output_path).write_text("\n\n".join(export_lines), encoding="utf-8")
            except Exception as e:
                # show a soft error inline
                err = QTextEdit()
                err.setReadOnly(True)
                err.setHtml(f"<span style='color:#c33'>Failed to save output: {e}</span>")
                self.results_layout.addWidget(err)
    
if __name__ == '__main__':
        app = QApplication(sys.argv)
        win = JournalApp()
        win.show()
        sys.exit(app.exec_())