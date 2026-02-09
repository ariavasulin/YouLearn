"""Context loading: reads .tex files, extracts summaries, assembles prompt context."""

from __future__ import annotations

import re
from pathlib import Path

_RE_RENEW = re.compile(r"\\renewcommand\{\\(\w+)\}\{(.+?)\}")
_RE_SUMMARY = re.compile(
    r"\\begin\{lecturesummary\}(.*?)\\end\{lecturesummary\}",
    re.DOTALL,
)
_RE_SUMMARYBOX = re.compile(
    r"\\begin\{summarybox\}(.*?)\\end\{summarybox\}",
    re.DOTALL,
)


def extract_lecture_metadata(tex_content: str) -> dict:
    """Extract metadata from a lecture .tex file.

    Returns: {
        "num": "1",
        "date": "January 20, 2026",
        "topic": "Ordered sets, least-upper-bound property; fields.",
        "summary": "We begin by proving sqrt(2) is irrational...",
        "summaryboxes": ["Section Overview: ..."]
    }
    """
    metadata: dict = {}

    # Parse \renewcommand{\lecturenum}{X} etc.
    field_map = {
        "lecturenum": "num",
        "lecturedate": "date",
        "lecturetopic": "topic",
    }
    for match in _RE_RENEW.finditer(tex_content):
        cmd_name = match.group(1)
        if cmd_name in field_map:
            metadata[field_map[cmd_name]] = match.group(2)

    # Extract lecturesummary content
    summary_match = _RE_SUMMARY.search(tex_content)
    if summary_match:
        metadata["summary"] = summary_match.group(1).strip()
    else:
        metadata["summary"] = ""

    # Extract all summarybox contents
    metadata["summaryboxes"] = [
        m.group(1).strip() for m in _RE_SUMMARYBOX.finditer(tex_content)
    ]

    return metadata


def extract_preamble_commands(master_tex: str) -> str:
    """Extract the preamble section of master.tex (before \\begin{document}).

    Returns just the custom commands, environments, and color definitions
    so the agent knows what's available when writing lecture content.
    """
    idx = master_tex.find(r"\begin{document}")
    if idx == -1:
        return master_tex
    return master_tex[:idx]


def discover_lectures(class_dir: Path) -> list[Path]:
    """Find all lecture .tex files, sorted by number.

    Looks for classes/{slug}/notes/latex/lecXX/lecXX.tex
    Returns sorted list of paths.
    """
    latex_dir = class_dir / "notes" / "latex"
    lectures = []
    if not latex_dir.exists():
        return lectures
    for d in sorted(latex_dir.iterdir()):
        if d.is_dir() and d.name.startswith("lec"):
            tex_file = d / f"{d.name}.tex"
            if tex_file.exists():
                lectures.append(tex_file)
    return lectures


def _read_safe(path: Path) -> str:
    """Read a file, returning empty string if it doesn't exist."""
    if path.exists():
        return path.read_text()
    return ""


def _all_lecture_metadata(class_dir: Path) -> list[dict]:
    """Extract metadata from all lectures."""
    results = []
    for lec_path in discover_lectures(class_dir):
        content = lec_path.read_text()
        meta = extract_lecture_metadata(content)
        meta["path"] = str(lec_path.relative_to(class_dir))
        results.append(meta)
    return results


def _format_lecture_index(all_meta: list[dict]) -> str:
    """Format a compact index of all lectures with metadata."""
    lines = ["### Lecture Index"]
    for meta in all_meta:
        num = meta.get("num", "?")
        date = meta.get("date", "?")
        topic = meta.get("topic", "?")
        lines.append(f"- Lecture {num} ({date}): {topic}")
    return "\n".join(lines)


def _format_lecture_summaries(all_meta: list[dict]) -> str:
    """Format all lecture summaries."""
    lines = ["### Lecture Summaries"]
    for meta in all_meta:
        num = meta.get("num", "?")
        topic = meta.get("topic", "?")
        summary = meta.get("summary", "")
        lines.append(f"\n**Lecture {num}: {topic}**")
        if summary:
            lines.append(summary)
        else:
            lines.append("(no summary available)")
    return "\n".join(lines)


def _format_summaryboxes(all_meta: list[dict]) -> str:
    """Format all section summaryboxes from lectures."""
    lines = ["### Section Summaries"]
    for meta in all_meta:
        num = meta.get("num", "?")
        boxes = meta.get("summaryboxes", [])
        if boxes:
            lines.append(f"\n**Lecture {num} sections:**")
            for box in boxes:
                lines.append(f"- {box[:200]}")
    return "\n".join(lines)


def _list_sessions(class_dir: Path) -> str:
    """List existing session files."""
    sessions_dir = class_dir / "notes" / "latex" / "sessions"
    if not sessions_dir.exists():
        return "No sessions directory found."
    files = sorted(
        f.name for f in sessions_dir.iterdir() if f.name.startswith("session-")
    )
    if not files:
        return "No session logs yet."
    return "### Existing Sessions\n" + "\n".join(f"- {f}" for f in files)


def _list_hw_dirs(class_dir: Path) -> str:
    """List homework directories."""
    hw_dir = class_dir / "hw"
    if not hw_dir.exists():
        return "No hw directory found."
    dirs = sorted(
        d.name for d in hw_dir.iterdir() if d.is_dir() and d.name.startswith("hw")
    )
    if not dirs:
        return "No homework directories yet."
    return "### Homework Directories\n" + "\n".join(f"- {d}/" for d in dirs)


