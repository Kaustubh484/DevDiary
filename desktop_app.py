import sys
import os
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QCheckBox, QComboBox, QFileDialog, QLineEdit, QDateEdit,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import QDate

from journal.date_utils import resolve_since_date

from journal.multi_repo_git_utils import get_all_commits_across_repos, find_git_repos



def markdown_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]*)`', r'<code>\1</code>', text)
    text = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', text)
    text = text.replace('\n', '<br>')
    return text

class JournalApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Developer Journal Assistant")
        self.resize(800, 600)

        layout = QVBoxLayout()

        self.all_projects_checkbox = QCheckBox("Scan all projects (default: ~/dev)")
        layout.addWidget(self.all_projects_checkbox)

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

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Summary will appear here...")
        layout.addWidget(self.result_text)

        self.setLayout(layout)
        self.populate_repo_list()

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

    def run_summary(self):
        all_projects = self.all_projects_checkbox.isChecked()
        mode = self.mode_dropdown.currentText()
        
        save_output = self.save_checkbox.isChecked()
        output_path = self.output_path.text().strip()
        root = self.root_input.text().strip() or "~/dev"

        if mode.lower().startswith("custom"):
            since_date = self.date_from_edit.date().toPyDate().isoformat()
            to_date = self.date_to_edit.date().toPyDate().isoformat()
        else:
            since_date = resolve_since_date(mode)
            to_date = None
            
        selected_repos = [
                Path(self.repo_list.item(i).text())
                for i in range(self.repo_list.count())
                if self.repo_list.item(i).checkState() == 2
            ]
        if all_projects:
           summary = get_all_commits_across_repos(
                since_date=since_date,
                to_date=to_date,
                root=root,
                summarize_with_llm=True,
                mode=mode,
                selected_repos=None
            )
        else:
            summary = get_all_commits_across_repos(
                since_date=since_date,
                to_date=to_date,
                root=root,
                summarize_with_llm=True,
                mode=mode,
                selected_repos=selected_repos
            )
            

        html_output = markdown_to_html(summary)
        self.result_text.setHtml(html_output)

        if save_output and output_path:
            Path(output_path).write_text(summary, encoding='utf-8')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = JournalApp()
    win.show()
    sys.exit(app.exec_())
