"""Background fact-check agent for the LaTeX notebook.

Produces a report file at classes/{slug}/fact-check-report.json rather than
editing .tex files directly.  The report is loaded as context for the main
chat agent so the student (or agent) can decide what to act on.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from youlearn.config import Settings, get_settings
from youlearn.tools.youcom_tools import YouComSearchTools

log = structlog.get_logger()

# Path (relative to class_dir) where we store the report + state
_REPORT_FILE = "fact-check-report.json"
_STATE_FILE = ".fact-check-state.json"

FACT_CHECK_INSTRUCTIONS = """\
You are a fact-checking agent for a university-level LaTeX notebook on Real Analysis (Math 104).

## Your Job
You will be given the content of lecture .tex files that have been added or
edited since the last fact-check run.  Your job is to identify factual claims,
verify them via web search, and produce a structured report.

**You do NOT edit any files.**  You only output a report.

### Steps
1. Read through the provided lecture content carefully.
2. Identify factual claims that can be verified against web sources:
   - Historical attributions (e.g., "Hermite proved e is transcendental in 1873")
   - Named theorems (e.g., "Heine-Borel theorem", "Cauchy-Schwarz inequality")
   - Dates and people (e.g., "Cantor's diagonal argument", "Dedekind cuts")
   - Concrete examples with verifiable properties
3. For each claim, call search_web() with a specific, targeted query.
4. Produce your final answer as a JSON array — nothing else — where each
   element has these fields:
   - "file": the lecture filename (e.g., "notes/latex/lec03/lec03.tex")
   - "claim": the original text from the .tex file
   - "status": one of "correct", "incorrect", "unverified"
   - "correction": if incorrect, what it should say (null otherwise)
   - "source_url": URL of the most relevant source (null if unverified)
   - "explanation": brief explanation of the finding

## What NOT to Fact-Check
- Formal proofs (mathematical derivations, not factual claims)
- Pure definitions (these define the framework, not claims about the world)
- Theorem statements themselves (these are proved, not asserted as historical fact)
- LaTeX formatting or structure

## How to Search
- Use specific, targeted queries: "When did Lindemann prove pi is transcendental"
- Not vague queries: "math history"
- One claim per search query

## Output
Return ONLY a JSON array.  No markdown fences, no commentary outside the array.
Example:
[
  {
    "file": "notes/latex/lec03/lec03.tex",
    "claim": "Hermite proved e is transcendental in 1873",
    "status": "correct",
    "correction": null,
    "source_url": "https://en.wikipedia.org/wiki/Transcendental_number",
    "explanation": "Confirmed: Charles Hermite published the proof in 1873."
  }
]
"""


def _load_state(class_dir: Path) -> dict:
    """Load the last-run state (timestamp of previous run)."""
    state_path = class_dir / _STATE_FILE
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {}


def _save_state(class_dir: Path, state: dict) -> None:
    state_path = class_dir / _STATE_FILE
    state_path.write_text(json.dumps(state, indent=2))


def _find_changed_lectures(class_dir: Path, since: float) -> list[Path]:
    """Find lecture .tex files modified after `since` (unix timestamp).

    If since is 0, returns all lectures.
    """
    latex_dir = class_dir / "notes" / "latex"
    changed = []
    if not latex_dir.exists():
        return changed
    for d in sorted(latex_dir.iterdir()):
        if d.is_dir() and d.name.startswith("lec"):
            tex_file = d / f"{d.name}.tex"
            if tex_file.exists() and tex_file.stat().st_mtime > since:
                changed.append(tex_file)
    return changed


def load_fact_check_report(class_dir: Path) -> str | None:
    """Load the fact-check report for injection into chat agent context.

    Returns a formatted string, or None if no report exists.
    """
    report_path = class_dir / _REPORT_FILE
    if not report_path.exists():
        return None
    try:
        data = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    findings = data.get("findings", [])
    if not findings:
        return None

    lines = ["### Fact-Check Report (auto-generated)"]
    lines.append(f"_Last run: checked {len(findings)} claim(s)_\n")

    for f in findings:
        status = f.get("status", "?")
        icon = {"correct": "OK", "incorrect": "ISSUE", "unverified": "?"}.get(status, "?")
        lines.append(f"**[{icon}]** `{f.get('file', '?')}` — {f.get('claim', '?')}")
        if status == "incorrect":
            lines.append(f"  Suggested correction: {f.get('correction', '?')}")
            lines.append(f"  Source: {f.get('source_url', '?')}")
        if f.get("explanation"):
            lines.append(f"  {f['explanation']}")
        lines.append("")

    return "\n".join(lines)


async def run_fact_check(settings: Settings | None = None) -> str:
    """Run a fact-check pass on recently changed lectures.

    Writes the report to classes/{slug}/fact-check-report.json.
    Returns the agent's raw response.
    """
    if settings is None:
        settings = get_settings()

    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class

    # Determine what changed since last run
    state = _load_state(class_dir)
    last_run = state.get("last_run", 0)
    changed = _find_changed_lectures(class_dir, last_run)

    if not changed:
        log.info("fact_check_skipped", reason="no lectures changed since last run")
        return "No lectures changed since last fact-check."

    # Read the changed lecture content
    lecture_content_parts = []
    for lec_path in changed:
        rel = str(lec_path.relative_to(class_dir))
        content = lec_path.read_text()
        lecture_content_parts.append(
            f"--- FILE: {rel} ---\n{content}\n--- END FILE ---"
        )
    lecture_block = "\n\n".join(lecture_content_parts)

    agent = Agent(
        name="FactChecker",
        model=OpenRouter(
            id=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
        ),
        tools=[YouComSearchTools(api_key=settings.you_api_key)],
        instructions=FACT_CHECK_INSTRUCTIONS,
        markdown=False,
        tool_call_limit=30,
    )

    run_ts = time.time()

    try:
        response = await agent.arun(
            f"Fact-check the following lecture files. They have been added or "
            f"edited since the last run.\n\n{lecture_block}"
        )
        raw = response.content or "[]"

        # Try to parse the agent's JSON output
        try:
            findings = json.loads(raw)
            if not isinstance(findings, list):
                findings = []
        except json.JSONDecodeError:
            # Agent may have wrapped in markdown fences — try to extract
            import re
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                try:
                    findings = json.loads(m.group())
                except json.JSONDecodeError:
                    findings = []
            else:
                findings = []

        # Write report
        report_data = {
            "timestamp": run_ts,
            "files_checked": [str(p.relative_to(class_dir)) for p in changed],
            "findings": findings,
        }
        report_path = class_dir / _REPORT_FILE
        report_path.write_text(json.dumps(report_data, indent=2))

        # Update state
        _save_state(class_dir, {"last_run": run_ts})

        log.info(
            "fact_check_complete",
            files_checked=len(changed),
            findings=len(findings),
        )
        return raw

    except Exception as e:
        log.exception("fact_check_error", error=str(e))
        return f"Fact-check failed: {e}"
