# Math-104 Notebook Structure — Research & Integration Proposal

**Date**: 2026-02-06
**Purpose**: Document how the Math-104 LaTeX notebook system works and propose how to adapt it for YouLearn's agent-managed, multi-class system.

---

## Part 1: How Math-104 Works (Complete Documentation)

### Directory Structure

```
classes/Math-104/
  CLAUDE.md              # Repo navigation guide (for Claude sessions)
  README.md              # Human-facing intro
  Makefile               # Build system (pdflatex + makeindex)
  Math104-Notes.pdf      # Compiled master output
  notes/
    CLAUDE.md            # Dictation workflow guide
    latex/
      master/master.tex  # Master document: preamble + \subfile includes
      temp/temp.tex      # Template for new lectures
      lec01/lec01.tex    # Individual lecture files (one per lecture)
      lec02/lec02.tex
      ...
    markdown/            # (unused, placeholder)
  hw/
    CLAUDE.md            # Homework assistant guide
    temp/hw_template.tex # Template for new homework submissions
    hw1/
      assignment.txt     # "Rudin Chapter 1: 1,5,9,18\nBonus: 7,8,20"
      book_probs/        # PDF/tex of textbook problem statements
        ch1_probs.pdf
      submission/
        hw1.tex          # Student's LaTeX submission
        hw1.pdf          # Compiled PDF
      explainers/
        p1/explainer1.tex  # Visual concept guide for problem 1
        p1/explainer1.pdf
        p2/explainer2.tex
        ...
    hw2/
      assignment.txt     # "Rudin Chapter 2: 6, 22, 27, 29\nBonus: Kuratowski..."
      book_probs/ch2_probs.tex
      submission/hw2.tex
      explainers/
        p1/ p2/ p3/ p4/ bonus/
```

### The Subfiles Pattern

The core architectural pattern is LaTeX's `subfiles` package:

**master.tex** (preamble + includes):
```latex
\documentclass[11pt]{article}
% ... all packages, colors, theorem envs, custom commands ...
\usepackage{subfiles}

\begin{document}
\maketitle
\tableofcontents
\newpage

\subfile{../lec01/lec01}
\newpage
\subfile{../lec02/lec02}
% ... more lectures ...

\printindex
\end{document}
```

**lecXX.tex** (individual lecture):
```latex
\documentclass[../master/master.tex]{subfiles}
\begin{document}

\renewcommand{\lecturenum}{X}
\renewcommand{\lecturedate}{January 20, 2026}
\renewcommand{\lecturetopic}{Topic Name}

\section{Lecture \lecturenum : \lecturedate}
% ... content ...
\end{document}
```

