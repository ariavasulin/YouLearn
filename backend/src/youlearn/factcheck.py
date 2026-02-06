"""Background fact-check agent for the LaTeX notebook."""

from __future__ import annotations

from pathlib import Path

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from youlearn.config import Settings, get_settings
from youlearn.tools.notebook_tools import NotebookTools
from youlearn.tools.youcom_tools import YouComSearchTools

log = structlog.get_logger()

FACT_CHECK_INSTRUCTIONS = """\
You are a fact-checking agent for a university-level LaTeX notebook on Real Analysis (Math 104).

## Your Job
1. Call list_files("notes/latex") to find all lecture directories
2. For each lecture (lec01, lec02, ...), call read_file("notes/latex/lecXX/lecXX.tex")
3. Identify factual claims that can be verified against web sources:
   - Historical attributions (e.g., "Hermite proved e is transcendental in 1873")
   - Named theorems (e.g., "Heine-Borel theorem", "Cauchy-Schwarz inequality")
   - Dates and people (e.g., "Cantor's diagonal argument", "Dedekind cuts")
   - Concrete examples with verifiable properties
4. For each claim, call search_web() with a specific query to verify it
5. If a claim is WRONG, fix it in the .tex file:
   - Read the full file with read_file()
   - Make the correction
   - Add a LaTeX comment on the line above: % FACT-CHECK: corrected "old" to "new" (source: URL)
   - Write the corrected file with write_file()
6. After checking all lectures, provide a summary report

## What NOT to Fact-Check
- Formal proofs (mathematical derivations, not factual claims)
- Pure definitions (these define the framework, they aren't claims about the world)
- Theorem statements themselves (these are proved, not asserted as historical fact)
- LaTeX formatting or structure

## How to Search
- Use specific, targeted queries: "When did Lindemann prove pi is transcendental"
- Not vague queries: "math history"
- One claim per search query

## How to Correct
- Only change factual errors (wrong dates, wrong names, wrong attributions)
- Do NOT change mathematical content, proofs, or formatting
- Do NOT add new content — only fix errors in existing content
- Preserve the exact LaTeX formatting around the correction
- Always add a % FACT-CHECK comment so the student can see what changed

## Output Format
After checking, provide a brief report:
- Total claims checked
- Claims verified as correct (with lecture references)
- Claims corrected (with before/after and source URL)
- Claims that couldn't be verified (ambiguous or no results)
"""


async def run_fact_check(settings: Settings | None = None) -> str:
    """Run a single fact-check pass on the notebook. Returns the agent's report."""
    if settings is None:
        settings = get_settings()

    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class

    agent = Agent(
        name="FactChecker",
        model=OpenRouter(
            id=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
        ),
        tools=[
            YouComSearchTools(api_key=settings.you_api_key),
            NotebookTools(class_dir),
        ],
        instructions=FACT_CHECK_INSTRUCTIONS,
        markdown=True,
        tool_call_limit=30,
    )

    try:
        response = await agent.arun(
            "Fact-check the lecture notes in this notebook. "
            "List the lectures, read each one, identify verifiable factual claims, "
            "search the web to verify them, and fix any errors you find."
        )
        report = response.content or "(no report generated)"
        log.info("fact_check_complete", report=report[:500])
        return report
    except Exception as e:
        log.exception("fact_check_error", error=str(e))
        return f"Fact-check failed: {e}"
