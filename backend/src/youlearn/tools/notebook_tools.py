"""NotebookTools — Agno toolkit for reading/writing the LaTeX notebook."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from agno.tools import Toolkit


class NotebookTools(Toolkit):
    """Read/write LaTeX notebook files for a specific class."""

    def __init__(self, class_dir: Path, backend_url: str = "http://localhost:8200"):
        self.class_dir = class_dir.resolve()
        self.backend_url = backend_url.rstrip("/")
        self.class_slug = class_dir.name
        tools = [
            self.read_file,
            self.write_file,
            self.list_files,
            self.create_lecture,
            self.create_session,
            self.compile_notes,
        ]
        super().__init__(name="notebook_tools", tools=tools)

    def _safe_path(self, path: str) -> Path | None:
        """Resolve a relative path and verify it doesn't escape class_dir."""
        target = (self.class_dir / path).resolve()
        if not str(target).startswith(str(self.class_dir)):
            return None
        return target

    def read_file(self, path: str) -> str:
        """Read a file from the notebook. Path is relative to the class directory.

        Examples:
          read_file("notes/latex/lec01/lec01.tex")
          read_file("hw/hw1/assignment.txt")
          read_file("notes/latex/master/master.tex")

        Args:
            path: Relative path within the class directory

        Returns:
            File contents as string, or error message if not found
        """
        target = self._safe_path(path)
        if target is None:
            return "Error: path escapes notebook directory"
        if not target.exists():
            return f"Error: file not found: {path}"
        return target.read_text()

    def write_file(self, path: str, content: str) -> str:
        """Write or update a file in the notebook. Creates parent directories if needed.

        Use this to write lecture content, update master.tex, etc.

        Args:
            path: Relative path within the class directory
            content: Full file content to write

        Returns:
            Confirmation message
        """
        target = self._safe_path(path)
        if target is None:
            return "Error: path escapes notebook directory"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Written: {path} ({len(content)} chars)"

    def list_files(self, subdir: str = "") -> str:
        """List files and directories in the notebook.

        Args:
            subdir: Subdirectory to list (default: root of class directory).
                    Examples: "notes/latex", "hw/hw1", "hw"

        Returns:
            Formatted listing of files and directories
        """
        target = self._safe_path(subdir)
        if target is None:
            return "Error: path escapes notebook directory"
        if not target.is_dir():
            return f"Error: not a directory: {subdir}"

        entries = sorted(target.iterdir())
        lines = []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            prefix = "d " if entry.is_dir() else "f "
            lines.append(f"{prefix}{entry.name}")
        return "\n".join(lines) if lines else "(empty directory)"

    def create_lecture(self, lecture_num: int, date: str, topic: str) -> str:
        """Create a new lecture file from the template and add it to master.tex.

        This copies the template, fills in the metadata, and adds a \\subfile
        line to master.tex. After calling this, use write_file to add content
        to the lecture.

        Args:
            lecture_num: Lecture number (e.g., 6 for lec06)
            date: Lecture date (e.g., "February 7, 2026")
            topic: Lecture topic (e.g., "Sequences and Series")

        Returns:
            Path to the new lecture file, ready for content
        """
        lec_id = f"lec{lecture_num:02d}"
        lec_dir = self.class_dir / "notes" / "latex" / lec_id
        lec_file = lec_dir / f"{lec_id}.tex"

        if lec_file.exists():
            return f"Error: {lec_id} already exists"

        # Copy template
        template = self.class_dir / "notes" / "latex" / "temp" / "temp.tex"
        if not template.exists():
            return "Error: template not found at notes/latex/temp/temp.tex"

        lec_dir.mkdir(parents=True, exist_ok=True)
        content = template.read_text()

        # Fill in metadata using str.replace (simpler and safer than regex)
        content = content.replace(
            r"\renewcommand{\lecturenum}{X}",
            f"\\renewcommand{{\\lecturenum}}{{{lecture_num}}}",
        )
        content = content.replace(
            r"\renewcommand{\lecturedate}{January 1, 2026}",
            f"\\renewcommand{{\\lecturedate}}{{{date}}}",
        )
        content = content.replace(
            r"\renewcommand{\lecturetopic}{Topic}",
            f"\\renewcommand{{\\lecturetopic}}{{{topic}}}",
        )
        content = content.replace(
            "% LECTURE X: Topic",
            f"% LECTURE {lecture_num}: {topic}",
        )
        content = content.replace(
            "% Date: January 1, 2026",
            f"% Date: {date}",
        )

        lec_file.write_text(content)

        # Add \subfile to master.tex at the ADD_LECTURE_HERE marker
        master_path = self.class_dir / "notes" / "latex" / "master" / "master.tex"
        if master_path.exists():
            master = master_path.read_text()
            marker = "% ADD_LECTURE_HERE"
            if marker in master:
                subfile_line = (
                    f"% Lecture {lecture_num}\n"
                    f"\\subfile{{../{lec_id}/{lec_id}}}\n"
                    f"\\newpage\n\n"
                )
                master = master.replace(marker, subfile_line + marker)
                master_path.write_text(master)
            else:
                return (
                    f"Created {lec_id}/{lec_id}.tex but could not find {marker} in "
                    f"master.tex — add \\subfile manually."
                )

        return f"Created {lec_id}/{lec_id}.tex — ready for content. Added to master.tex."

    def create_session(
        self,
        date: str,
        mode: str,
        summary: str,
        topics: str,
        covered: str,
        next_steps: str,
    ) -> str:
        """Create a session log as a .tex subfile and add it to sessions.tex.

        Called during /Done mode to record what was accomplished.

        Args:
            date: Session date in YYYY-MM-DD format (e.g., "2026-02-06")
            mode: Primary mode used (e.g., "Review", "Lecture", "Homework")
            summary: Brief session summary (1 sentence)
            topics: Comma-separated topics covered
            covered: What was accomplished (one item per line, will become \\item entries)
            next_steps: Suggested next steps (one item per line, will become \\item entries)

        Returns:
            Confirmation message with path to created session file
        """
        session_id = f"session-{date}"
        sessions_dir = self.class_dir / "notes" / "latex" / "sessions"
        session_file = sessions_dir / f"{session_id}.tex"

        if session_file.exists():
            return f"Error: {session_id}.tex already exists"

        # Build covered items and next_steps items as LaTeX \item lists
        covered_items = "\n".join(
            f"    \\item {line.strip()}"
            for line in covered.strip().split("\n")
            if line.strip()
        )
        next_items = "\n".join(
            f"    \\item {line.strip()}"
            for line in next_steps.strip().split("\n")
            if line.strip()
        )

        content = f"""\\documentclass[../master/master.tex]{{subfiles}}

\\begin{{document}}

\\subsection{{{date} --- {mode} Session}}

\\begin{{summarybox}}
\\textbf{{Session Summary}} \\\\
\\textbf{{Date:}} {date} \\\\
\\textbf{{Mode:}} {mode} \\\\
\\textbf{{Topics:}} {topics}
\\end{{summarybox}}

\\textbf{{What we covered:}}
\\begin{{itemize}}[nosep]
{covered_items}
\\end{{itemize}}

\\textbf{{Next steps:}}
\\begin{{itemize}}[nosep]
{next_items}
\\end{{itemize}}

\\end{{document}}
"""
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_file.write_text(content)

        # Add \subfile to sessions.tex container
        container = sessions_dir / "sessions.tex"
        if container.exists():
            container_content = container.read_text()
            marker = "% ADD_SESSION_HERE"
            if marker in container_content:
                subfile_line = f"\\subfile{{{session_id}}}\n\n"
                container_content = container_content.replace(
                    marker, subfile_line + marker
                )
                container.write_text(container_content)

        return f"Created session log: notes/latex/sessions/{session_id}.tex"

    def compile_notes(self, target: str = "master") -> str:
        """Compile LaTeX notes to PDF using pdflatex + makeindex.

        For "master", runs the 3-pass build: pdflatex -> makeindex -> pdflatex.
        This generates the table of contents and Index of Definitions.
        For individual lectures, runs a single pdflatex pass.

        Args:
            target: What to compile. "master" compiles the full notebook.
                    "lec01", "lec02", etc. compiles a single lecture.

        Returns:
            Success message with the PDF path, or error details.
        """
        if target == "master":
            tex_path = self.class_dir / "notes" / "latex" / "master" / "master.tex"
        else:
            tex_path = (
                self.class_dir / "notes" / "latex" / target / f"{target}.tex"
            )

        if not tex_path.exists():
            return f"Error: {tex_path.name} not found"

        cwd = str(tex_path.parent)
        tex_name = tex_path.name

        try:
            if target == "master":
                # 3-pass build: pdflatex -> makeindex -> pdflatex
                for step in [
                    ["pdflatex", "-interaction=nonstopmode", tex_name],
                    ["makeindex", tex_path.with_suffix(".idx").name],
                    ["pdflatex", "-interaction=nonstopmode", tex_name],
                ]:
                    result = subprocess.run(
                        step,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        cwd=cwd,
                    )
                    # makeindex may fail if no .idx exists yet — that's OK
                    if result.returncode != 0 and step[0] == "pdflatex":
                        # pdflatex writes errors to stdout, not stderr
                        output = result.stdout or result.stderr or "(no output)"
                        err_lines = [l for l in output.splitlines() if l.startswith("!")]
                        detail = "\n".join(err_lines) if err_lines else output[-500:]
                        return f"Compilation failed at {step[0]}:\n{detail}"
            else:
                # Single-pass for individual lectures
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", tex_name],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=cwd,
                )
                if result.returncode != 0:
                    output = result.stdout or result.stderr or "(no output)"
                    err_lines = [l for l in output.splitlines() if l.startswith("!")]
                    detail = "\n".join(err_lines) if err_lines else output[-500:]
                    return f"Compilation failed:\n{detail}"

        except FileNotFoundError:
            return "Error: pdflatex not installed. Install TeX Live."
        except subprocess.TimeoutExpired:
            return "Error: compilation timed out after 120 seconds"

        pdf_path = tex_path.with_suffix(".pdf")
        if not pdf_path.exists():
            return "Error: PDF not generated"

        # Copy master PDF to class root (matching Makefile behavior)
        if target == "master":
            root_pdf = self.class_dir / f"{self.class_dir.name}-Notes.pdf"
            shutil.copy2(pdf_path, root_pdf)
            download_url = f"{self.backend_url}/pdf/{self.class_slug}/{root_pdf.name}"
            return (
                f"Compiled successfully ({pdf_path.stat().st_size // 1024}KB). "
                f"Download: {download_url}"
            )

        # For individual lectures, copy PDF to class root too for easy access
        lec_pdf_name = f"{target}.pdf"
        root_lec_pdf = self.class_dir / lec_pdf_name
        shutil.copy2(pdf_path, root_lec_pdf)
        download_url = f"{self.backend_url}/pdf/{self.class_slug}/{lec_pdf_name}"
        return (
            f"Compiled successfully. "
            f"Download: {download_url}"
        )
