# Session Progress Agent — Implementation Plan

## Overview

A background agent that fires after `/Done` mode to maintain an evolving `progress.tex` file — a rich, narrative theory-of-mind document that reads like a tutor's introspective journal about the student's intellectual journey through the course. Not a checklist or tracker, but a living synthesis: where the student's understanding stands, how their thinking has evolved, what conceptual gaps remain, and where curiosity is pulling them next.

This gives the chat agent genuine statefulness — every mode reads `progress.tex` as context, so the AI companion *remembers* and *understands* the student across sessions.

## Current State Analysis

- **Session summaries exist** but are never loaded into context for `/Lec`, `/Rev`, `/Work`, or default modes. The agent has no memory between sessions.
- **Fact-check agent** (`factcheck.py`) provides the background-agent pattern: Agno agent, fires via `asyncio.create_task` after `/Done`, writes output to a file, `context.py` loads it for all modes.
- **`progress.tex` does not exist yet.** There is no progress tracking of any kind.

### Key Discoveries
- `server.py:159-167` — fact-check fires after `/Done` via `asyncio.create_task(run_fact_check(settings))`
- `context.py:293-296` — fact-check report appended to all modes at end of `build_context()`
- `notebook_tools.py:177-260` — `create_session()` writes `.tex` subfile + updates `sessions.tex`
- `master.tex:149-159` — Sessions section sits between Assignments and Resources
- `factcheck.py:94-108` — `_find_changed_lectures()` uses `st_mtime` to find files modified since last run

## Desired End State

A new `progress.tex` subfile appears in the compiled PDF as a "Student Progress" section between Assignments and Sessions. It reads as a rich narrative — a tutor's evolving assessment of the student's understanding, written in first-person plural ("We began by...", "The student has developed...").

After every `/Done` session, a background agent:
1. Reads the current `progress.tex`, all session summaries, and any `.tex` files edited during the session
2. Rewrites `progress.tex` as an updated narrative synthesis
3. The chat agent in all modes has this narrative in context, giving it a theory of mind about the student

### Verification
- `progress.tex` exists at `notes/latex/progress/progress.tex` and compiles as a subfile
- `master.tex` includes it between Assignments and Sessions
- After running `/Done`, `progress.tex` is updated with content reflecting the session
- All modes include the progress narrative in their context
- The narrative reads as a rich, introspective assessment — not a checklist

## What We're NOT Doing

- Not creating a separate JSON report (unlike fact-check — this writes `.tex` directly)
- Not tracking granular per-topic mastery scores or percentages
- Not building a database or structured data model — the narrative IS the data
- Not giving the progress agent tools to edit lecture files or any file other than `progress.tex`
- Not making the progress agent interactive — it runs silently in the background

## Implementation Approach

Follow the `factcheck.py` pattern closely: a single `progress.py` module with an async `run_progress_update()` function, an Agno agent with constrained tools, and a loader function for `context.py`. The agent writes LaTeX directly rather than JSON.

The key difference from fact-check: this agent has **write access** (scoped to `progress.tex` only) and produces a **narrative `.tex` file** rather than a structured report.

---

## Phase 1: Create `progress.tex` Template and Add to Master

### Overview
Set up the LaTeX subfile and integrate it into the notebook structure.

### Changes Required

#### 1. Create `notes/latex/progress/progress.tex`
**File**: `classes/Math-104/notes/latex/progress/progress.tex`

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Student Progress}

\begin{lecturesummary}
\textbf{Learning Journey:} This section is a living document maintained by the YouLearn AI companion. It synthesizes observations from study sessions, lecture notes, and homework to paint a picture of the student's evolving understanding of Real Analysis. Updated automatically after each study session.
\end{lecturesummary}

\subsection{Where We Are}

\textit{No sessions recorded yet. Begin a study session and end with \texttt{/Done} to start building your learning narrative.}

