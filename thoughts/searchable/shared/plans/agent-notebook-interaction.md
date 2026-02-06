# Plan: Agent-Notebook Interaction Layer

**Date**: 2026-02-06
**Scope**: Mode detection, system prompts, context loading, NotebookTools, LaTeX compilation
**Status**: Implemented

---

## Overview

This plan covers how the Agno agent reads, writes, and compiles the LaTeX notebook in `classes/`. It defines: (1) how /Lec, /Rev, /Work, /Done commands change agent behavior, (2) what .tex content gets injected per mode, (3) the NotebookTools API the agent uses, (4) system prompt templates, and (5) compilation strategy.

**Constraint**: The demo uses the pre-existing `classes/Math-104/` notebook (restructured per `thoughts/shared/plans/notebook-restructure.md`). No class creation needed — the agent works with what's already there. Hardcode `Math-104` as the active class for the hackathon.

**Depends on**: `notebook-restructure.md` must be implemented first (new sections: syllabus, assignments, sessions, resources, glossary in master.tex).

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/src/youlearn/modes.py` | **Create** | Mode detection + system prompt builder |
| `backend/src/youlearn/context.py` | **Create** | Context loading: reads .tex files, extracts summaries, assembles prompt context |
| `backend/src/youlearn/tools/notebook_tools.py` | **Create** | NotebookTools Agno toolkit (read/write/create lecture/compile) |
| `backend/src/youlearn/tools/__init__.py` | **Create** | Empty init |
| `backend/src/youlearn/server.py` | **Modify** | Wire up modes, context loading, NotebookTools instead of generic FileTools/ShellTools |
| `backend/src/youlearn/config.py` | **Modify** | Add `active_class` setting (default: `Math-104`) |

---

## Step 1: Mode Detection (`modes.py`)

### Mode Detection Function

The agent mode is determined by the latest user message. If the user sends `/Lec`, `/Rev`, `/Work`, or `/Done` (case-insensitive), the backend switches mode. Anything else stays in `default` mode (general helpful chat with notebook access).

```python
# backend/src/youlearn/modes.py

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Mode:
    name: str           # "lec", "rev", "work", "done", "default"
    user_message: str   # The user's message with the command stripped


def detect_mode(latest_message: str) -> Mode:
    """Detect mode from the latest user message.

    Returns the mode and the message with the command prefix stripped.
    Examples:
      "/Lec Today we're covering topology" -> Mode("lec", "Today we're covering topology")
      "/Rev Quiz me on lecture 3"          -> Mode("rev", "Quiz me on lecture 3")
      "/Work hw2"                          -> Mode("work", "hw2")
      "/Done"                              -> Mode("done", "")
      "What is a compact set?"             -> Mode("default", "What is a compact set?")
    """
    stripped = latest_message.strip()
    lower = stripped.lower()

    for prefix in ("lec", "rev", "work", "done"):
        if lower.startswith(f"/{prefix}"):
            rest = stripped[len(prefix) + 1:].strip()
            return Mode(name=prefix, user_message=rest)

    return Mode(name="default", user_message=stripped)
```

**Key decision**: The mode command is detected on *every* user message, not just the first. This means the user can switch modes mid-conversation. The mode from the latest message is what controls agent behavior for that response.

### Success Criteria
- `/lec`, `/Lec`, `/LEC` all detected as "lec" mode
- `/Lec some content here` strips the prefix and passes content through
- `/Done` with no trailing content works
- A plain message returns "default" mode
- `/rev quiz me` extracts "quiz me" as user_message

---

## Step 2: Context Loading (`context.py`)

### Architecture

Context loading reads .tex files from the notebook and assembles them into a string that gets injected into the system prompt. The key challenge: LaTeX is verbose (~200-400 lines per lecture), so we need a hierarchical strategy.

### Context Extraction Functions

```python
# backend/src/youlearn/context.py

from __future__ import annotations
import re
from pathlib import Path


def extract_lecture_metadata(tex_content: str) -> dict:
    """Extract metadata from a lecture .tex file.

    Returns: {
        "num": "1",
        "date": "January 20, 2026",
        "topic": "Ordered sets, least-upper-bound property; fields.",
        "summary": "We begin by proving sqrt(2) is irrational..."
    }
    """
    # Parse \renewcommand{\lecturenum}{X}
    # Parse \renewcommand{\lecturedate}{...}
    # Parse \renewcommand{\lecturetopic}{...}
    # Extract text between \begin{lecturesummary} and \end{lecturesummary}
