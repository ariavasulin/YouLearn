# Create Explainer Tool & Update Rev/Work Mode Prompts

## Overview

Add a `create_explainer()` tool to `NotebookTools` and update `/Rev` and `/Work` mode system prompts so both modes follow the "brief description → offer in-depth → check for existing explainer → serve or generate new LaTeX document" interaction pattern.

## Current State Analysis

### What exists:
- **`/Work` mode** (`modes.py:170-206`): System prompt mentions explainers but doesn't prescribe a step-by-step interaction flow. Agent creates explainers via raw `write_file()`.
- **`/Rev` mode** (`modes.py:142-169`): No mention of standalone explainer documents. Agent explains conversationally only.
- **`context.py:245-254`**: In `/Work` mode, all `.tex` explainer files from `hw/{hwN}/explainers/` are pre-loaded into context.
- **`context.py:214-224`**: In `/Rev` mode, only lecture summaries + summaryboxes + glossary are loaded. No explainers.
- **9 existing explainers** in `classes/Math-104/hw/hw{1,2}/explainers/` — standalone LaTeX with TikZ diagrams, following a consistent pattern.
- **No `create_explainer()` tool** — agent uses `write_file()` directly.
- **No concept explainer directory** — all explainers are homework-problem-specific.

### Key Discoveries:
- Existing explainers are **standalone** (`\documentclass[12pt]{article}`), not subfiles — `hw/hw1/explainers/p1/explainer1.tex:1`
- Naming convention: `hw/hwN/explainers/pM/explainerM.tex` for homework, `hw/hwN/explainers/bonus/explainer_bonus.tex` for bonus — `classes/Math-104/hw/CLAUDE.md:59-60`
- Each explainer has both `.tex` source and compiled `.pdf` in the same directory
- Compilation uses pdflatex (single-pass, no makeindex needed for standalone docs)
- PDF serving copies to class root and uses `/pdf/{class}/{filename}` endpoint — `notebook_tools.py:331-353`
- The `hw/CLAUDE.md` documents the explainer workflow for homework mode

## Desired End State

After implementation:

1. **New tool**: `create_explainer(title, topic_slug, content, hw_id=None, problem_id=None)` in `NotebookTools`
   - Creates standalone LaTeX explainer document
   - Compiles to PDF automatically
   - Returns download link via `/pdf/` endpoint
   - Works for both homework explainers (`hw/hwN/explainers/pM/`) and concept explainers (`notes/latex/explainers/{slug}/`)

2. **`/Rev` mode**: System prompt instructs agent to follow the brief→offer→check→generate flow. Context includes existing concept explainers.

3. **`/Work` mode**: System prompt updated to use the same interaction flow and to prefer `create_explainer()` over `write_file()`.

4. **Verification**: Agent in `/Rev` mode can reference existing explainer, generate new concept explainer, and return PDF link. Agent in `/Work` mode can create homework-specific explainer via the new tool.

## What We're NOT Doing

- Not adding explainers to the compiled master notebook (they stay standalone)
- Not changing the existing hw explainer directory structure
- Not adding a `compile_explainer()` as a separate tool (compilation is built into `create_explainer()`)
- Not modifying the PDF serving endpoint (it already works for any PDF in the class root)
- Not changing the existing 9 demo explainers

## Implementation Approach

The tool handles two paths based on whether `hw_id` is provided:
- **Homework explainer**: `hw/{hw_id}/explainers/{problem_id}/{filename}.tex`
- **Concept explainer**: `notes/latex/explainers/{topic_slug}/explainer.tex`

Both produce standalone LaTeX documents following the established pattern. The system prompt changes are purely text — no server.py or context wiring changes needed beyond adding concept explainer loading to `/Rev` context.

---

## Phase 1: Add `create_explainer()` Tool to NotebookTools

### Overview
Add a new tool method that creates, writes, and compiles standalone LaTeX explainer documents.

### Changes Required:

#### 1. `backend/src/youlearn/tools/notebook_tools.py`

**Add `create_explainer` to the tools list in `__init__`:**

```python
tools = [
    self.read_file,
    self.write_file,
    self.list_files,
    self.create_lecture,
    self.create_session,
    self.compile_notes,
    self.create_explainer,  # NEW
]
```

**Add the `create_explainer` method** (after `create_session`, before `compile_notes`):