\end{document}
```

#### 2. Add `progress.tex` to `master.tex`
**File**: `classes/Math-104/notes/latex/master/master.tex`
**Changes**: Insert a `\subfile` for progress between the Assignments and Sessions sections.

Insert after line 153 (`\newpage` after assignments subfile), before the Sessions comment block:

```latex
%----------------------------------------------------------------------
% STUDENT PROGRESS
%----------------------------------------------------------------------
\subfile{../progress/progress}
\newpage
```

### Success Criteria

#### Automated Verification:
- [x] `progress.tex` exists at `classes/Math-104/notes/latex/progress/progress.tex`
- [x] `master.tex` includes `\subfile{../progress/progress}` between Assignments and Sessions
- [x] `cd classes/Math-104 && make` compiles successfully with the new section

#### Manual Verification:
- [ ] The compiled PDF shows "Student Progress" section between Assignments and Sessions
- [ ] The placeholder text renders correctly

---

## Phase 2: Create `progress.py` — The Background Agent

### Overview
Implement the progress agent module following the `factcheck.py` pattern. The agent reads session summaries, edited files, and existing progress, then rewrites `progress.tex` as a rich narrative.

### Changes Required

#### 1. Create `backend/src/youlearn/progress.py`
**File**: `backend/src/youlearn/progress.py`

```python
"""Background progress agent — maintains a narrative progress.tex file.

After each /Done session, reads session summaries and recently edited files,
then rewrites progress.tex as an evolving tutor's-journal-style narrative
about the student's intellectual journey through the course.
"""

from __future__ import annotations

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
    import json
    state_path = class_dir / _STATE_FILE
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {}


def _save_state(class_dir: Path, state: dict) -> None:
    import json
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
    # Look for content between \begin{document} and \end{document}
    import re
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

        # Ensure the output has the subfile wrapper
        if r"\documentclass" not in raw:
            # Agent forgot the wrapper — add it
            raw = (
                "\\documentclass[../master/master.tex]{subfiles}\n\n"
                "\\begin{document}\n\n"
                f"{raw}\n\n"
                "\\end{document}\n"
            )

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
```

### Design Decisions

**No tools for the agent**: Unlike fact-check (which needs `YouComSearchTools` to search the web), the progress agent is pure synthesis — all input is provided in the prompt, and the output is the complete `progress.tex` content. `tool_call_limit=0` enforces this.

**Full rewrite each time**: The agent receives the current `progress.tex` and rewrites it entirely. This avoids append-bloat and lets the narrative evolve organically — early sessions might warrant a paragraph, while after 20 sessions the document grows into a multi-page assessment.

**Edited files tracking**: Uses `st_mtime` timestamps (same as fact-check) via `.progress-state.json` to identify what changed during the session. Excludes session files (read separately) and `progress.tex` itself.

**LaTeX output directly**: The agent outputs raw LaTeX. A fallback wraps the output in subfile boilerplate if the agent forgets it.

### Success Criteria

#### Automated Verification:
- [x] `backend/src/youlearn/progress.py` exists and imports cleanly: `cd backend && .venv/bin/python -c "from youlearn.progress import run_progress_update, load_progress"`
- [x] No linting errors (ruff not installed, but syntax valid and imports clean)

#### Manual Verification:
- [ ] Review the `PROGRESS_INSTRUCTIONS` prompt — does the voice/tone guidance produce the right kind of narrative?

**Pause here for manual review of Phase 2 before continuing.**

---

## Phase 3: Wire into Server and Context

### Overview
Connect the progress agent to the `/Done` flow and load progress into all modes' context.

### Changes Required

#### 1. Trigger progress agent after `/Done`
**File**: `backend/src/youlearn/server.py`
**Changes**: Import `run_progress_update` and fire it after `/Done`, alongside (not after) the fact-check agent.

At the top, add import:
```python
from youlearn.progress import run_progress_update
```

In the `generate()` function, after the existing fact-check trigger block (line 159-167), add the progress agent trigger:

```python
            # Auto-trigger fact-check after /Done mode
            if mode.name == "done" and settings.you_api_key:
                asyncio.create_task(run_fact_check(settings))
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "status",
                        "content": "Fact-check agent started in background...",
                    }),
                }

            # Auto-trigger progress update after /Done mode
            if mode.name == "done":
                asyncio.create_task(run_progress_update(settings))
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "status",
                        "content": "Updating student progress narrative...",
                    }),
                }
```

Note: Progress agent fires unconditionally after `/Done` (no API key required, unlike fact-check).

#### 2. Load progress into context for all modes
**File**: `backend/src/youlearn/context.py`
**Changes**: Import `load_progress` and append it to the context parts, just like `load_fact_check_report`.

Add import at top:
```python
from youlearn.progress import load_progress
```

At the end of `build_context()`, after the fact-check report block (line 293-296), add:

```python
    # Append student progress narrative if available (all modes)
    progress = load_progress(class_dir)
    if progress:
        parts.append(progress)
