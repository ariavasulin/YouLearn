"""Background progress agent — maintains a narrative progress.tex file.

After each /Done session, reads session summaries and recently edited files,
then rewrites progress.tex as an evolving tutor's-journal-style narrative
about the student's intellectual journey through the course.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from youlearn.config import Settings, get_settings

log = structlog.get_logger()

_STATE_FILE = ".progress-state.json"

PROGRESS_INSTRUCTIONS = """\
You are a reflective, insightful tutor maintaining a living document about a student's
intellectual journey through a university Real Analysis course (Math 104).

## Your Task
You will receive:
1. The current progress.tex file (your previous narrative, or a placeholder if this is the first run)
2. All session summary .tex files (the student's study session logs)
3. Content of .tex files that were edited during the most recent session

Rewrite progress.tex as a rich, introspective narrative. This is NOT a checklist or tracker.
It reads like a thoughtful tutor's journal — part letter of recommendation, part learning
portfolio, part intellectual autobiography.

## Voice and Tone
- Write in first-person plural where natural ("We began by exploring...", "Our work on...")
  but shift to observational third-person for assessments ("The student has developed a
  remarkably intuitive grasp of...")
- Be genuinely reflective — note conceptual breakthroughs, evolving intuitions, productive
  struggles, and moments of connection between ideas
- Sound like a professor who deeply cares about this student's growth
- Be specific — reference actual theorems, definitions, proofs, and examples from the sessions
- Don't flatten complexity — if the student understands compactness intuitively but struggles
  with the formal epsilon-delta machinery, say exactly that

## Document Structure
Use these LaTeX sections (adapt as the narrative grows):

1. **\\subsection{Where We Are}** — A present-tense synthesis of the student's current
   understanding. What do they grasp deeply? What's still forming? Where is their intuition
   strong vs. where do they rely on mechanical procedure?

2. **\\subsection{The Journey So Far}** — An evolving narrative of how understanding has
   developed across sessions. Not a session-by-session log (that's what sessions.tex is for),
   but a thematic arc: "Early sessions focused on building comfort with the epsilon-delta
   formalism. By the third session, we saw a shift..."

3. **\\subsection{Edges of Understanding}** — Where the frontier is. What concepts are
   partially formed? What misconceptions surfaced? What questions has the student asked
   that reveal deep thinking (or gaps)?

4. **\\subsection{Looking Forward}** — What should come next, pedagogically. Not just
   "review Topic X" but a thoughtful recommendation: "The student's comfort with sequences
   suggests they're ready for series convergence tests, but we should first solidify the
   connection between sequential compactness and the Bolzano-Weierstrass theorem."

## LaTeX Formatting
- Use the standard environments: summarybox, notebox, lecturesummary
- Use \\defn{term} for key terms being tracked
- Use \\textit{} for the student's own words or paraphrased insights
- Keep the document compilable as a subfile of master.tex
- Start with: \\documentclass[../master/master.tex]{subfiles}
- Wrap content in \\begin{document} ... \\end{document}
- The \\section{Student Progress} and opening lecturesummary box should always be present

## Critical Rules
- REWRITE the entire progress.tex each time — this is a living document, not an append log
- Preserve the narrative arc from previous versions while incorporating new session data
- If this is the first real session, write the opening chapter of the narrative
- Be substantive — this should be 1-3 pages when compiled, not a paragraph
- Output ONLY the complete LaTeX content for progress.tex — no commentary outside the document
"""


def _load_state(class_dir: Path) -> dict:
    """Load the last-run state."""
    state_path = class_dir / _STATE_FILE
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {}


def _save_state(class_dir: Path, state: dict) -> None:
    state_path = class_dir / _STATE_FILE
    state_path.write_text(json.dumps(state, indent=2))


def _find_edited_files(class_dir: Path, since: float) -> list[Path]:
    """Find .tex files edited since `since` timestamp.

    Looks at lectures, homework, and other notebook content —
    but NOT sessions (those are read separately) and NOT progress.tex itself.
    """
    edited = []
    latex_dir = class_dir / "notes" / "latex"
    hw_dir = class_dir / "hw"

    # Check lecture files
    if latex_dir.exists():
        for d in sorted(latex_dir.iterdir()):
            if d.is_dir() and d.name.startswith("lec"):
                tex_file = d / f"{d.name}.tex"
                if tex_file.exists() and tex_file.stat().st_mtime > since:
                    edited.append(tex_file)

    # Check homework submissions
    if hw_dir.exists():
        for hw in sorted(hw_dir.iterdir()):
            if hw.is_dir():
                sub_dir = hw / "submission"
                if sub_dir.exists():
                    for f in sub_dir.iterdir():
                        if f.suffix == ".tex" and f.stat().st_mtime > since:
                            edited.append(f)

    return edited


def _read_all_sessions(class_dir: Path) -> str:
    """Read all session .tex files and concatenate them."""
    sessions_dir = class_dir / "notes" / "latex" / "sessions"
    if not sessions_dir.exists():
        return ""
    parts = []
    for f in sorted(sessions_dir.iterdir()):
        if f.name.startswith("session-") and f.suffix == ".tex":
            rel = str(f.relative_to(class_dir))
            content = f.read_text()
            parts.append(f"--- SESSION: {rel} ---\n{content}\n--- END ---")
    return "\n\n".join(parts)


def load_progress(class_dir: Path) -> str | None:
    """Load progress.tex content for injection into chat agent context.

    Returns the raw LaTeX content (minus the subfile boilerplate), or None.
    """
    progress_path = class_dir / "notes" / "latex" / "progress" / "progress.tex"
    if not progress_path.exists():
        return None
    content = progress_path.read_text()
    # Strip the subfile wrapper to get just the narrative content
    m = re.search(
        r"\\begin\{document\}(.*?)\\end\{document\}",
        content,
        re.DOTALL,
    )
    if m:
        body = m.group(1).strip()
        if body and "No sessions recorded yet" not in body:
            return f"### Student Progress (auto-maintained)\n\n{body}"
    return None


async def run_progress_update(settings: Settings | None = None) -> str:
    """Run the progress agent to update progress.tex.

    Reads all sessions, recently edited files, and current progress.tex,
    then rewrites progress.tex as a narrative synthesis.
    """
    if settings is None:
        settings = get_settings()

    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class
    progress_path = class_dir / "notes" / "latex" / "progress" / "progress.tex"

    # Load state to find files edited during this session
    state = _load_state(class_dir)
    last_run = state.get("last_run", 0)

    # Gather inputs
    current_progress = progress_path.read_text() if progress_path.exists() else "(no progress document yet)"
    all_sessions = _read_all_sessions(class_dir)
    edited_files = _find_edited_files(class_dir, last_run)

    if not all_sessions:
        log.info("progress_skipped", reason="no sessions exist yet")
        return "No sessions to synthesize."

    # Build the edited-files block
    edited_block = ""
    if edited_files:
        parts = []
        for f in edited_files:
            rel = str(f.relative_to(class_dir))
            content = f.read_text()
            parts.append(f"--- EDITED: {rel} ---\n{content}\n--- END ---")
        edited_block = "\n\n".join(parts)

    agent = Agent(
        name="ProgressWriter",
        model=OpenRouter(
            id=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
        ),
        instructions=PROGRESS_INSTRUCTIONS,
        markdown=False,
        tool_call_limit=0,  # No tools needed — pure generation
    )

    run_ts = time.time()

    prompt_parts = [
        "Update the student progress document based on all available information.\n",
        f"## Current progress.tex\n```latex\n{current_progress}\n```\n",
        f"## All Session Summaries\n{all_sessions}\n",
    ]
    if edited_block:
        prompt_parts.append(f"## Files Edited This Session\n{edited_block}\n")

    prompt = "\n".join(prompt_parts)

    try:
        response = await agent.arun(prompt)
        raw = response.content or ""

        if not raw.strip():
            log.warning("progress_empty_response")
            return "Progress agent returned empty response."

        # Strip markdown code fences if the LLM wrapped output in them
        raw = re.sub(r"^```(?:latex|tex)?\s*\n", "", raw.strip())
        raw = re.sub(r"\n```\s*$", "", raw.strip())

        # Ensure the output has the subfile wrapper
        if r"\documentclass" not in raw:
            raw = (
                "\\documentclass[../master/master.tex]{subfiles}\n\n"
                "\\begin{document}\n\n"
                f"{raw}\n\n"
                "\\end{document}\n"
            )

        # Ensure \end{document} is present (LLM may truncate)
        if r"\end{document}" not in raw:
            log.warning("progress_missing_end_document")
            raw += "\n\n\\end{document}\n"

        # Write progress.tex
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text(raw)

        # Update state
        _save_state(class_dir, {"last_run": run_ts})

        log.info(
            "progress_update_complete",
            sessions_read=len(list((class_dir / "notes" / "latex" / "sessions").glob("session-*.tex"))),
            edited_files=len(edited_files),
            output_size=len(raw),
        )
        return raw

    except Exception as e:
        log.exception("progress_update_error", error=str(e))
        return f"Progress update failed: {e}"