```python
def create_explainer(
    self,
    title: str,
    topic_slug: str,
    content: str,
    hw_id: str | None = None,
    problem_id: str | None = None,
) -> str:
    """Create a standalone LaTeX explainer document and compile it to PDF.

    Explainers are visual concept guides with TikZ diagrams that help students
    understand concepts without giving away solutions. They are standalone
    documents (not part of the master notebook).

    There are two types:
    - **Homework explainers**: Tied to a specific homework problem.
      Set hw_id="hw1" and problem_id="p1" to create at hw/hw1/explainers/p1/
    - **Concept explainers**: General concept guides for review.
      Omit hw_id to create at notes/latex/explainers/{topic_slug}/

    The content should be the LaTeX body (everything between \\begin{document}
    and \\end{document}). The tool wraps it in the standard explainer preamble
    with amsmath, tikz, etc.

    Args:
        title: Display title for the explainer (e.g., "Compactness in Metric Spaces")
        topic_slug: Short kebab-case identifier (e.g., "compactness", "rudin-1-1").
                    Used in the filename and page header.
        content: LaTeX body content (sections, TikZ diagrams, etc.)
        hw_id: Homework ID (e.g., "hw1") — set for homework explainers, omit for concepts.
        problem_id: Problem ID (e.g., "p1", "bonus") — required if hw_id is set.

    Returns:
        Success message with PDF download link, or error details.
    """
    # Determine output path
    if hw_id:
        if not problem_id:
            return "Error: problem_id is required when hw_id is set"
        explainer_dir = self.class_dir / "hw" / hw_id / "explainers" / problem_id
        filename = f"explainer_{topic_slug}"
    else:
        explainer_dir = self.class_dir / "notes" / "latex" / "explainers" / topic_slug
        filename = "explainer"

    tex_path = explainer_dir / f"{filename}.tex"

    # Safety check
    resolved = tex_path.resolve()
    if not str(resolved).startswith(str(self.class_dir)):
        return "Error: path escapes notebook directory"

    if tex_path.exists():
        return f"Error: explainer already exists at {tex_path.relative_to(self.class_dir)}"

    # Build the full document
    document = f"""\\documentclass[12pt]{{article}}
\\usepackage{{amsfonts, amssymb, amsmath, amsthm}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{tikz}}
\\usetikzlibrary{{patterns, decorations.pathreplacing, arrows.meta, calc}}

\\pagestyle{{myheadings}}
\\markright{{Explainer: {title}\\hfill}}

\\newcommand{{\\R}}{{\\mathbb{{R}}}}
\\newcommand{{\\Q}}{{\\mathbb{{Q}}}}
\\newcommand{{\\N}}{{\\mathbb{{N}}}}
\\newcommand{{\\Z}}{{\\mathbb{{Z}}}}
\\newcommand{{\\C}}{{\\mathbb{{C}}}}
\\newcommand{{\\eps}}{{\\varepsilon}}

\\begin{{document}}

\\begin{{center}}
    \\textbf{{\\Large {title}}}\\\\[0.5em]
    \\large A visual concept guide
\\end{{center}}

{content}

\\end{{document}}
"""

    # Write the file
    explainer_dir.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(document)

    # Compile to PDF (single-pass, no makeindex needed)
    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(explainer_dir),
        )
        if result.returncode != 0:
            output = result.stdout or result.stderr or "(no output)"
            err_lines = [l for l in output.splitlines() if l.startswith("!")]
            detail = "\n".join(err_lines) if err_lines else output[-500:]
            return (
                f"Created {tex_path.relative_to(self.class_dir)} but compilation failed:\n{detail}"
            )
    except FileNotFoundError:
        return f"Created {tex_path.relative_to(self.class_dir)} but pdflatex not installed."
    except subprocess.TimeoutExpired:
        return f"Created {tex_path.relative_to(self.class_dir)} but compilation timed out."

    # Copy PDF to class root for serving
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        return f"Created {tex_path.relative_to(self.class_dir)} but PDF not generated."

    pdf_name = f"{filename}.pdf"
    root_pdf = self.class_dir / pdf_name
    shutil.copy2(pdf_path, root_pdf)
    download_url = f"{self.backend_url}/pdf/{self.class_slug}/{pdf_name}"

    rel_path = tex_path.relative_to(self.class_dir)
    return f"Created explainer: {rel_path}\nPDF: {download_url}"
```