def _load_page_map(class_dir: Path) -> str:
    """Load the page map from master.aux if it exists.

    Returns a formatted string with section -> page mappings,
    or empty string if no .aux file is available.
    """
    aux_path = class_dir / "notes" / "latex" / "master" / "master.aux"
    if not aux_path.exists():
        return ""

    content = aux_path.read_text()
    page_map: dict[str, int] = {}

    pattern = re.compile(
        r"\\contentsline\s*\{(?:section|subsection)\}"
        r"\{(?:\\numberline\s*\{[^}]*\})?(.+?)\}"
        r"\{(\d+)\}"
    )

    for match in pattern.finditer(content):
        title = match.group(1).strip()
        page = int(match.group(2))
        title = re.sub(r"\\[a-zA-Z]+\s*", "", title)
        title = title.replace("\\&", "&")
        title = title.replace("---", "\u2014").replace("--", "\u2013")
        title = title.replace("{", "").replace("}", "")
        title = title.replace("$", "")
        title = re.sub(r"\s+", " ", title).strip()
        if title:
            page_map[title] = page

    if not page_map:
        return ""

    lines = ["### Page Map (from last compilation)"]
    lines.append("Use these page numbers with `#page=N` when linking to the PDF.")
    for title, page in page_map.items():
        lines.append(f"- {title}: page {page}")
    return "\n".join(lines)


def build_context(
    class_dir: Path,
    mode: str,
    hw_id: str | None = None,
) -> str:
    """Build the notebook context string for the given mode.

    This is injected into the system prompt so the agent has
    notebook knowledge without needing to call tools first.
    """
    latex_dir = class_dir / "notes" / "latex"
    all_meta = _all_lecture_metadata(class_dir)
    parts: list[str] = []

    if mode == "lec":
        # 1. Preamble commands
        master_tex = _read_safe(latex_dir / "master" / "master.tex")
        preamble = extract_preamble_commands(master_tex)
        parts.append("### LaTeX Preamble (available commands)\n```latex\n" + preamble + "\n```")

        # 2. Template
        template = _read_safe(latex_dir / "temp" / "temp.tex")
        parts.append("### Lecture Template (temp.tex)\n```latex\n" + template + "\n```")

        # 3. Last 2 full lectures
        lectures = discover_lectures(class_dir)
        last_two = lectures[-2:] if len(lectures) >= 2 else lectures
        for lec_path in last_two:
            content = lec_path.read_text()
            name = lec_path.parent.name
            parts.append(f"### Full content: {name}\n```latex\n{content}\n```")

        # 4. Metadata for all earlier lectures
        parts.append(_format_lecture_index(all_meta))

        # 5. Syllabus calendar
        syllabus = _read_safe(latex_dir / "syllabus" / "syllabus.tex")
        if syllabus:
            parts.append("### Syllabus\n```latex\n" + syllabus + "\n```")

    elif mode == "rev":
        # 1. All lecture summaries
        parts.append(_format_lecture_summaries(all_meta))

        # 2. Section summaryboxes
        parts.append(_format_summaryboxes(all_meta))

        # 3. Glossary
        glossary = _read_safe(latex_dir / "glossary" / "glossary.tex")
        if glossary:
            parts.append("### Glossary\n```latex\n" + glossary + "\n```")

    elif mode == "work":
        # 1. Assignment.txt for the specified hw
        if hw_id:
            hw_dir = class_dir / "hw" / hw_id
            assignment = _read_safe(hw_dir / "assignment.txt")
            if assignment:
                parts.append(f"### Assignment ({hw_id})\n{assignment}")
            else:
                parts.append(f"### Assignment ({hw_id})\nNo assignment.txt found for {hw_id}.")

            # 2. Current submission
            submission_dir = hw_dir / "submission"
            if submission_dir.exists():
                for f in sorted(submission_dir.iterdir()):
                    if f.suffix == ".tex":
                        parts.append(
                            f"### Current submission: {f.name}\n```latex\n{f.read_text()}\n```"
                        )

            # 3. Existing explainers
            explainers_dir = hw_dir / "explainers"
            if explainers_dir.exists():
                for edir in sorted(explainers_dir.iterdir()):
                    if edir.is_dir():
                        for f in sorted(edir.iterdir()):
                            if f.suffix == ".tex":
                                parts.append(
                                    f"### Explainer: {f.name}\n```latex\n{f.read_text()}\n```"
                                )
        else:
            parts.append("No homework specified. Available homework directories:")
            parts.append(_list_hw_dirs(class_dir))

        # 4. Assignments overview
        assignments = _read_safe(latex_dir / "assignments" / "assignments.tex")
        if assignments:
            parts.append("### Assignments Overview\n```latex\n" + assignments + "\n```")

        # 5. Lecture summaries
        parts.append(_format_lecture_summaries(all_meta))

    elif mode == "done":
        # 1. Lecture metadata
        parts.append(_format_lecture_index(all_meta))

        # 2. Existing sessions
        parts.append(_list_sessions(class_dir))

        # 3. Sessions.tex container
        sessions_tex = _read_safe(latex_dir / "sessions" / "sessions.tex")
        if sessions_tex:
            parts.append("### sessions.tex\n```latex\n" + sessions_tex + "\n```")

    else:  # default
        # 1. Syllabus overview
        syllabus = _read_safe(latex_dir / "syllabus" / "syllabus.tex")
        if syllabus:
            parts.append("### Syllabus\n```latex\n" + syllabus + "\n```")

        # 2. Lecture summaries
        parts.append(_format_lecture_summaries(all_meta))

        # 3. Homework dirs
        parts.append(_list_hw_dirs(class_dir))

        # 4. Sessions
        parts.append(_list_sessions(class_dir))

    # Append page map from last compilation if available (all modes)
    page_map = _load_page_map(class_dir)
    if page_map:
        parts.append(page_map)

    return "\n\n".join(parts)