```

Implementation: use simple regex. The .tex files follow a strict template, so this is reliable.

```python
_RE_RENEW = re.compile(r"\\renewcommand\{\\(\w+)\}\{(.+?)\}")
_RE_SUMMARY = re.compile(
    r"\\begin\{lecturesummary\}(.*?)\\end\{lecturesummary\}",
    re.DOTALL,
)
_RE_SUMMARYBOX = re.compile(
    r"\\begin\{summarybox\}(.*?)\\end\{summarybox\}",
    re.DOTALL,
)
```

### Preamble Extraction

For /Lec mode, the agent needs to know what LaTeX commands are available. Rather than loading the entire master.tex (which includes \subfile lines), extract just the preamble commands.

```python
def extract_preamble_commands(master_tex: str) -> str:
    """Extract the preamble section of master.tex (before \\begin{document}).

    Returns just the custom commands, environments, and color definitions
    so the agent knows what's available when writing lecture content.
    """
    idx = master_tex.find(r"\begin{document}")
    if idx == -1:
        return master_tex
    return master_tex[:idx]
```

### Main Context Builder

```python
def build_context(
    class_dir: Path,
    mode: str,
    hw_id: str | None = None,
) -> str:
    """Build the notebook context string for the given mode.

    This is injected into the system prompt so the agent has
    notebook knowledge without needing to call tools first.
    """
```

#### Mode: "lec"
Load:
1. Preamble commands (so agent knows available environments/commands) — ~80 lines
2. The temp.tex template (so agent knows the lecture structure to follow) — ~30 lines
3. Last 2 lecture .tex files in full (for style continuity and cross-referencing) — ~400-800 lines
4. Metadata (num, date, topic, summary) for ALL earlier lectures — ~50 lines total
5. Syllabus calendar section (so agent knows what topic is expected today) — ~30 lines

Token estimate: ~4-6K tokens

#### Mode: "rev"
Load:
1. Metadata + lecture summaries for ALL lectures (Level 1) — ~200 lines total
2. Section summaries (summarybox content) for all lectures (Level 2) — ~400 lines total
3. Glossary content (for quizzing on terms) — ~100 lines
4. Full content of lectures is NOT pre-loaded — agent uses `read_file` tool on-demand

Token estimate: ~4-5K tokens upfront, agent fetches full lectures as needed

#### Mode: "work"
Load:
1. The specific homework's assignment.txt — ~5 lines
2. The current submission .tex (if exists) — ~50-200 lines
3. Any existing explainers for this homework — ~100-300 lines each
4. Assignments section overview (for cross-referencing related lectures) — ~50 lines
5. Metadata + summaries for all lectures (agent picks which to read in full) — ~200 lines

hw_id is parsed from the user message. If user says `/Work hw2`, hw_id = "hw2". If ambiguous, agent asks.

Token estimate: ~3-5K tokens

#### Mode: "done"
Load:
1. Metadata for all lectures (num, topic) — ~20 lines
2. List of existing session logs (so agent doesn't create duplicates) — ~10 lines
3. The sessions.tex container (so agent knows the ADD_SESSION_HERE marker pattern) — ~15 lines

The agent processes the conversation history directly (it already has it from the messages).

Token estimate: ~1K tokens

#### Mode: "default"
Load:
1. Syllabus overview (course info, calendar) — ~80 lines
2. Metadata + summaries for all lectures — ~200 lines
3. List of homework directories — ~10 lines
4. List of existing sessions — ~10 lines

Token estimate: ~3K tokens

### Implementation Detail: Lecture Discovery

```python
def discover_lectures(class_dir: Path) -> list[Path]:
    """Find all lecture .tex files, sorted by number.

    Looks for classes/{slug}/notes/latex/lecXX/lecXX.tex
    Returns sorted list of paths.
    """
    latex_dir = class_dir / "notes" / "latex"
    lectures = []
    for d in sorted(latex_dir.iterdir()):
        if d.is_dir() and d.name.startswith("lec"):
            tex_file = d / f"{d.name}.tex"
            if tex_file.exists():
                lectures.append(tex_file)
    return lectures