**Add `import subprocess` and `import shutil`** — these are already imported at the top of the file, so no change needed.

### Success Criteria:

#### Automated Verification:
- [ ] Backend starts without errors: `cd backend && PYTHONPATH=src .venv/bin/python -c "from youlearn.tools.notebook_tools import NotebookTools; print('OK')"`
- [ ] NotebookTools has 7 tools (was 6): `cd backend && PYTHONPATH=src .venv/bin/python -c "from youlearn.tools.notebook_tools import NotebookTools; from pathlib import Path; t = NotebookTools(Path('.')); print(len(t.tools))"`

#### Manual Verification:
- [ ] Call `create_explainer(title="Test", topic_slug="test", content="\\section{Hello}\\nTest content.")` and verify it creates `notes/latex/explainers/test/explainer.tex` with correct preamble
- [ ] Call with `hw_id="hw1", problem_id="p5"` and verify it creates at `hw/hw1/explainers/p5/explainer_test.tex`
- [ ] Verify PDF compilation succeeds and download URL works

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation before proceeding.

---

## Phase 2: Update `/Rev` Mode — Prompt and Context Loading

### Overview
Add the "brief → offer → check → generate" interaction pattern to `/Rev` mode and load existing concept explainers into context.

### Changes Required:

#### 1. `backend/src/youlearn/context.py` — Load concept explainers for `/Rev` mode

**Add a helper function** (after `_list_hw_dirs`):

```python
def _load_concept_explainers(class_dir: Path) -> str:
    """Load existing concept explainers from notes/latex/explainers/."""
    explainers_dir = class_dir / "notes" / "latex" / "explainers"
    if not explainers_dir.exists():
        return ""
    parts = ["### Concept Explainers"]
    for edir in sorted(explainers_dir.iterdir()):
        if edir.is_dir():
            for f in sorted(edir.iterdir()):
                if f.suffix == ".tex":
                    parts.append(
                        f"**Explainer: {edir.name}**\n```latex\n{f.read_text()}\n```"
                    )
    if len(parts) == 1:
        return ""
    return "\n\n".join(parts)


def _list_hw_explainers(class_dir: Path) -> str:
    """List all homework explainer files (names only, not content)."""
    hw_dir = class_dir / "hw"
    if not hw_dir.exists():
        return ""
    lines = ["### Homework Explainers"]
    found = False
    for hdir in sorted(hw_dir.iterdir()):
        if hdir.is_dir() and hdir.name.startswith("hw"):
            exp_dir = hdir / "explainers"
            if exp_dir.exists():
                for pdir in sorted(exp_dir.iterdir()):
                    if pdir.is_dir():
                        for f in sorted(pdir.iterdir()):
                            if f.suffix == ".tex":
                                lines.append(f"- {hdir.name}/{pdir.name}/{f.name}")
                                found = True
    if not found:
        return ""
    return "\n".join(lines)
```

**Update the `elif mode == "rev":` block** in `build_context()` — add after glossary loading:

```python
elif mode == "rev":
    # 1. All lecture summaries
    parts.append(_format_lecture_summaries(all_meta))

    # 2. Section summaryboxes
    parts.append(_format_summaryboxes(all_meta))

    # 3. Glossary
    glossary = _read_safe(latex_dir / "glossary" / "glossary.tex")
    if glossary:
        parts.append("### Glossary\n```latex\n" + glossary + "\n```")

    # 4. Concept explainers (full content)
    concept_explainers = _load_concept_explainers(class_dir)
    if concept_explainers:
        parts.append(concept_explainers)

    # 5. Homework explainer index (names only, so agent knows what exists)
    hw_explainers = _list_hw_explainers(class_dir)
    if hw_explainers:
        parts.append(hw_explainers)
```

#### 2. `backend/src/youlearn/modes.py` — Update `/Rev` system prompt

**Replace the `"rev"` entry** in `MODE_PROMPTS`:

```python
"rev": """## Mode: Review (/Rev)

You are in REVIEW MODE. The student wants to study and review material from their notebook.

### Interaction Style
- Active and engaging — ask questions, quiz the student, make connections
- Reference specific lectures and theorems by number
- When the student struggles, point them to relevant sections
- Generate study materials on request (summary sheets, practice problems)

### Explaining Concepts
When the student asks for an explanation of a question or concept, follow this flow:

1. **Brief description first** — Give a 1-3 sentence overview of the concept
2. **Offer in-depth explainer** — Ask: "Would you like me to create a visual explainer document for this?"
3. **If yes, check for existing explainers:**
   - Check the pre-loaded concept explainers and homework explainer index in your context
   - If one exists, reference it and provide the key insights. Use `read_file()` to load homework explainers if needed.
   - If one already exists, do NOT create a duplicate — serve the existing one
4. **If no existing explainer, generate one:**
   - Use `create_explainer(title, topic_slug, content)` to create a new concept explainer
   - Structure: header describing the concept → introduce building blocks one by one → build to the full picture
   - Include TikZ diagrams for visual intuition
   - Do NOT provide solutions or hints unless the student asks

### What You Can Do
- Quiz the student: "What's the formal definition of compactness?"
- Make connections: "This relates to the Heine-Borel theorem from Lecture 5"
- Create summaries: Use the lecturesummary and summarybox format
- Explain concepts using the flow above
- Generate practice problems
- Compile notes to PDF when requested
- Create standalone visual explainer documents

### Workflow
1. Review the lecture summaries in the pre-loaded context to understand what's been covered
2. When the student asks about a specific topic, use read_file to load the full lecture
3. Quiz, explain, and connect concepts based on the notebook content
4. For in-depth explanations, follow the Explaining Concepts flow above

### What NOT to Do
- Don't just recite notes back — engage actively
- Don't overwhelm with content — focus on what the student asks about
- Don't generate new lecture content (that's /Lec mode)
- Don't create an explainer without asking the student first
- Don't create a duplicate explainer if one already exists""",
```

### Success Criteria:

#### Automated Verification:
- [ ] Backend starts without errors: `cd backend && PYTHONPATH=src .venv/bin/python -c "from youlearn.context import build_context; print('OK')"`
- [ ] Context building works: `cd backend && PYTHONPATH=src .venv/bin/python -c "from youlearn.context import build_context; from pathlib import Path; c = build_context(Path('../classes/Math-104'), 'rev'); print('concept_explainers' if 'Concept Explainers' in c else 'no_concept_explainers', len(c))"`

#### Manual Verification:
- [ ] In `/Rev` mode, agent receives concept explainers in context
- [ ] In `/Rev` mode, agent receives homework explainer file listing
- [ ] System prompt includes the "brief → offer → check → generate" flow instructions

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation before proceeding.

---

## Phase 3: Update `/Work` Mode Prompt

### Overview
Update `/Work` mode system prompt to follow the same interaction pattern and prefer `create_explainer()` over `write_file()`.

### Changes Required:

#### 1. `backend/src/youlearn/modes.py` — Update `/Work` system prompt

**Replace the `"work"` entry** in `MODE_PROMPTS`:

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

### Explaining Concepts
When the student asks for an explanation of a question or concept, follow this flow:

1. **Brief description first** — Give a 1-3 sentence overview of the concept
2. **Offer in-depth explainer** — Ask: "Would you like me to create a visual explainer for this?"
3. **If yes, check for existing explainers:**
   - Check the pre-loaded explainers in your context (they are already loaded for this homework)
   - If one exists, reference it and walk the student through the key ideas
   - If one already exists, do NOT create a duplicate — serve the existing one
4. **If no existing explainer, generate one:**
   - Use `create_explainer(title, topic_slug, content, hw_id="hwN", problem_id="pM")` for problem-specific explainers
   - Use `create_explainer(title, topic_slug, content)` for general concept explainers
   - Structure: header describing the problem → introduce concepts one by one → build to the full picture
   - Include TikZ diagrams for visual intuition
   - Do NOT provide solutions or hints unless the student explicitly asks

### Workflow
1. Read assignment.txt to know the problems
2. Read the current submission .tex to see progress
3. Help the student work through problems one at a time
4. Write up ONLY what they provide
5. Stop after each part and ask if they're ready for the next
6. When they need conceptual help, follow the Explaining Concepts flow