```

#### 3. Add manual trigger endpoint (optional, mirrors fact-check)
**File**: `backend/src/youlearn/server.py`
**Changes**: Add a `POST /progress/trigger` endpoint for manual triggering.

```python
@app.post("/progress/trigger")
async def trigger_progress(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Manually trigger a progress narrative update."""
    settings = get_settings()
    background_tasks.add_task(run_progress_update, settings)
    return {"status": "progress update started"}
```

### Success Criteria

#### Automated Verification:
- [x] Server starts without errors: `cd backend && make server` (starts on :8200)
- [x] Health check passes: `curl http://localhost:8200/health`
- [x] Manual trigger works: `curl -X POST http://localhost:8200/progress/trigger`
- [x] Import chain works: `cd backend && .venv/bin/python -c "from youlearn.server import app"`

#### Manual Verification:
- [ ] Send a `/Done` message through the chat — verify both "Fact-check agent started" and "Updating student progress narrative" status messages appear
- [ ] After the progress agent completes, verify `progress.tex` has been updated
- [ ] Send a subsequent message in any mode — verify the progress narrative appears in the agent's context (check server logs or agent response referencing past sessions)
- [ ] Compile master PDF — verify the Student Progress section renders correctly

**Pause here for manual testing of the full flow before continuing.**

---

## Phase 4: Update System Prompts to Use Progress Context

### Overview
Update mode prompts so the agent knows to leverage the progress narrative when interacting with the student. The context is already injected (Phase 3), but the agent needs guidance on how to use it.

### Changes Required

#### 1. Update mode prompts
**File**: `backend/src/youlearn/modes.py`
**Changes**: Add a note to the `BASE_PROMPT` about the progress narrative, so all modes know it exists and how to use it.

Add to the end of `BASE_PROMPT` (before the closing `"""`), after the Rules section:

```python
### Student Progress
If a "Student Progress" narrative is included in the pre-loaded context, use it to:
- Remember what the student has worked on in previous sessions
- Understand their current level of mastery and areas of weakness
- Build on previous sessions rather than starting from scratch
- Reference their learning journey naturally: "Last time we worked on X, let's build on that"
- Adapt your teaching to their demonstrated understanding
```

### Success Criteria

#### Automated Verification:
- [x] `modes.py` imports cleanly: `cd backend && .venv/bin/python -c "from youlearn.modes import build_system_prompt"`

#### Manual Verification:
- [ ] After a `/Done` + progress update, start a new `/Rev` session — the agent should reference previous session topics naturally
- [ ] The agent's responses feel like it "remembers" the student

---

## Testing Strategy

### End-to-End Flow Test
1. Start the backend: `cd backend && make server`
2. Send a `/Lec` message with some content → agent creates/updates lecture notes
3. Send a `/Done` message → agent creates session summary, progress agent fires
4. Wait for background progress agent to complete (check logs)
5. Verify `progress.tex` was created/updated with narrative content
6. Send a `/Rev` message → agent's response should reference previous session
7. Compile master: `cd classes/Math-104 && make` → PDF includes Student Progress section

### Edge Cases
- First ever session (no existing `progress.tex`) — agent should write the "opening chapter"
- Multiple sessions in one day — sessions with same date prefix
- No files edited during session (pure chat) — agent still has sessions to synthesize
- Very long history (many sessions) — narrative should stay 1-3 pages, not grow unbounded

## Performance Considerations

- The progress agent is pure LLM generation (no tool calls), so it should complete in 10-30 seconds
- All session files are read and concatenated — for a semester with ~30 sessions, this is ~30KB of input, well within context limits
- The progress agent and fact-check agent run concurrently via separate `asyncio.create_task` calls — no blocking

## References

- Background agent pattern: `backend/src/youlearn/factcheck.py`
- Context loading: `backend/src/youlearn/context.py`
- Server wiring: `backend/src/youlearn/server.py`
- Session creation: `backend/src/youlearn/tools/notebook_tools.py:177-260`
- Master structure: `classes/Math-104/notes/latex/master/master.tex`
- Example session: `classes/Math-104/notes/latex/sessions/session-2026-02-06.tex`