```

### Success Criteria
- `extract_lecture_metadata` correctly parses all 5 Math-104 lectures
- `build_context("lec")` includes the preamble and last 2 full lectures
- `build_context("rev")` includes all lecture summaries without full content
- `build_context("work", hw_id="hw1")` includes assignment.txt content and submission

---

## Step 3: NotebookTools Agno Toolkit (`tools/notebook_tools.py`)

### Design Decisions

1. **Keep it minimal for hackathon**: 6 tool functions, not 9. Skip `create_class`, `create_homework`, `create_explainer` — the demo uses the existing Math-104 notebook.
2. **Compilation is a tool**: The agent calls `compile_notes()` to produce a PDF. This uses pdflatex + makeindex (3-pass, matching the existing Makefile).
3. **Read/write are path-scoped**: All paths are relative to the class directory. The agent can't escape.
4. **`create_lecture` inserts at `ADD_LECTURE_HERE` marker**: Not before `\end{document}` — that would put lectures after the glossary.
5. **`create_session` handles /Done ceremony**: Creates session .tex subfile and adds to sessions.tex container.

### Tool Functions

```python
# backend/src/youlearn/tools/notebook_tools.py

from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from agno.tools import Toolkit


class NotebookTools(Toolkit):
    """Read/write LaTeX notebook files for a specific class."""

    def __init__(self, class_dir: Path):
        self.class_dir = class_dir
        super().__init__(name="notebook_tools")
        self.register(self.read_file)
        self.register(self.write_file)
        self.register(self.list_files)
        self.register(self.create_lecture)
        self.register(self.create_session)
        self.register(self.compile_notes)
```

#### Tool 1: `read_file(path: str) -> str`

```python
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
    target = (self.class_dir / path).resolve()
    # Security: ensure path doesn't escape class_dir
    if not str(target).startswith(str(self.class_dir.resolve())):
        return "Error: path escapes notebook directory"
    if not target.exists():
        return f"Error: file not found: {path}"
    return target.read_text()
```

#### Tool 2: `write_file(path: str, content: str) -> str`

```python
def write_file(self, path: str, content: str) -> str:
    """Write or update a file in the notebook. Creates parent directories if needed.

    Use this to write lecture content, update master.tex, etc.

    Args:
        path: Relative path within the class directory
        content: Full file content to write

    Returns:
        Confirmation message
    """
    target = (self.class_dir / path).resolve()
    if not str(target).startswith(str(self.class_dir.resolve())):
        return "Error: path escapes notebook directory"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Written: {path} ({len(content)} chars)"
```

#### Tool 3: `list_files(subdir: str = "") -> str`

```python
def list_files(self, subdir: str = "") -> str:
    """List files and directories in the notebook.

    Args:
        subdir: Subdirectory to list (default: root of class directory).
                Examples: "notes/latex", "hw/hw1", "hw"

    Returns:
        Formatted listing of files and directories
    """
    target = (self.class_dir / subdir).resolve()
    if not str(target).startswith(str(self.class_dir.resolve())):
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
```

#### Tool 4: `create_lecture(lecture_num: int, date: str, topic: str) -> str`

```python
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

    # Fill in metadata
    content = re.sub(
        r"\\renewcommand\{\\lecturenum\}\{X\}",
        f"\\\\renewcommand{{\\\\lecturenum}}{{{lecture_num}}}",
        content,
    )
    content = re.sub(
        r"\\renewcommand\{\\lecturedate\}\{January 1, 2026\}",
        f"\\\\renewcommand{{\\\\lecturedate}}{{{date}}}",
        content,
    )
    content = re.sub(
        r"\\renewcommand\{\\lecturetopic\}\{Topic\}",
        f"\\\\renewcommand{{\\\\lecturetopic}}{{{topic}}}",
        content,
    )
    # Update the header comment
    content = re.sub(
        r"% LECTURE X: Topic",
        f"% LECTURE {lecture_num}: {topic}",
        content,
    )
    content = re.sub(
        r"% Date: January 1, 2026",
        f"% Date: {date}",
        content,
    )

    lec_file.write_text(content)

    # Add \subfile to master.tex at the ADD_LECTURE_HERE marker
    master_path = self.class_dir / "notes" / "latex" / "master" / "master.tex"
    if master_path.exists():
        master = master_path.read_text()
        marker = "% ADD_LECTURE_HERE"
        if marker in master:
            subfile_line = f"% Lecture {lecture_num}\n\\subfile{{../{lec_id}/{lec_id}}}\n\\newpage\n\n"
            master = master.replace(marker, subfile_line + marker)
        else:
            return f"Created {lec_id}/{lec_id}.tex but could not find {marker} in master.tex — add \\subfile manually."
        master_path.write_text(master)

    return f"Created {lec_id}/{lec_id}.tex — ready for content. Added to master.tex."