### What NOT to Do
- Never solve problems for the student
- Never generate proof content they haven't provided
- Never move to the next problem without checking
- Don't compile unless asked
- Don't create an explainer without asking the student first
- Don't create a duplicate explainer if one already exists""",
```

#### 2. `backend/src/youlearn/modes.py` — Update BASE_PROMPT tools list

**Update the Tools section** in `BASE_PROMPT` to include `create_explainer`:

Replace this in `BASE_PROMPT`:
```
### Tools
You have access to notebook tools:
- `read_file(path)` — Read any file in the notebook
- `write_file(path, content)` — Write/update any file
- `list_files(subdir)` — List files in a directory
- `create_lecture(num, date, topic)` — Create a new lecture from template, add to master.tex
- `create_session(date, mode, summary, topics, covered, next_steps)` — Create a session log .tex subfile
- `compile_notes(target)` — Compile to PDF using pdflatex + makeindex ("master" or "lecXX")
```

With:
```
### Tools
You have access to notebook tools:
- `read_file(path)` — Read any file in the notebook
- `write_file(path, content)` — Write/update any file
- `list_files(subdir)` — List files in a directory
- `create_lecture(num, date, topic)` — Create a new lecture from template, add to master.tex
- `create_session(date, mode, summary, topics, covered, next_steps)` — Create a session log .tex subfile
- `create_explainer(title, topic_slug, content, hw_id=None, problem_id=None)` — Create a standalone visual explainer document with TikZ diagrams, compiled to PDF. Use hw_id/problem_id for homework explainers, omit for general concept explainers.
- `compile_notes(target)` — Compile to PDF using pdflatex + makeindex ("master" or "lecXX")
```

### Success Criteria:

#### Automated Verification:
- [ ] Backend starts without errors: `cd backend && make server` (then Ctrl+C)
- [ ] All imports resolve: `cd backend && PYTHONPATH=src .venv/bin/python -c "from youlearn.modes import MODE_PROMPTS, BASE_PROMPT; assert 'create_explainer' in BASE_PROMPT; assert 'create_explainer' in MODE_PROMPTS['work']; assert 'create_explainer' in MODE_PROMPTS['rev']; print('OK')"`

#### Manual Verification:
- [ ] In `/Work` mode, agent follows the "brief → offer → check → generate" flow when student asks for an explanation
- [ ] In `/Work` mode, agent uses `create_explainer()` instead of raw `write_file()` for explainers
- [ ] In `/Rev` mode, agent follows the same interaction pattern
- [ ] Explainer PDFs compile and are accessible via `/pdf/` endpoint

**Implementation Note**: This is the final phase. After all automated verification passes, do full end-to-end manual testing.

---

## Testing Strategy

### Unit Tests:
- Verify `create_explainer()` creates correct file at concept path
- Verify `create_explainer()` creates correct file at homework path
- Verify error on missing `problem_id` when `hw_id` set
- Verify error on duplicate explainer
- Verify path traversal protection

### Integration Tests:
- Full `/Rev` flow: send concept question → agent gives brief → agent offers explainer → agent creates via tool → PDF accessible
- Full `/Work` flow: send `/Work hw1` → ask about a problem → agent finds existing explainer in context → references it

### Manual Testing Steps:
1. Start backend, send `/Rev What is compactness?` — verify agent gives brief answer and offers explainer
2. Accept the offer — verify agent calls `create_explainer()` (not `write_file()`)
3. Verify PDF link works in browser
4. Ask the same question again — verify agent references existing explainer instead of creating duplicate
5. Send `/Work hw1` then ask "explain Rudin 1.1" — verify agent references the existing `explainer1.tex` from context
6. Send `/Work hw1` then ask about a concept with no explainer — verify agent creates one via `create_explainer()`

## References

- Research document: `thoughts/shared/research/2026-02-06-rev-work-explainer-behavior.md`
- Existing explainer pattern: `classes/Math-104/hw/hw1/explainers/p1/explainer1.tex`
- NotebookTools: `backend/src/youlearn/tools/notebook_tools.py`
- Mode prompts: `backend/src/youlearn/modes.py`
- Context loading: `backend/src/youlearn/context.py`
- Server wiring: `backend/src/youlearn/server.py`
- Math-104 structure: `classes/Math-104/CLAUDE.md`
- Homework workflow: `classes/Math-104/hw/CLAUDE.md`