**Key property**: Each lecture compiles standalone (inherits master's preamble) OR as part of the master document. The `\renewcommand` pattern overrides placeholders defined in master.tex.

### Custom Environments & Commands

**Colored Boxes (tcolorbox)**:
- `lecturesummary` — Orange box (RGB 255,200,120). One per lecture at top. High-level overview.
- `summarybox` — Baby blue box (RGB 173,216,230). One per subsection. Detailed section overview.
- `notebox` — Light red box (RGB 255,180,180). Notes to reader about proof techniques, intuition.

**Theorem Environments** (numbered within sections):
- `theorem`, `lemma`, `proposition`, `corollary` (plain style)
- `definition` (definition style)
- `example` (unnumbered)
- `remark` (remark style)

**Custom Commands**:
- `\R`, `\N`, `\Z`, `\Q`, `\C` — Blackboard bold number sets
- `\eps` — Varepsilon
- `\defn{term}` — Red bold text + auto-adds to index via `\index{term}`
- `\coursetitle`, `\courseterm` — Course metadata
- `\lecturenum`, `\lecturedate`, `\lecturetopic` — Per-lecture placeholders

### Auto-Generated Index

Every `\defn{term}` call automatically adds the term to the document index. The Makefile runs `makeindex` between two `pdflatex` passes:

```makefile
master:
    cd notes/latex/master && pdflatex -interaction=nonstopmode master.tex
    cd notes/latex/master && makeindex master.idx
    cd notes/latex/master && pdflatex -interaction=nonstopmode master.tex
    cp notes/latex/master/master.pdf ./Math104-Notes.pdf
```

This produces an "Index of Definitions" at the end of the compiled PDF with page numbers.

### Lecture Content Patterns (Observed Across 5 Lectures)

Each lecture follows a consistent structure:

1. **Header comment block** with lecture number, topic, date
2. **`\renewcommand`** for lecturenum, lecturedate, lecturetopic
3. **`\section{Lecture N : Date}`** — one section per lecture
4. **`\begin{lecturesummary}`** — 2-4 sentence overview of entire lecture
5. **Subsections** each with:
   - `\begin{summarybox}` — section overview
   - Definitions using `\defn{}` for key terms
   - Theorems with full proofs
   - Examples (often with TikZ diagrams)
   - `\begin{notebox}` — proof technique notes, reader guidance
6. **TikZ diagrams** — Venn diagrams, number lines, Cantor set constructions, proof visualizations

Content density: lectures range from ~100 lines (lec05, more compact) to ~400 lines (lec03, lec04 with many diagrams).

### Homework System

**assignment.txt**: Plain text, just problem numbers:
```
Rudin Chapter 1: 1,5,9,18
Bonus: 7,8,20
```

**Submission template** (`hw_template.tex`): Standalone document (NOT subfiles). Includes:
- `prob` theorem environment for problem statements
- `proof` environment for solutions
- AI Use Disclaimer at bottom

**Actual submissions** (hw1.tex, hw2.tex): Full worked solutions with:
- Problem restatements
- Complete proofs
- Bonus problems (often left blank — student works on them later)
- AI disclaimer

**Explainers**: Standalone visual documents per-problem. Key characteristics:
- Separate preamble (not subfiles — independent documents)
- Heavy use of TikZ diagrams (flowcharts, number lines, Venn diagrams)
- "High-school level" explanations of formal concepts
- Proof strategy visualization (boxes with arrows showing logical flow)
- NOT the solution — builds understanding before attempting the proof
- Example: explainer1.tex for Rudin 1.1 has colored TikZ flowcharts showing proof by contradiction strategy

### Dictation Workflow (notes/CLAUDE.md)

The CLAUDE.md in notes/ establishes a critical principle:
- **ONLY transcribe what the user dictates** — never invent content
- Accepts markdown shorthand (`->` → `\to`, `A int B` → `A \cap B`)
- Commands: "New section", "Make a note about X", "Clean up my logic", "Fill in X"
- After session: run `make` to compile

### Homework Workflow (hw/CLAUDE.md)

- **Only write what the student provides** — guide, don't solve
- Ask before extending to new parts of a problem
- Guide with hints rather than full solutions
- Explainers are for building understanding, NOT giving answers
- The struggle is part of learning

---

## Part 2: Proposed Adapted Structure for YouLearn

### Generalized Directory Structure

```
notebooks/{user_id}/{class_slug}/
  CLAUDE.md                         # Agent navigation guide (auto-generated)
  notebook.json                     # Metadata: class name, term, instructor, lecture count, etc.
  Makefile                          # Build system (tectonic-based)
  {ClassSlug}-Notes.pdf             # Compiled master output
  notes/
    latex/
      master/master.tex             # Master document: preamble + includes
      temp/temp.tex                 # Lecture template (copied for new lectures)
      lec01/lec01.tex               # Individual lectures (subfiles)
      lec02/lec02.tex
      ...
  hw/
    temp/hw_template.tex            # Homework submission template
    hw1/
      assignment.txt                # Problem numbers/descriptions
      book_probs/                   # Reference material (uploaded PDFs)
      submission/hw1.tex            # Student's work
      explainers/
        p1/explainer1.tex           # Visual concept guides
        ...
    hw2/
      ...
  sessions/                         # Session logs (markdown is fine here)
    2026-02-06-lec.md
    2026-02-06-work.md
```

### What Changes vs Math-104

| Aspect | Math-104 (Manual) | YouLearn (Agent-Managed) |
|--------|-------------------|-------------------------|
| Class creation | Manual mkdir + copy | Agent scaffolds entire tree |
| Preamble | Math-104 specific (real analysis) | Templated per subject area |
| Lecture creation | Manual cp temp → lecXX | Agent copies, fills metadata, adds to master.tex |
| `\defn{}` terms | Manual | Agent uses them when taking dictation |
| Index | makeindex in Makefile | Same, but agent triggers compilation |
| HW creation | Manual directory setup | Agent creates from assignment.txt input |
| Explainers | Student requests, Claude writes | Agent proactively offers when student struggles |
| Compilation | `make` via shell | Agent calls tectonic (no makeindex needed) |
| Build output | Local PDF file | PDF embedded as OpenWebUI artifact |
| Glossary | Auto-index via `\defn{}` | Same — index IS the glossary |
| Resources | Not tracked | Could add `resources.tex` section in master |
| Sessions | Not tracked | Markdown session logs in sessions/ dir |

### What Stays the Same

- Subfiles pattern (master + individual lectures)
- Colored summary boxes (lecturesummary, summarybox, notebox)
- `\defn{}` for auto-indexed definitions
- Theorem environments (theorem, lemma, proposition, etc.)
- Homework structure: assignment.txt → submission/ → explainers/
- Dictation-first workflow: student talks, agent transcribes to LaTeX
- Educational philosophy: guide, don't solve

---

## Part 3: NotebookTools API Design

### Core Tools

```python
class NotebookTools(Toolkit):
    """Read and write LaTeX notebook files with path resolution."""

    def __init__(self, notebooks_dir: Path):
        self.notebooks_dir = notebooks_dir
        tools = [
            self.create_class,
            self.read_file,
            self.write_file,
            self.list_files,
            self.create_lecture,
            self.add_lecture_to_master,
            self.create_homework,
            self.create_explainer,
            self.get_notebook_context,
        ]
        super().__init__(name="notebook_tools", tools=tools)
```

### Tool Functions

#### `create_class(class_name, class_slug, subject_area, term, instructor)`
Scaffolds the entire directory tree:
1. Creates `notebooks/{user_id}/{class_slug}/` and all subdirs
2. Generates `master.tex` from a subject-appropriate preamble template
3. Creates `temp.tex` lecture template
4. Creates `hw_template.tex`
5. Creates `CLAUDE.md` with navigation guide
6. Creates `notebook.json` with metadata
7. Creates `Makefile` with tectonic compilation targets
8. Returns confirmation with structure overview

**Subject-area preamble selection**: The preamble should vary by subject:
- **Math**: Full theorem envs, `\defn{}`, number set shortcuts, TikZ
- **CS**: Code listing support (lstlisting), algorithm envs, no theorem numbering
- **Science**: SI units, chemistry formulas, figure support
- **Humanities**: Minimal math, emphasis on quotation and citation

For the hackathon, just ship the Math preamble and generalize later.

#### `read_file(class_slug, path) -> str`
Read any file relative to the class directory. Examples:
- `read_file("math104", "notes/latex/lec01/lec01.tex")`
- `read_file("math104", "hw/hw1/assignment.txt")`
- `read_file("math104", "notebook.json")`

#### `write_file(class_slug, path, content) -> str`
Write/update any file. Agent uses this for all content creation.

#### `list_files(class_slug, subdir="") -> str`
List files in the notebook, optionally in a subdirectory.

#### `create_lecture(class_slug, lecture_num, date, topic) -> str`
1. Copies temp.tex → `notes/latex/lecXX/lecXX.tex`
2. Fills in `\renewcommand` for lecturenum, lecturedate, lecturetopic
3. Adds `\subfile{../lecXX/lecXX}` to master.tex
4. Updates notebook.json lecture count
5. Returns the path to the new lecture file

#### `add_lecture_to_master(class_slug, lecture_num) -> str`
Edits master.tex to add a `\subfile` include. Separate from create_lecture because sometimes the agent needs to fix or re-add entries.

#### `create_homework(class_slug, hw_num, assignment_text) -> str`
1. Creates `hw/hwN/` directory structure (assignment.txt, book_probs/, submission/, explainers/)
2. Writes assignment.txt with the problem list
3. Copies hw_template.tex → `hw/hwN/submission/hwN.tex`
4. Returns confirmation

#### `create_explainer(class_slug, hw_num, problem_id) -> str`
1. Creates `hw/hwN/explainers/pM/` directory
2. Creates `explainerM.tex` with a standalone explainer template
3. Returns the path

#### `get_notebook_context(class_slug, mode) -> str`
Smart context loader. Returns concatenated notebook content appropriate for the mode:

**mode = "lec"**:
- master.tex preamble (just the commands/environments, not the includes — so the agent knows what's available)
- Last 2 lecture .tex files (for continuity/style reference)
- notebook.json metadata

**mode = "rev"**:
- All lecture .tex files (or summaries of older ones if too large)
- The `lecturesummary` and `summarybox` sections extracted from each lecture (for quick review)
- notebook.json metadata

**mode = "work"**:
- The specific homework's assignment.txt
- The homework submission .tex (current progress)
- Relevant lecture .tex files (detected by topic matching or explicit user request)
- Any existing explainers for the assignment

**mode = "end"**:
- notebook.json
- Current session's conversation context (from OpenWebUI messages)

---

## Part 4: Context Loading Strategy for .tex Files

### The Challenge

LaTeX files are more verbose than markdown due to commands and environments. A single lecture can be 200-400 lines. Loading all lectures for /Rev mode could easily exceed token budgets.

### Strategy: Hierarchical Context Loading

#### Level 1: Metadata Only (~500 tokens total)
Extract from each lecture:
- Lecture number, date, topic (from `\renewcommand` lines)
- `lecturesummary` box content (2-4 sentences)

This gives the agent a table of contents with summaries. Good for /Rev and /End modes.

#### Level 2: Section Summaries (~2K tokens total)
Add `summarybox` content from each subsection. This gives detailed section-by-section overview without the proofs/examples.

#### Level 3: Full Lectures (~4-8K tokens per lecture)
Load complete .tex file. Use for:
- The current lecture being written (/Lec mode)
- The specific lecture being reviewed (/Rev mode, on-demand)
- Lectures relevant to current homework (/Work mode)

### Implementation: Parse .tex for Sections

```python
def extract_summaries(tex_content: str) -> dict:
    """Extract structured summaries from a lecture .tex file."""
    result = {
        "lecture_num": "",
        "date": "",
        "topic": "",
        "lecture_summary": "",
        "sections": []
    }
    # Parse \renewcommand{\lecturenum}{X} etc.
    # Extract content between \begin{lecturesummary} and \end{lecturesummary}
    # Extract content between \begin{summarybox} and \end{summarybox}
    # Extract \subsection{} names
    return result
```

This is simple regex parsing — LaTeX has predictable structure in our template. No need for a full LaTeX parser.

### Token Budget Per Mode

| Mode | Context Budget | Strategy |
|------|---------------|----------|
| /Lec | ~8K | Preamble commands + last 2 full lectures + metadata |
| /Rev | ~16K | All lecture summaries (Level 1-2) + on-demand full lecture |
| /Work | ~8K | Full HW assignment + 2-3 relevant full lectures |
| /End | ~4K | Metadata + session transcript |

---

## Part 5: Compilation Strategy

### Tectonic vs pdflatex

Math-104 uses `pdflatex` + `makeindex` (traditional TeX Live toolchain). YouLab uses `tectonic` (Rust-based, auto-downloads packages).

**For YouLearn, use tectonic because**:
1. Already proven in YouLab's LaTeXTools — direct code reuse
2. Single binary, no TeX Live installation needed
3. Auto-downloads packages on first use (no `tlmgr` management)
4. Docker-friendly (small image, no TeX Live bloat)
5. Supports everything Math-104 uses (tcolorbox, tikz, subfiles, amsthm, etc.)

**Trade-off: No `makeindex`**
Tectonic doesn't support `makeindex` out of the box (it runs as a single-pass compiler with automatic re-runs). Options:
1. **Drop the index** for the hackathon — the `\defn{}` command still renders as red bold, just no index page. The agent can maintain a glossary section manually.
2. **Use tectonic's multi-pass mode** — tectonic can handle most index-like features through its automatic re-run system, but makeindex specifically may need a workaround.
3. **Post-hackathon**: Add `makeindex` as a separate step in compilation if needed.

**Recommendation for hackathon**: Keep `\defn{}` for visual highlighting (red bold) but drop the `\makeindex`/`\printindex` from the preamble. The agent can maintain a "Key Definitions" section at the end of the master document manually during /End mode. This is simpler and avoids the makeindex dependency.

### When to Compile

**On-demand only** — compilation is expensive and only needed for PDF output:

1. **User explicitly asks for PDF**: "Compile my notes" or "Show me the PDF"
2. **During /Rev mode**: When student wants a study guide PDF
3. **During /End mode**: Compile and return as artifact so student has latest PDF
4. **Never during /Lec mode**: Agent writes .tex files; compilation would slow down note-taking

### Compilation Flow (Adapted from YouLab)

```python
def compile_notes(class_slug: str, target: str = "master") -> str:
    """Compile LaTeX notes to PDF, return as OpenWebUI artifact."""
    if target == "master":
        tex_path = notebooks_dir / class_slug / "notes/latex/master/master.tex"
    else:
        tex_path = notebooks_dir / class_slug / f"notes/latex/{target}/{target}.tex"

    result = subprocess.run(
        ["tectonic", "-X", "compile", str(tex_path)],
        capture_output=True, timeout=120
    )

    if result.returncode != 0:
        return f"Compilation failed: {result.stderr[:500]}"

    pdf_path = tex_path.with_suffix(".pdf")
    pdf_bytes = pdf_path.read_bytes()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

    # Return as OpenWebUI artifact (same pattern as YouLab)
    html = PDF_VIEWER_TEMPLATE % {"title": ..., "pdf_base64": pdf_base64, ...}
    return f"```html\n{html}\n```"
```

### LaTeXTools Integration

Copy YouLab's `latex_tools.py` but modify it:
- **Current YouLab behavior**: Agent generates LaTeX from scratch, compiles a one-off document
- **YouLearn behavior**: Agent compiles existing .tex files from the notebook structure

Two approaches:
1. **Keep YouLab's render_notes()** for one-off PDF generation (study guides, summaries)
2. **Add compile_notebook()** for compiling the actual notebook master/lecture files

Both return the same OpenWebUI artifact format (base64 PDF in HTML viewer).

---

## Part 6: Specific Changes Needed to the Build Plan

### Section: "Notebook File Structure" (Replace Entirely)

**Old** (markdown-based):
```
notebooks/{user_id}/{class_slug}/
  notebook.json, syllabus.md, glossary.md, resources.md
  lectures/01-intro.md
  assignments/hw1-sorting.md
  sessions/2026-02-06-lec.md
```

**New** (LaTeX-based, adapted from Math-104):
```
notebooks/{user_id}/{class_slug}/
  notebook.json          # Metadata (same as before)
  CLAUDE.md              # Auto-generated navigation guide
  Makefile               # Tectonic build targets
  {ClassSlug}-Notes.pdf  # Compiled master output
  notes/
    latex/
      master/master.tex  # Preamble + \subfile includes
      temp/temp.tex      # Lecture template
      lec01/lec01.tex    # Subfile lectures
      lec02/lec02.tex
      ...
  hw/
    temp/hw_template.tex  # HW submission template
    hw1/
      assignment.txt      # Problem numbers
      book_probs/         # Uploaded reference material
      submission/hw1.tex  # Student's work
      explainers/         # Visual concept guides
        p1/explainer1.tex
    ...
  sessions/               # Session logs (still markdown — these aren't compiled)
    2026-02-06-lec.md
    ...
```

### Section: "Why Markdown (Not LaTeX/JSON)" (Replace with "Why LaTeX")

**New justification**:
- **Proven structure**: Math-104 demonstrates this works for real coursework
- **Professional output**: Compiled PDFs with colored boxes, theorem numbering, TikZ diagrams
- **Auto-indexed glossary**: `\defn{}` command builds glossary automatically
- **Subfiles modularity**: Each lecture compiles standalone or as part of master
- **Agent writes LaTeX naturally**: LLMs are excellent at LaTeX generation, especially with template guidance
- **The preamble IS the styling**: No CSS, no markdown rendering quirks — LaTeX handles it
- **Sessions stay as markdown**: Only compiled documents need LaTeX; session logs are fine as .md

### Section: "NotebookTools" (Update API)

Replace the 4-function markdown API with the 9-function LaTeX-aware API described in Part 3 above.

### Section: "Context Loading Per Mode" (Update)

Keep the same mode structure (/Lec, /Rev, /Work, /End) but update the context loading to reference .tex files instead of .md files, using the hierarchical strategy from Part 4.

- `/Lec` context: Preamble commands (so agent knows available environments) + last 2 lecture .tex files
- `/Rev` context: Extracted summaries from all lectures + on-demand full lecture access
- `/Work` context: assignment.txt + submission .tex + relevant lecture .tex files
- `/End` context: notebook.json + session history

### Section: "Tools" — LaTeXTools (Update)

**Old**: "100% reusable from YouLab"
**New**: Two-part LaTeX tooling:

1. **LaTeXTools** (from YouLab): `render_notes(title, content)` for one-off PDF generation. Used when the agent wants to generate a custom study guide, summary sheet, or explainer as an artifact.

2. **NotebookTools.compile_notebook()** (new): Compiles the actual notebook .tex files (master or individual lectures). Uses tectonic, returns same artifact format.

### Section: "5-Hour Build Order" (Minor Updates)

**Hour 0-1** additions:
- Add: Write `master.tex` preamble template (10 min) — copy from Math-104, parameterize course name/term
- Add: Write `temp.tex` lecture template (5 min)
- Add: Write `hw_template.tex` (5 min)
- Change: NotebookTools now has 9 functions instead of 4 (add 10 min)

**Hour 1-2** changes:
- "Class creation flow" now scaffolds LaTeX directory tree instead of markdown files
- "/Lec mode" writes .tex files instead of .md files

### Section: "Demo Script" (Update)

Replace step 8:
- **Old**: "Generate PDF — LaTeX-compiled beautiful study guide (if time)"
- **New**: "Compile notes — Show the master PDF with colored boxes, theorem numbering, and auto-generated index. This is what the student's notebook looks like after just 20 minutes of lectures."

This is now a primary demo feature, not a nice-to-have.

### Section: "Critical Decisions" (Update)

Replace decision #1:
- **Old**: "Markdown over LaTeX for storage — LLMs write markdown naturally; LaTeX only for PDF output"
- **New**: "LaTeX for notebook storage — Proven by Math-104's real-world use. The subfiles pattern gives us modularity, professional PDF output, and auto-indexed definitions. The agent generates LaTeX directly during note-taking. Session logs remain as markdown."

---

## Part 7: Master.tex Preamble Template (Ready to Use)

This is the generalized preamble, parameterized from Math-104:

```latex
\documentclass[11pt]{article}

% Page geometry
\usepackage[margin=1in]{geometry}

% Math packages
\usepackage{amsmath, amssymb, amsthm}
\usepackage{mathtools}

% Other useful packages
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{tcolorbox}
\usepackage{tikz}
\usepackage{subfiles}

% Baby blue section summary box
\definecolor{babyblue}{RGB}{173, 216, 230}
\newtcolorbox{summarybox}{
    colback=babyblue!30,
    colframe=babyblue!80,
    boxrule=1pt, arc=3pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Orange lecture summary box
\definecolor{lectureorange}{RGB}{255, 200, 120}
\newtcolorbox{lecturesummary}{
    colback=lectureorange!30,
    colframe=lectureorange!80,
    boxrule=1pt, arc=3pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Light red note box
\definecolor{lightred}{RGB}{255, 180, 180}
\newtcolorbox{notebox}{
    colback=lightred!30,
    colframe=lightred!80,
    boxrule=1pt, arc=3pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Colored bold for definitions
\newcommand{\defn}[1]{\textcolor{red}{\textbf{#1}}}

% Theorem environments
\theoremstyle{plain}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{proposition}[theorem]{Proposition}
\newtheorem{corollary}[theorem]{Corollary}

\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem*{example}{Example}

\theoremstyle{remark}
\newtheorem{remark}[theorem]{Remark}

% Common math shortcuts
\newcommand{\R}{\mathbb{R}}
\newcommand{\N}{\mathbb{N}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\Q}{\mathbb{Q}}
\newcommand{\C}{\mathbb{C}}
\newcommand{\eps}{\varepsilon}

% Course info (PARAMETERIZED — agent fills these in)
\newcommand{\coursetitle}{%(class_name)s}
\newcommand{\courseterm}{%(term)s}

% Lecture info placeholders (overwritten by each lecture via \renewcommand)
\newcommand{\lecturenum}{}
\newcommand{\lecturedate}{}
\newcommand{\lecturetopic}{}

\title{\coursetitle \\ \large Lecture Notes}
\author{%(student_name)s}
\date{\courseterm}

\begin{document}

\maketitle
\tableofcontents
\newpage

%----------------------------------------------------------------------
% LECTURES - Add new lectures here
%----------------------------------------------------------------------

% LECTURE_INCLUDES_PLACEHOLDER

\end{document}
```

The agent replaces `%(class_name)s`, `%(term)s`, `%(student_name)s` during class creation, and appends `\subfile` lines at the `LECTURE_INCLUDES_PLACEHOLDER` comment.

**Note**: `\makeindex`/`\printindex` removed vs Math-104. The `\defn{}` command still renders as red bold for visual highlighting. For a true glossary, the agent can maintain a "Key Definitions" section at the end, or we add makeindex back post-hackathon.

---

## Part 8: Open Questions

1. **TikZ in agent-generated content**: The Math-104 lectures use extensive TikZ diagrams. Can the agent reliably generate TikZ during live lecture note-taking? Likely yes for simple diagrams (number lines, Venn diagrams) but risky for complex ones. Mitigation: agent generates simpler diagrams during /Lec, enhances during /End.

2. **Compilation time on Render**: Tectonic's first run downloads packages (~30s). Subsequent runs are fast (~2-5s). Need to pre-warm the cache in the Docker image or accept first-run latency.

3. **tectonic + subfiles**: Need to verify tectonic handles the subfiles package correctly. pdflatex handles it fine; tectonic should too since it's a full TeX engine, but worth testing.

4. **PDF size**: With TikZ diagrams and 5+ lectures, the master PDF could be large. Base64 encoding doubles the size for the artifact. May need to compress or serve PDFs differently for large notebooks.

5. **Concurrent lecture editing**: If the agent is writing lec03.tex and the student asks to compile, the file might be in a partial state. Solution: only compile on explicit request, not automatically.
