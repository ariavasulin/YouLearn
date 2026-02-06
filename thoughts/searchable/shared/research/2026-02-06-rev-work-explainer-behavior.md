---
date: 2026-02-06T22:00:00-08:00
researcher: ARI
git_commit: 9e17458
branch: main
repository: YouLearn
topic: "How /Rev and /Work modes handle student questions and the explainer system"
tags: [research, codebase, rev-mode, work-mode, explainers, pedagogy]
status: complete
last_updated: 2026-02-06
last_updated_by: ARI
---

# Research: /Rev and /Work Mode Explainer Behavior

**Date**: 2026-02-06T22:00:00-08:00
**Researcher**: ARI
**Git Commit**: 9e17458
**Branch**: main
**Repository**: YouLearn

## Research Question

In `/Rev` and `/Work` modes — when a student asks for an explanation of a question/concept, how does the system currently handle it? What is the explainer infrastructure? How should the behavior work: brief description → offer in-depth explainer → check for existing explainers → generate new LaTeX document if needed?

## Summary

The system has **two distinct explanation paths** depending on mode:

1. **`/Rev` mode** — The system prompt tells the agent to "explain concepts using different angles, examples, and analogies" and to quiz actively. Context loaded includes lecture summaries, summaryboxes, and the glossary. There is **no explicit explainer-document workflow** in `/Rev` mode — the agent explains concepts conversationally and can read full lectures via `read_file()` for deeper detail. There is no current instruction to offer standalone explainer documents.

2. **`/Work` mode** — The system prompt explicitly instructs the agent to "offer to create an explainer document" when the student is stuck. The path is `hw/hwN/explainers/pM/explainerM.tex`. Context loading **already pre-loads all existing `.tex` explainer files** into the agent's context, so the agent can see what's already been generated. The agent has `write_file()` to create new ones.

The **existing explainer corpus** in `classes/Math-104/` contains 9 standalone LaTeX documents (4 for hw1, 5 for hw2), each with heavy TikZ diagrams, progressive concept building, and a pedagogical "no solutions" approach. These serve as the de facto pattern for what an agent-generated explainer should look like.

## Detailed Findings

### /Rev Mode: Current Explanation Behavior

**System prompt** (`modes.py:142-169`):
```
## Mode: Review (/Rev)
- Active and engaging — ask questions, quiz the student, make connections
- Reference specific lectures and theorems by number
- When the student struggles, point them to relevant sections
- Generate study materials on request (summary sheets, practice problems)
```

**What the agent CAN do in /Rev:**
- Quiz the student
- Make cross-lecture connections
- Explain concepts with different angles, examples, analogies
- Read full lecture content via `read_file()` tool
- Generate practice problems
- Compile notes to PDF on request

**What the agent does NOT currently do in /Rev:**
- Check for existing standalone explainer documents
- Offer to generate a dedicated LaTeX explainer document
- Follow a "brief answer → offer in-depth" interaction pattern

**Context loaded** (`context.py:214-224`):
- All lecture summaries (extracted from `lecturesummary` environments)
- All section summaryboxes (extracted from `summarybox` environments)
- Glossary content from `glossary/glossary.tex`
- Fact-check report (if available)
- Student progress narrative (if available)

### /Work Mode: Current Explanation Behavior

**System prompt** (`modes.py:170-206`):
```
## Mode: Homework (/Work)
### Critical Rule: Guide, don't solve.
### Explainers
When the student is stuck, offer to create an explainer document:
- Visual TikZ diagrams illustrating key concepts
- High-school-level explanations of definitions
- Intuition behind the proof strategy
- NOT the actual solution
Create explainers at: hw/hwN/explainers/pM/explainerM.tex
```

**What the agent CAN do in /Work:**
- Read assignment text and current submission
- Write up ONLY what the student provides
- Guide with hints (not solutions)
- Create explainer documents at `hw/hwN/explainers/pM/explainerM.tex`
- Reference lecture summaries loaded in context

**Context loaded** (`context.py:226-265`):
- Assignment text (`hw/{hw_id}/assignment.txt`)
- All `.tex` files in `hw/{hw_id}/submission/`
- **All `.tex` files in `hw/{hw_id}/explainers/`** — pre-loaded into context
- Assignments overview (`assignments/assignments.tex`)
- All lecture summaries
- Fact-check report and progress narrative

**Key detail**: Because explainers are pre-loaded in context (`context.py:245-254`), the agent already "sees" existing explainer documents and could reference them without calling `read_file()`.

### Existing Explainer Files

**Location**: `classes/Math-104/hw/{hwN}/explainers/{pN}/explainer{N}.tex`

| HW | Problem | File | Topic |
|----|---------|------|-------|
| hw1 | p1 | `explainer1.tex` + `.pdf` | Rudin 1.1 — Rationals and Irrationals |
| hw1 | p2 | `explainer2.tex` + `.pdf` | Rudin 1.5 — Infimum and Supremum Duality |
| hw1 | p3 | `explainer3.tex` + `.pdf` | Rudin 1.9 — Lexicographic Order on C |
| hw1 | p4 | `explainer4.tex` + `.pdf` | Rudin 1.18 — Orthogonal Vectors in R^k |
| hw2 | p1 | `explainer1.tex` + `.pdf` | Rudin 2.6 — Limit Points and Closure |
| hw2 | p2 | `explainer2.tex` + `.pdf` | Rudin 2.22 — Separable Metric Spaces |
| hw2 | p3 | `explainer3.tex` + `.pdf` | Rudin 2.27 — Condensation Points |
| hw2 | p4 | `explainer4.tex` + `.pdf` | Rudin 2.29 — Open Sets in R |
| hw2 | bonus | `explainer_bonus.tex` + `.pdf` | Kuratowski Closure-Complement Problem |