```

**Note**: The regex replacement here is intentionally simple. In a real implementation, test carefully with the actual temp.tex. The `\\\\` escaping may need adjustment — use raw strings or string replacement instead of `re.sub` for the `\renewcommand` lines. Simpler approach: just use `str.replace()`:

```python
content = content.replace(
    r"\renewcommand{\lecturenum}{X}",
    f"\\renewcommand{{\\lecturenum}}{{{lecture_num}}}",
)
```

#### Tool 5: `create_session(date: str, mode: str, summary: str, topics: str, covered: str, next_steps: str) -> str`

```python
def create_session(self, date: str, mode: str, summary: str, topics: str, covered: str, next_steps: str) -> str:
    """Create a session log as a .tex subfile and add it to sessions.tex.

    Called during /Done mode to record what was accomplished.

    Args:
        date: Session date (e.g., "February 6, 2026")
        mode: Primary mode used (e.g., "Review", "Lecture", "Homework")
        summary: Brief session summary (1 sentence)
        topics: Comma-separated topics covered
        covered: Bullet points of what was accomplished (newline-separated)
        next_steps: Bullet points of suggested next steps (newline-separated)

    Returns:
        Confirmation message with path to created session file
    """
    # Generate filename from date: "February 6, 2026" -> "session-2026-02-06"
    # (agent provides ISO-ish date, we normalize)
    session_id = f"session-{date}"  # agent should pass YYYY-MM-DD format
    sessions_dir = self.class_dir / "notes" / "latex" / "sessions"
    session_file = sessions_dir / f"{session_id}.tex"

    if session_file.exists():
        return f"Error: {session_id}.tex already exists"

    # Build covered items and next_steps items as LaTeX \item lists
    covered_items = "\n".join(f"    \\item {line.strip()}" for line in covered.strip().split("\n") if line.strip())
    next_items = "\n".join(f"    \\item {line.strip()}" for line in next_steps.strip().split("\n") if line.strip())

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
            container_content = container_content.replace(marker, subfile_line + marker)
            container.write_text(container_content)

    return f"Created session log: notes/latex/sessions/{session_id}.tex"
```

#### Tool 6: `compile_notes(target: str = "master") -> str`

```python
def compile_notes(self, target: str = "master") -> str:
    """Compile LaTeX notes to PDF using pdflatex + makeindex.

    For "master", runs the 3-pass build: pdflatex → makeindex → pdflatex.
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
        tex_path = self.class_dir / "notes" / "latex" / target / f"{target}.tex"

    if not tex_path.exists():
        return f"Error: {tex_path.name} not found"

    cwd = str(tex_path.parent)
    tex_name = tex_path.name

    try:
        if target == "master":
            # 3-pass build: pdflatex → makeindex → pdflatex
            for step in [
                ["pdflatex", "-interaction=nonstopmode", tex_name],
                ["makeindex", tex_path.with_suffix(".idx").name],
                ["pdflatex", "-interaction=nonstopmode", tex_name],
            ]:
                result = subprocess.run(
                    step, capture_output=True, text=True, timeout=120, cwd=cwd,
                )
                # makeindex may fail if no .idx exists yet — that's OK
                if result.returncode != 0 and step[0] == "pdflatex":
                    return f"Compilation failed at {step[0]}:\n{result.stderr[:500]}"
        else:
            # Single-pass for individual lectures
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_name],
                capture_output=True, text=True, timeout=120, cwd=cwd,
            )
            if result.returncode != 0:
                return f"Compilation failed:\n{result.stderr[:500]}"

    except FileNotFoundError:
        return "Error: pdflatex not installed. Install TeX Live."
    except subprocess.TimeoutExpired:
        return "Error: compilation timed out after 120 seconds"

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        return "Error: PDF not generated"

    # Copy master PDF to class root (matching Makefile behavior)
    if target == "master":
        root_pdf = self.class_dir / "Math104-Notes.pdf"
        shutil.copy2(pdf_path, root_pdf)
        return f"Compiled successfully: Math104-Notes.pdf ({pdf_path.stat().st_size // 1024}KB)"

    return f"Compiled successfully: {pdf_path.relative_to(self.class_dir)}"
```

**PDF artifact delivery**: For the hackathon, the compile tool just reports success and the PDF path. A stretch goal would be to base64-encode it and return it as an OpenWebUI HTML artifact (like YouLab does). If we add artifact support, it goes in this function.

### Success Criteria
- `read_file("notes/latex/lec01/lec01.tex")` returns lec01 content
- `read_file("../../etc/passwd")` returns path escape error
- `write_file("notes/latex/lec06/lec06.tex", content)` creates the file
- `list_files("notes/latex")` shows master/, lec01/, ..., syllabus/, assignments/, sessions/, resources/, glossary/, temp/
- `create_lecture(6, "February 7, 2026", "Sequences")` creates lec06 and inserts before `ADD_LECTURE_HERE` in master.tex
- `create_session("2026-02-06", "Review", ...)` creates session .tex and updates sessions.tex container
- `compile_notes("master")` produces PDF via pdflatex + makeindex (requires TeX Live installed)
- `compile_notes("lec01")` produces standalone lecture PDF via single pdflatex pass

---

## Step 4: System Prompts (`modes.py`, continued)

### Prompt Architecture

Each mode gets a system prompt assembled from 3 parts:
1. **Base instructions** — Always present. Defines the agent's identity, the notebook structure, available tools.
2. **Mode instructions** — Mode-specific behavior, constraints, interaction style.
3. **Context block** — The pre-loaded notebook content from `context.py`.

```python
def build_system_prompt(mode: str, context: str, class_name: str) -> str:
    return f"""{BASE_PROMPT.format(class_name=class_name)}

