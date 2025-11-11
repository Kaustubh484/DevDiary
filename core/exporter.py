"""
Multi-format export service for DevDiary.

Provides export functionality for scan results in various formats including
Markdown, HTML, JSON, and PDF with customizable options.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.types import ScanResult, ExportOptions
from core.config import DevDiaryConfig, get_config

logger = logging.getLogger(__name__)


class Exporter:
    """
    Service for exporting scan results in multiple formats.

    Supports Markdown, HTML, JSON, and PDF formats with customizable
    options for including/excluding various sections.
    """

    def __init__(self, config: Optional[DevDiaryConfig] = None):
        """
        Initialize the exporter.

        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config if config is not None else get_config()
        logger.info("Exporter initialized")
        logger.debug(f"Default export format: {self.config.export.default_format}")

    def export(
        self,
        scan_result: ScanResult,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """
        Export scan result to the specified format.

        Args:
            scan_result: ScanResult to export
            options: Export options. If None, uses defaults.

        Returns:
            Formatted string content

        Raises:
            ValueError: If format is not supported
        """
        if options is None:
            options = ExportOptions(format=self.config.export.default_format)

        logger.info(f"Exporting scan result to {options.format} format")

        format_lower = options.format.lower()

        if format_lower in ("markdown", "md"):
            return self.to_markdown(scan_result, options)
        elif format_lower in ("html", "htm"):
            return self.to_html(scan_result, options)
        elif format_lower == "json":
            return self.to_json(scan_result, options)
        elif format_lower == "pdf":
            return self.to_pdf(scan_result, options)
        else:
            raise ValueError(f"Unsupported export format: {options.format}")

    def to_markdown(self, scan_result: ScanResult, options: ExportOptions) -> str:
        """
        Export scan result as Markdown.

        Args:
            scan_result: ScanResult to export
            options: Export options

        Returns:
            Markdown-formatted string
        """
        logger.debug("Generating Markdown export")
        lines: list[str] = []

        # Header
        lines.append("# DevDiary Summary")
        lines.append("")
        lines.append(f"**Mode:** {scan_result.scan_mode.value}")
        lines.append(f"**Period:** {scan_result.since_date} to {scan_result.to_date or 'now'}")
        lines.append(f"**Generated:** {scan_result.scan_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Overall statistics
        if options.include_stats:
            lines.append("")
            lines.append("## Overview")
            lines.append("")
            lines.append(f"- **Total Repositories:** {scan_result.total_repos}")
            lines.append(f"- **Total Commits:** {scan_result.total_commits}")
            lines.append(f"- **Active Repositories:** {len(scan_result.get_repos_with_activity())}")

            # Work type distribution
            work_types = scan_result.work_type_distribution
            if work_types:
                lines.append("")
                lines.append("### Work Type Distribution")
                lines.append("")
                for work_type, count in sorted(work_types.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"- **{work_type.value.capitalize()}:** {count}")

        # Per-repository sections
        lines.append("")
        lines.append("## Repositories")
        lines.append("")

        for repo in scan_result.repositories:
            lines.append(f"### 📁 {repo.repo_name}")
            lines.append("")

            # Repository statistics
            if options.include_stats:
                lines.append(f"**Commits:** {repo.commit_count} | "
                           f"**Files:** {repo.total_files_changed} | "
                           f"**+{repo.total_insertions}** / **-{repo.total_deletions}**")
                lines.append("")

            # Commit bullets
            if options.include_bullets and repo.bullets:
                lines.append("**Commits:**")
                lines.append("")
                for bullet in repo.bullets:
                    lines.append(bullet)
                lines.append("")

            # Standup summary
            if options.include_standup and repo.standup_summary:
                lines.append("**Standup Summary:**")
                lines.append("")
                lines.append(repo.standup_summary)
                lines.append("")

            # Diff details
            if options.include_diffs and repo.commits:
                lines.append("<details>")
                lines.append("<summary>Commit Details</summary>")
                lines.append("")
                for commit in repo.commits:
                    lines.append(f"- `{commit.commit_hash}`: {commit.message}")
                    if commit.files_changed > 0:
                        lines.append(f"  - Files: {commit.files_changed}, "
                                   f"+{commit.insertions}, -{commit.deletions}")
                lines.append("")
                lines.append("</details>")
                lines.append("")

        # Team summary
        if options.include_team_summary and scan_result.team_summary:
            lines.append("## 🧠 Team Summary")
            lines.append("")
            lines.append(scan_result.team_summary)
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Generated with DevDiary*")

        logger.debug(f"Generated Markdown export ({len(lines)} lines)")
        return "\n".join(lines)

    def to_html(self, scan_result: ScanResult, options: ExportOptions) -> str:
        """
        Export scan result as HTML.

        Args:
            scan_result: ScanResult to export
            options: Export options

        Returns:
            HTML-formatted string
        """
        logger.debug("Generating HTML export")

        # Convert markdown to HTML (simple conversion)
        markdown_content = self.to_markdown(scan_result, options)

        # Simple markdown to HTML conversion
        html_body = self._markdown_to_html(markdown_content)

        # Wrap in HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevDiary Summary - {scan_result.scan_mode.value}</title>
    <style>
        :root {{
            --bg-color: #ffffff;
            --text-color: #24292e;
            --border-color: #e1e4e8;
            --code-bg: #f6f8fa;
            --link-color: #0366d6;
            --header-bg: #f6f8fa;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #0d1117;
                --text-color: #c9d1d9;
                --border-color: #30363d;
                --code-bg: #161b22;
                --link-color: #58a6ff;
                --header-bg: #161b22;
            }}
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--bg-color);
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        h1, h2, h3 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}

        h1 {{ font-size: 2em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}

        code {{
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            background-color: var(--code-bg);
            border-radius: 3px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        }}

        pre {{
            padding: 16px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            background-color: var(--code-bg);
            border-radius: 6px;
        }}

        ul, ol {{
            padding-left: 2em;
        }}

        li {{
            margin-top: 0.25em;
        }}

        strong {{
            font-weight: 600;
        }}

        hr {{
            height: 0.25em;
            padding: 0;
            margin: 24px 0;
            background-color: var(--border-color);
            border: 0;
        }}

        details {{
            margin-top: 16px;
            padding: 16px;
            background-color: var(--header-bg);
            border-radius: 6px;
        }}

        summary {{
            cursor: pointer;
            font-weight: 600;
        }}

        .header-info {{
            background-color: var(--header-bg);
            padding: 16px;
            border-radius: 6px;
            margin-bottom: 24px;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""

        logger.debug("Generated HTML export")
        return html

    def _markdown_to_html(self, markdown: str) -> str:
        """
        Convert Markdown to HTML (simple implementation).

        Args:
            markdown: Markdown text

        Returns:
            HTML text
        """
        import re

        html = markdown

        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Code
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # Lists
        html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n)+', r'<ul>\n\g<0></ul>\n', html, flags=re.MULTILINE)

        # Horizontal rule
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)

        # Paragraphs (simple: double newline = paragraph break)
        html = re.sub(r'\n\n', r'</p>\n<p>', html)
        html = '<p>' + html + '</p>'

        # Clean up empty paragraphs
        html = re.sub(r'<p>\s*</p>', '', html)

        return html

    def to_json(self, scan_result: ScanResult, options: ExportOptions) -> str:
        """
        Export scan result as JSON.

        Args:
            scan_result: ScanResult to export
            options: Export options

        Returns:
            JSON-formatted string
        """
        logger.debug("Generating JSON export")

        data = {
            "scan_mode": str(scan_result.scan_mode.value),
            "since_date": scan_result.since_date,
            "to_date": scan_result.to_date,
            "scan_time": scan_result.scan_time.isoformat(),
            "statistics": {
                "total_repos": scan_result.total_repos,
                "total_commits": scan_result.total_commits,
                "active_repos": len(scan_result.get_repos_with_activity()),
                "work_type_distribution": {
                    str(k.value): v for k, v in scan_result.work_type_distribution.items()
                },
            },
            "repositories": [],
        }

        # Add team summary if included
        if options.include_team_summary:
            data["team_summary"] = scan_result.team_summary

        # Add repositories
        for repo in scan_result.repositories:
            repo_data = {
                "name": repo.repo_name,
                "path": str(repo.repo_path),
            }

            if options.include_stats:
                repo_data["statistics"] = {
                    "commits": repo.commit_count,
                    "files_changed": repo.total_files_changed,
                    "insertions": repo.total_insertions,
                    "deletions": repo.total_deletions,
                    "work_type_counts": {
                        str(k.value): v for k, v in repo.work_type_counts.items()
                    },
                }

            if options.include_bullets:
                repo_data["bullets"] = repo.bullets

            if options.include_standup:
                repo_data["standup_summary"] = repo.standup_summary

            if options.include_diffs:
                repo_data["commits"] = [
                    {
                        "hash": c.commit_hash,
                        "message": c.message,
                        "work_type": str(c.work_type.value),
                        "files_changed": c.files_changed,
                        "insertions": c.insertions,
                        "deletions": c.deletions,
                    }
                    for c in repo.commits
                ]

            data["repositories"].append(repo_data)

        logger.debug(f"Generated JSON export ({len(data['repositories'])} repositories)")
        return json.dumps(data, indent=2, ensure_ascii=False)

    def to_pdf(self, scan_result: ScanResult, options: ExportOptions) -> str:
        """
        Export scan result as PDF (placeholder).

        Args:
            scan_result: ScanResult to export
            options: Export options

        Returns:
            Markdown string (PDF generation not yet implemented)
        """
        logger.warning("PDF export not yet implemented, returning Markdown instead")
        return self.to_markdown(scan_result, options)

    def generate_filename(
        self,
        scan_result: ScanResult,
        options: ExportOptions,
    ) -> str:
        """
        Generate filename based on pattern and scan result.

        Args:
            scan_result: ScanResult to generate filename for
            options: Export options (for file extension)

        Returns:
            Filename string
        """
        pattern = self.config.export.filename_pattern

        # Replace placeholders
        filename = pattern.replace("{mode}", str(scan_result.scan_mode.value))
        filename = filename.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
        filename = filename.replace("{time}", datetime.now().strftime("%H%M%S"))

        # Add extension
        filename = f"{filename}.{options.file_extension}"

        logger.debug(f"Generated filename: {filename}")
        return filename

    def save_to_file(
        self,
        scan_result: ScanResult,
        options: Optional[ExportOptions] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Export scan result and save to file.

        Args:
            scan_result: ScanResult to export
            options: Export options. If None, uses defaults.
            output_path: Optional explicit output path.
                        If None, uses config export directory.

        Returns:
            Path to saved file
        """
        if options is None:
            options = ExportOptions(format=self.config.export.default_format)

        logger.info(f"Saving export to file (format: {options.format})")

        # Generate content
        content = self.export(scan_result, options)

        # Determine output path
        if output_path is None:
            export_dir = self.config.get_export_directory()
            filename = self.generate_filename(scan_result, options)
            output_path = export_dir / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Export saved to: {output_path}")

        return output_path
