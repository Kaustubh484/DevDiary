import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QCheckBox, QComboBox, QFileDialog, QLineEdit
)
import re

from journal.date_utils import resolve_since_date

from journal.git_utils import get_today_git_summary
from journal.multi_repo_git_utils import get_all_commits_across_repos,get_today_date, get_past_days_date, get_first_day_of_month
from journal.summarize import summarize_git_log

def markdown_to_html(text: str) -> str:
    # Convert **bold** to <b>bold</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Convert `code` to <code>code</code>
    text = re.sub(r'`([^`]*)`', r'<code>\1</code>', text)
    # Convert ### Header to <h3>Header</h3>
    text = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', text)
    # Add line breaks
    text = text.replace('\n', '<br>')
    return text

class JournalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Developer Journal Assistant")
        self.resize(800, 600)

        layout = QVBoxLayout()

        # Options
        self.all_projects_checkbox = QCheckBox("Scan all projects (default: ~/dev)")
        layout.addWidget(self.all_projects_checkbox)

        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["today", "weekly", "monthly"])
        layout.addWidget(QLabel("Select Mode:"))
        layout.addWidget(self.mode_dropdown)

        self.llm_checkbox = QCheckBox("Summarize with LLM")
        layout.addWidget(self.llm_checkbox)

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

        self.run_button = QPushButton("Run Summary")
        self.run_button.clicked.connect(self.run_summary)
        layout.addWidget(self.run_button)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.setLayout(layout)

    def browse_output_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output File")
        if path:
            self.output_path.setText(path)

    def run_summary(self):
        all_projects = self.all_projects_checkbox.isChecked()
        mode = self.mode_dropdown.currentText()
        summarize = self.llm_checkbox.isChecked()
        save_output = self.save_checkbox.isChecked()
        output_path = self.output_path.text().strip()
        root = self.root_input.text().strip() or "~/dev"

        since_date = resolve_since_date(mode)

        if all_projects:
            summary = get_all_commits_across_repos(
                since_date=since_date,
                root=root,
                summarize_with_llm=summarize,
                mode=mode
            )
            display_text =  summary
        else:
            raw_log = get_today_git_summary()  # You can enhance to support date range
            if summarize:
                display_text = summarize_git_log(raw_log)
            else:
                display_text = raw_log

        html_output = markdown_to_html(display_text)
        self.result_text.setHtml(html_output)


        if save_output and output_path:
            Path(output_path).write_text(display_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = JournalApp()
    win.show()
    sys.exit(app.exec_())