{MODE_PROMPTS[mode]}

---
## Pre-loaded Notebook Context

The following content is from the student's notebook. Use it to inform your responses.

{context}"""
```

### Base Prompt (always included)

```python
BASE_PROMPT = """You are YouLearn, an AI study companion for {class_name}.

You manage a LaTeX notebook for this class using the subfiles pattern. The notebook compiles to a single PDF with this structure:

1. **Syllabus** — Course overview, requirements, objectives, calendar
2. **Lectures** — One section per lecture (lec01–lec05 exist, more can be created)
3. **Assignments** — Homework summaries with status and related lectures
4. **Sessions** — Study session logs (you create these during /Done)
5. **Resources** — Textbook and supplementary materials
6. **Glossary** — Curated definitions organized by topic
7. **Index of Definitions** — Auto-generated page index from \\defn{{}} commands

### Key Paths
- `notes/latex/master/master.tex` — Master document (preamble + \\subfile includes)
- `notes/latex/lecXX/lecXX.tex` — Individual lectures (compile standalone or via master)
- `notes/latex/syllabus/syllabus.tex` — Course syllabus
- `notes/latex/assignments/assignments.tex` — Assignment summaries
- `notes/latex/sessions/sessions.tex` — Session log container (has ADD_SESSION_HERE marker)
- `notes/latex/resources/resources.tex` — Course resources
- `notes/latex/glossary/glossary.tex` — Curated glossary
- `hw/hwN/` — Homework directories with assignment.txt, submission/, explainers/

### Available LaTeX Commands
- \\defn{{term}} — Red bold text + auto-index entry for key definitions
- `lecturesummary` environment — Orange box for lecture/section overview
- `summarybox` environment — Baby blue box for subsection overview
- `notebox` environment — Light red box for notes to reader
- theorem, lemma, proposition, corollary, definition, example, remark environments
- \\R, \\N, \\Z, \\Q, \\C — Blackboard bold number sets
- \\eps — Varepsilon

### Tools
You have access to notebook tools:
- `read_file(path)` — Read any file in the notebook
- `write_file(path, content)` — Write/update any file
- `list_files(subdir)` — List files in a directory
- `create_lecture(num, date, topic)` — Create a new lecture from template, add to master.tex
- `create_session(date, mode, summary, topics, covered, next_steps)` — Create a session log .tex subfile
- `compile_notes(target)` — Compile to PDF using pdflatex + makeindex ("master" or "lecXX")

### Rules
- Write .tex files for all notebook content
- Use \\defn{{term}} for every new key term or definition
- Follow the established lecture structure: header comment, \\renewcommand metadata, \\section, lecturesummary, subsections with summarybox
- Compile with pdflatex + makeindex (3-pass for master, single-pass for individual lectures)
- New lectures insert at the ADD_LECTURE_HERE marker in master.tex
- New sessions insert at the ADD_SESSION_HERE marker in sessions.tex"""
```

### /Lec System Prompt — Live Lecture Mode

```python
MODE_PROMPTS = {
    "lec": """## Mode: Live Lecture (/Lec)

You are in DICTATION MODE. The student is in a live lecture and is feeding you content to organize into LaTeX notes.

### Critical Rule
**ONLY transcribe what the student dictates.** Do NOT invent content, add theorems, fill in proofs, or generate material beyond what the user provides. The only exceptions are:
- When the student explicitly says "fill in" or "clean up my logic"
- When the student asks for a diagram or reader's note
- Formatting/LaTeX conversion of dictated content

If the student says something like "New lecture: Topic", create the lecture file but do NOT fill in any content beyond the template. Wait for dictation.