### Explainer Document Structure (Pattern)

All 9 explainers follow a consistent structure:

1. **Standalone LaTeX** — `\documentclass[12pt]{article}`, NOT subfiles pattern
2. **Packages**: `amsfonts`, `amssymb`, `amsmath`, `amsthm`, `geometry` (1in margins), `tikz`
3. **Header**: `\pagestyle{myheadings}` with `\markright{Explainer: [Topic]}`
4. **Content flow**:
   - Problem statement / "The Claim"
   - "What is X?" — intuitive definition with TikZ diagram
   - Building blocks — key properties/lemmas needed
   - Proof strategy — flowcharts or step-by-step visual
   - Geometric/visual intuition — number lines, coordinate planes
   - Summary — key takeaway box
5. **Visual design**: 3-8 TikZ diagrams per explainer, color-coded (blue=primary, red=elements, green=special, orange=derived)
6. **Pedagogy**: No solutions, no hints unless asked. Concepts build progressively.

### How Context Flows for Explainers

```
User sends: "/Work hw2"
  → detect_mode() returns Mode(name="work", user_message="hw2")
  → server.py extracts hw_id="hw2" via regex
  → build_context(class_dir, "work", hw_id="hw2")
    → Reads hw/hw2/assignment.txt
    → Reads hw/hw2/submission/*.tex
    → Reads hw/hw2/explainers/**/*.tex  ← ALL existing explainers pre-loaded
    → Reads assignments/assignments.tex
    → Formats all lecture summaries
  → System prompt = BASE_PROMPT + WORK_MODE_PROMPT + context
  → Agent has: NotebookTools (read_file, write_file, list_files, create_lecture, create_session, compile_notes)
```

### Gap Analysis: What Exists vs. Desired Behavior

**Desired flow** (from user's description):
1. Student asks for an explanation of a concept
2. Agent gives brief description (1-3 sentences)
3. Agent asks if student wants in-depth explainer
4. If yes: check if one already exists (in notebook or standalone)
5. If found: serve it
6. If not found: generate new LaTeX explainer document

**What currently exists**:
- `/Work` mode: The system prompt mentions explainers but doesn't enforce the "brief → offer → check → generate" flow. The agent is told to "offer to create an explainer" when student is stuck, but the interaction pattern isn't prescribed step-by-step.
- `/Rev` mode: No mention of standalone explainer documents at all. The agent explains conversationally.
- **Pre-loading**: In `/Work` mode, existing explainers ARE loaded in context, so the agent could reference them. But there's no explicit instruction to check for and serve existing ones before generating new ones.
- **Compilation**: Explainer PDFs exist alongside `.tex` files, but there's no dedicated `compile_explainer()` tool — the agent would need to use `compile_notes()` which is designed for lectures/master, or the student would need to compile externally.
- **No `create_explainer()` tool**: The agent creates explainers via raw `write_file()`, so there's no structured tool that enforces the naming convention or registers the explainer.

## Code References

- `backend/src/youlearn/modes.py:142-169` — /Rev mode system prompt
- `backend/src/youlearn/modes.py:170-206` — /Work mode system prompt (includes explainer instructions)
- `backend/src/youlearn/modes.py:187-193` — Explainer creation instructions in /Work prompt
- `backend/src/youlearn/context.py:214-224` — /Rev context loading (summaries + glossary)
- `backend/src/youlearn/context.py:226-265` — /Work context loading (assignment + submission + explainers)
- `backend/src/youlearn/context.py:245-254` — Explainer pre-loading loop
- `backend/src/youlearn/server.py:138-143` — hw_id extraction for /Work mode
- `backend/src/youlearn/server.py:146` — build_context() call
- `backend/src/youlearn/tools/notebook_tools.py:58-75` — write_file() tool (used for explainer creation)
- `classes/Math-104/hw/hw1/explainers/` — 4 existing explainers for hw1
- `classes/Math-104/hw/hw2/explainers/` — 5 existing explainers for hw2

## Historical Context (from thoughts/)

- `thoughts/shared/plans/agent-notebook-interaction.md` — Original plan defining explainer workflow in /Work mode, specifies `hw/hwN/explainers/pM/explainerM.tex` path pattern, defines "guide don't solve" pedagogy
- `thoughts/shared/research/2026-02-06-math104-notebook-structure.md` — Documents existing Math-104 explainer structure, proposes a `create_explainer()` tool function (not yet implemented)
- `thoughts/build-plan.md` — Original hackathon build plan defining mode behaviors

## Open Questions

1. Should `/Rev` mode also check for and serve standalone explainer documents, or should explainers remain `/Work`-only?
2. Should explainers created in `/Rev` mode live in a different location (e.g., `notes/latex/explainers/` rather than `hw/hwN/explainers/`)?
3. Should a dedicated `create_explainer()` tool be added to NotebookTools to enforce naming conventions and compilation?
4. How should explainer PDFs be served — via the existing `/pdf/{class}/{filename}` endpoint, or a dedicated route?
5. Should the "brief → offer in-depth → check existing → generate" flow be encoded in the system prompt only, or enforced via tool logic?