### Interaction Style
- Be brief and efficient — the student is multitasking during a lecture
- Acknowledge input with short confirmations: "Got it, added to section 2.1"
- Don't ask unnecessary questions — infer structure from the content
- If something is ambiguous, make your best guess and note it: "I put this under the topology section — let me know if it belongs elsewhere"

### Input Formats You Accept
- Markdown with math shorthand: f: A -> B, x in A, A int B, A U B
- Incomplete sentences: "Def: countable if A~N"
- Verbal descriptions: "make a diagram showing..."
- Corrections: "clean up my logic", "fill in the definition of X"
- Structural commands: "new section: [name]", "make a note about X"

### Conversion Rules
| Input | LaTeX Output |
|-------|-------------|
| -> | \\to |
| A int B | A \\cap B |
| A U B | A \\cup B |
| x in A | x \\in A |
| A~B | A \\sim B |
| A^c | A^c |

### Workflow
1. If this is a new lecture (no current one started), call create_lecture() first
2. Read the current lecture file to see what's there
3. Append the student's dictation as properly formatted LaTeX
4. Write the updated file back
5. Confirm briefly

### What NOT to Do
- Never add content the student didn't provide
- Never compile unless the student asks
- Never reorganize existing content without being asked
- Don't verbose-explain what you're doing — just do it""",
```

### /Rev System Prompt — Review Mode

```python
    "rev": """## Mode: Review (/Rev)

You are in REVIEW MODE. The student wants to study and review material from their notebook.

### Interaction Style
- Active and engaging — ask questions, quiz the student, make connections
- Reference specific lectures and theorems by number
- When the student struggles, point them to relevant sections
- Generate study materials on request (summary sheets, practice problems)

### What You Can Do
- Quiz the student: "What's the formal definition of compactness?"
- Make connections: "This relates to the Heine-Borel theorem from Lecture 5"
- Create summaries: Use the lecturesummary and summarybox format
- Explain concepts: Use different angles, examples, and analogies
- Generate practice problems
- Compile notes to PDF when requested

### Workflow
1. Review the lecture summaries in the pre-loaded context to understand what's been covered
2. When the student asks about a specific topic, use read_file to load the full lecture
3. Quiz, explain, and connect concepts based on the notebook content
4. If the student asks for a PDF or study guide, compile or generate one

### What NOT to Do
- Don't just recite notes back — engage actively
- Don't overwhelm with content — focus on what the student asks about
- Don't generate new lecture content (that's /Lec mode)""",
```

### /Work System Prompt — Homework Mode

```python
    "work": """## Mode: Homework (/Work)

You are in HOMEWORK MODE. The student is working on an assignment.

### Critical Rule
**Guide, don't solve.** Only write what the student provides. If they give you an outline or verbal explanation for Part 1 of a proof, write up Part 1 only. Do NOT "helpfully" complete Part 2 on your own.

### Principles
1. Ask before extending to new parts of a problem
2. Guide with hints rather than full solutions:
   - "What property of supremum might be useful here?"
   - "Have you considered a proof by contradiction?"
   - "What does the definition of [concept] tell us?"
3. Verify understanding after writing up their solution
4. The struggle is part of learning

### Explainers
When the student is stuck, offer to create an explainer document:
- Visual TikZ diagrams illustrating key concepts
- High-school-level explanations of definitions
- Intuition behind the proof strategy
- NOT the actual solution

Create explainers at: hw/hwN/explainers/pM/explainerM.tex

### Workflow
1. Read assignment.txt to know the problems
2. Read the current submission .tex to see progress
3. Help the student work through problems one at a time
4. Write up ONLY what they provide
5. Stop after each part and ask if they're ready for the next

### What NOT to Do
- Never solve problems for the student
- Never generate proof content they haven't provided
- Never move to the next problem without checking
- Don't compile unless asked""",
```

### /Done System Prompt — Session Wrap-Up

```python
    "done": """## Mode: Session Wrap-Up (/Done)

The student is ending their study session. Summarize what was accomplished and create a session log.

### Tasks to Perform
1. Summarize the session — what was covered, what was created/modified
2. Call `create_session()` to create a .tex session log (this creates the subfile and adds it to sessions.tex automatically)
3. Suggest what to review next based on the material covered
4. If lecture notes were taken, offer to compile the master PDF

### create_session() Arguments
- `date`: Use YYYY-MM-DD format (e.g., "2026-02-06")
- `mode`: The primary mode used (e.g., "Review", "Lecture", "Homework")
- `summary`: 1-sentence session summary
- `topics`: Comma-separated topics covered
- `covered`: What was accomplished (one item per line, will become \\item entries)
- `next_steps`: Suggested next steps (one item per line, will become \\item entries)

### What NOT to Do
- Don't modify existing lecture content
- Don't create new content beyond the session log
- Keep the summary concise — 5-10 bullet points max
- Don't manually write session .tex files — use create_session() instead""",
```

### Default Mode (no command)

```python
    "default": """## Mode: General Chat

You are a helpful study companion. The student hasn't specified a mode, so be generally helpful with their coursework.

You can:
- Answer questions about course material (reference the notebook)
- Help navigate the notebook structure
- Compile notes if requested
- Suggest switching to a specific mode: "It sounds like you want to take lecture notes — try /Lec to start dictation mode"

Hint the student about available modes if they seem to be trying to do something specific:
- Taking notes → suggest /Lec
- Studying/reviewing → suggest /Rev
- Working on homework → suggest /Work
- Ending a session → suggest /Done""",
}
```

### Success Criteria
- Each mode prompt clearly defines the agent's behavior constraints
- /Lec prompt enforces dictation-only (no inventing content)
- /Work prompt enforces guide-don't-solve
- /Done prompt performs session wrap-up tasks
- Default mode suggests appropriate modes

---

## Step 5: Server Integration (`server.py` modifications)

### Changes to server.py

Replace the generic agent creation with mode-aware agent construction:

```python
# In chat_stream handler:

from youlearn.modes import detect_mode, build_system_prompt, MODE_PROMPTS
from youlearn.context import build_context
from youlearn.tools.notebook_tools import NotebookTools

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    async def generate() -> AsyncGenerator[dict[str, Any], None]:
        settings = get_settings()
        workspace = Path(settings.workspace)
        class_dir = workspace / settings.active_class  # e.g., classes/Math-104

        # 1. Detect mode from latest message
        latest = request.messages[-1].content if request.messages else ""
        mode = detect_mode(latest)

        # 2. Parse hw_id for /Work mode
        hw_id = None
        if mode.name == "work" and mode.user_message:
            # Try to extract hw identifier: "/Work hw2" -> "hw2"
            hw_match = re.match(r"(hw\d+)", mode.user_message.lower())
            if hw_match:
                hw_id = hw_match.group(1)

        # 3. Build context
        context = build_context(class_dir, mode.name, hw_id=hw_id)

        # 4. Build system prompt
        class_name = settings.active_class.replace("-", " ")  # "Math 104"
        system_prompt = build_system_prompt(mode.name, context, class_name)

        # 5. Create agent with NotebookTools
        agent = Agent(
            model=OpenRouter(
                id=settings.openrouter_model,
                api_key=settings.openrouter_api_key,
            ),
            tools=[NotebookTools(class_dir)],
            instructions=system_prompt,
            markdown=True,
        )

        # 6. Build the user prompt
        # Use mode.user_message (command stripped) for the current turn
        messages = request.messages
        if len(messages) <= 1:
            prompt = mode.user_message or "(session started)"
        else:
            history_parts = []
            for msg in messages[:-1]:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role_label}: {msg.content}")
            history = "\n\n".join(history_parts)
            prompt = f"Conversation so far:\n\n{history}\n\n---\n\nUser: {mode.user_message}"

        # ... rest of streaming logic unchanged ...
```

### Config Addition

```python
# config.py — add one field:
active_class: str = "Math-104"
```

### Success Criteria
- Sending `/Lec Today we covered X` creates an agent in lecture mode with lecture context loaded
- Sending a plain message creates an agent in default mode
- The system prompt includes both mode instructions AND pre-loaded context
- NotebookTools is the only toolkit (no more generic FileTools/ShellTools)

---

## Step 6: Compilation Strategy

### When to Compile
- **Never automatically** — compilation is expensive (~5-10s with pdflatex 3-pass)
- **On explicit request**: User says "compile", "show me the PDF", "build the notes"
- **During /Done**: Agent offers to compile after summarizing the session
- **NOT during /Lec**: Would slow down the dictation flow

### pdflatex + makeindex (proven toolchain)
Use the existing Math-104 Makefile approach: `pdflatex → makeindex → pdflatex`. This is already working and produces correct PDFs with:
- Table of contents
- Auto-generated Index of Definitions (from `\defn{}` + `\index{}`)
- All packages (tcolorbox, tikz, subfiles, amsthm)

The 3-pass build is needed because:
1. First `pdflatex` generates `.idx` file with index entries
2. `makeindex` processes `.idx` → `.ind` (sorted index)
3. Second `pdflatex` includes the generated index + resolves TOC page numbers

**Post-hackathon**: Can switch to tectonic for Docker deployment (smaller image, no TeX Live). Would need a makeindex workaround. Not worth the risk during a hackathon.

### PDF Delivery (stretch goal)
If time permits, the compile_notes tool can return the PDF as an OpenWebUI artifact:

```python
import base64

PDF_VIEWER_TEMPLATE = """<html>
<body style="margin:0;padding:0;">
<embed src="data:application/pdf;base64,{pdf_base64}"
       type="application/pdf" width="100%" height="100%"
       style="min-height:80vh;"/>
</body>
</html>"""

# In compile_notes, after successful compilation:
pdf_bytes = pdf_path.read_bytes()
pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
html = PDF_VIEWER_TEMPLATE.format(pdf_base64=pdf_b64)
return f"```html\n{html}\n```"
```

This renders the PDF inline in OpenWebUI's artifact viewer. Low priority for the hackathon but high demo impact.

---

## Implementation Order

This is the build order for a developer implementing this plan:

### Phase 1: Modes + Context (~30 min)
1. Create `backend/src/youlearn/tools/__init__.py` (empty)
2. Create `backend/src/youlearn/modes.py` with `detect_mode()` and all system prompt templates
3. Create `backend/src/youlearn/context.py` with `extract_lecture_metadata()`, `extract_preamble_commands()`, `discover_lectures()`, and `build_context()`
4. Test: manually call `build_context()` with each mode against Math-104 directory, verify output

### Phase 2: NotebookTools (~30 min)
5. Create `backend/src/youlearn/tools/notebook_tools.py` with all 6 tool functions
6. Test: manually call each tool function against Math-104 directory
7. Test `create_lecture(6, "February 7, 2026", "Sequences")` — verify file created and inserted before ADD_LECTURE_HERE marker
8. Test `create_session("2026-02-06", "Review", ...)` — verify session .tex created and sessions.tex updated

### Phase 3: Wire into Server (~15 min)
8. Add `active_class` to `config.py`
9. Modify `server.py` to use `detect_mode`, `build_context`, `build_system_prompt`, and `NotebookTools`
10. Remove `FileTools` and `ShellTools` imports

### Phase 4: End-to-End Test (~15 min)
11. Start backend, send `/Lec Today we're covering sequences` through the pipe
12. Verify agent creates lecture file and writes dictated content
13. Send `/Rev Quiz me on lecture 1` — verify agent references lec01 content
14. Send `/Work hw1` — verify agent loads assignment.txt and guides
15. Send `/Done` — verify agent creates session .tex via create_session() and updates sessions.tex
16. Send `Compile my notes` — verify pdflatex + makeindex produces PDF with all sections

---

## Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| `/Lec` with no content | Agent creates lecture file, waits for dictation |
| `/Work` with no hw specified | Agent lists available homework dirs, asks which one |
| `/Work hw99` (doesn't exist) | Agent reports hw99 not found, lists available ones |
| User sends plain message in middle of /Lec session | Still processes as default mode (mode is per-message, not sticky) |
| pdflatex not installed | compile_notes returns clear error message |
| Compilation fails (bad LaTeX) | Returns first 500 chars of stderr |
| Agent tries to read file outside class_dir | Path traversal check blocks it |
| `/Done` called twice same day | create_session returns error (session file already exists) |
| ADD_LECTURE_HERE marker missing | create_lecture returns warning, doesn't corrupt master.tex |
| ADD_SESSION_HERE marker missing | create_session still creates .tex file but warns about sessions.tex |

**Note on mode stickiness**: Modes are NOT sticky across messages. Each message is independently detected. This is simpler and avoids state management. If the student sends `/Lec` then just types content on the next message, the second message will be "default" mode. This is acceptable for the hackathon — the student can prefix with `/Lec` each message, or just use default mode and the agent will still be helpful. A stretch goal would be to persist mode in the chat session metadata.

---

## What's NOT in This Plan

- **Class creation**: The demo uses pre-existing Math-104. No scaffolding needed.
- **You.com integration**: Separate plan. The agent can use it in any mode.
- **Composio/Google Calendar**: Separate plan. Would be called during /Done.
- **Pipe modifications**: pipe.py is unchanged — it just forwards messages.
- **OpenWebUI changes**: None needed.
- **User/session management**: Hardcoded to Math-104 for the demo.
- **Sticky modes**: Mode is per-message, not per-session. Simplifies implementation.
