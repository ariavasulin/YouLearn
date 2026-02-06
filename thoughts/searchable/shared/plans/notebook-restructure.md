# Plan: Restructure Math-104 Demo Notebook

**Date**: 2026-02-06
**Scope**: File structure and content changes to `classes/Math-104/` — NOT backend code
**Status**: Implemented
**Depends on**: None (pure LaTeX/content work)

---

## Goal

Transform the Math-104 notebook from a plain "5 lectures + index" document into a complete, impressive demo notebook with: syllabus, lectures, assignments section, sessions section, resources, glossary, and auto-generated index — all compiled into a single PDF via pdflatex + makeindex (the proven, working toolchain).

### Target Table of Contents (in compiled PDF)

```
1  Syllabus
   1.1  Course Information
   1.2  Course Requirements
   1.3  Learning Objectives
   1.4  Assignments
   1.5  Course Calendar
2  Lectures
   2.1  Lecture 1: January 20, 2026
      2.1.1  Ordered sets and the least-upper-bound property
      2.1.2  Fields
   2.2  Lecture 2: January 22, 2026
      ...
   2.3–2.5  Lectures 3–5
3  Assignments
   3.1  Homework 1 (summary + full PDF)
   3.2  Homework 2 (summary + full PDF)
4  Sessions
   4.1  Feb 6 — Review Session (example)
5  Resources
6  Glossary
Index of Definitions
```

---

## What Currently Exists

| Item | Status | Notes |
|------|--------|-------|
| `notes/latex/master/master.tex` | Needs modification | Has preamble + 5 lecture includes + `\printindex`. Missing: syllabus, assignments, sessions, resources, glossary sections. Keep `\makeindex`/`\printindex` — they work. |
| `notes/latex/lec01-lec05/` | **DO NOT MODIFY** | Real content, working. 5 lectures using subfiles pattern |
| `notes/latex/temp/temp.tex` | Keep as-is | Lecture template |
| `hw/hw1/, hw/hw2/` | **DO NOT MODIFY** | Real student work. Full submission PDFs embedded in Assignments section via `\includepdf` |
| `hw/temp/hw_template.tex` | Keep as-is | HW template |
| `Makefile` | Keep as-is | Already uses pdflatex + makeindex and works correctly |
| `sessions/` | Does not exist | Create with example session .tex |
| Syllabus | Does not exist | Create as subfile |
| Assignments section | Does not exist | Create as subfile (references hw/ dirs) |
| Resources section | Does not exist | Create as subfile |
| Glossary section | Does not exist | Create as subfile (curated glossary WITH definitions, complements the auto-index) |

---

## Constraints

1. **DO NOT modify** `lec01.tex` through `lec05.tex` — they are real content
2. **DO NOT modify** anything in `hw/` — it's real student work
3. **Use existing preamble commands** (lecturesummary, summarybox, notebox, `\defn{}`, theorem envs). Added `pdfpages` package for embedding homework PDFs.
4. All new sections are `\subfile` documents (same pattern as lectures)
5. **Compilation: pdflatex + makeindex** (the existing working toolchain). Keep `\makeindex`/`\printindex` — the auto-generated Index of Definitions is a feature, not a liability.
6. The `\defn{}` command is **unchanged** — red bold + `\index{}`. The auto-index AND the curated glossary both appear in the PDF (glossary has definitions, index has page numbers).
7. Syllabus content should be realistic for Math 104 (Intro to Real Analysis, Spring 2026, UC Berkeley style, Rudin textbook)
8. Keep it simple — hackathon demo quality, not production quality

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `notes/latex/master/master.tex` | **Modify** | Add `\usepackage{pdfpages}`, `\section{Lectures}` with `\let`-based section demoting so lectures nest in PDF outline, plus syllabus/assignments/sessions/resources/glossary `\subfile` includes. Keep `\makeindex`/`\printindex` (index moves after glossary). |
| `notes/latex/syllabus/syllabus.tex` | **Create** | Course overview, requirements, objectives, assignments listing, calendar |
| `notes/latex/assignments/assignments.tex` | **Create** | Summary boxes for HW1/HW2 + full submission PDFs embedded via `\includepdf` |
| `notes/latex/sessions/sessions.tex` | **Create** | Container subfile for session log entries |
| `notes/latex/sessions/session-2026-02-06.tex` | **Create** | Example session log (demonstrates what the agent produces) |
| `notes/latex/resources/resources.tex` | **Create** | Textbook, supplementary materials, links |
| `notes/latex/glossary/glossary.tex` | **Create** | Curated glossary with definitions organized by topic (complements the auto-index) |
| `Makefile` | **No change** | Already works with pdflatex + makeindex |
| `sessions/` | **Create dir** | Runtime directory for agent-written .tex session logs |

---

## Step 1: Preamble Changes

Minimal preamble addition:
- **Added**: `\usepackage{pdfpages}` — needed to embed full homework submission PDFs in the Assignments section
- `\usepackage{makeidx}` and `\makeindex` stay
- `\defn{}` keeps both red bold AND `\index{}` — the auto-generated index is a feature
- `\printindex` stays (moves to after the glossary in the new document body)

**Why keep pdflatex + makeindex**: It already works. The Makefile produces correct PDFs with a working Index of Definitions. Switching to tectonic would mean losing the index for no benefit during a hackathon. Tectonic can be a post-hackathon optimization for Docker deployment.

**Glossary vs Index**: Both appear in the final PDF. The glossary (Step 6) is a curated section with actual definitions organized by topic. The auto-generated Index of Definitions (from `\printindex`) lists every `\defn{}` term with page numbers. They complement each other — glossary for studying, index for quick lookup.

---

## Step 2: Create Syllabus Subfile

### File: `notes/latex/syllabus/syllabus.tex`

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Syllabus}

\begin{lecturesummary}
\textbf{Course Overview:} Math 104 is an introduction to real analysis, covering the rigorous foundations of calculus. We study the real number system, sequences and series, continuity, differentiation, and Riemann integration, with emphasis on proofs. The primary text is Walter Rudin's \textit{Principles of Mathematical Analysis} (3rd edition).
\end{lecturesummary}

\subsection{Course Information}

\begin{summarybox}
\textbf{At a Glance:}
\begin{itemize}[nosep]
    \item \textbf{Course}: Math 104 --- Introduction to Real Analysis
    \item \textbf{Term}: Spring 2026
    \item \textbf{Schedule}: MWF 10:00--10:50 AM, Evans Hall 3
    \item \textbf{Textbook}: Rudin, \textit{Principles of Mathematical Analysis}, 3rd ed.
    \item \textbf{Prerequisites}: Math 53 and Math 54 (or equivalents)
\end{itemize}
\end{summarybox}

\subsection{Course Requirements}

\begin{itemize}
    \item \textbf{Homework (40\%)}: Weekly problem sets from Rudin. Due Fridays. Lowest score dropped.
    \item \textbf{Midterm (25\%)}: In-class, Week 8. Covers Chapters 1--4.
    \item \textbf{Final (35\%)}: Comprehensive. Covers Chapters 1--7.
\end{itemize}

\subsection{Learning Objectives}

By the end of this course, students will be able to:
\begin{enumerate}
    \item Construct rigorous proofs involving properties of the real numbers.
    \item State and apply the completeness axiom (Least Upper Bound Property).
    \item Prove convergence or divergence of sequences and series.
    \item Define and prove properties of continuous functions on metric spaces.
    \item Apply compactness and connectedness in proofs.
    \item Develop and present mathematical arguments with clarity and precision.
\end{enumerate}

\subsection{Assignments}

\begin{summarybox}
\textbf{Homework Schedule:}
\begin{itemize}[nosep]
    \item \textbf{HW 1} --- Rudin Ch.\ 1: Problems 1, 5, 9, 18 (Bonus: 7, 8, 20) \hfill \textit{Due: Jan 31}
    \item \textbf{HW 2} --- Rudin Ch.\ 2: Problems 6, 22, 27, 29 (Bonus: Kuratowski) \hfill \textit{Due: Feb 7}
    \item \textbf{HW 3} --- Rudin Ch.\ 2--3: TBD \hfill \textit{Due: Feb 14}
    \item \textbf{HW 4} --- Rudin Ch.\ 3: TBD \hfill \textit{Due: Feb 21}
    \item \textbf{HW 5} --- Rudin Ch.\ 4: TBD \hfill \textit{Due: Feb 28}
\end{itemize}
\end{summarybox}

\subsection{Course Calendar}

\begin{center}
\begin{tabular}{|c|l|l|l|}
\hline
\textbf{Week} & \textbf{Dates} & \textbf{Topics} & \textbf{Reading/Due} \\
\hline
1 & Jan 20--24 & Ordered sets, LUB property, fields & Rudin 1.1--1.4 \\
2 & Jan 27--31 & Construction of $\R$, Archimedean property & Rudin 1.5--1.8; \textbf{HW 1 due} \\
3 & Feb 3--7 & Countability, metric spaces & Rudin 2.1--2.3; \textbf{HW 2 due} \\
4 & Feb 10--14 & Topology, open/closed sets & Rudin 2.4--2.6; \textbf{HW 3 due} \\
5 & Feb 17--21 & Compactness, Heine-Borel & Rudin 2.7--2.8; \textbf{HW 4 due} \\
6 & Feb 24--28 & Sequences, subsequences & Rudin 3.1--3.3; \textbf{HW 5 due} \\
7 & Mar 3--7 & Series, convergence tests & Rudin 3.4--3.7 \\
8 & Mar 10--14 & \textbf{Midterm (Wed)} & Covers Ch.\ 1--4 \\
\hline
\end{tabular}
\end{center}

\end{document}
```

### Rationale

- Realistic UC Berkeley Math 104 syllabus (based on actual course structure)
- Uses existing box environments for visual consistency
- `lecturesummary` for the course overview (orange box — high impact)
- `summarybox` for at-a-glance info and homework schedule (blue box)
- The assignments listing matches the real hw1/hw2 content, with placeholders for future HWs
- The calendar aligns with the existing lecture dates (Jan 20, 22, 27, 29, Feb 3)
- Clean table for calendar — tcolorbox isn't needed here, a simple tabular works

---

## Step 3: Create Assignments Subfile

### File: `notes/latex/assignments/assignments.tex`

This section gives a summary of each homework assignment, followed by the **full submission PDF** embedded inline via `\includepdf`. The hw/ `.tex` files are standalone (not subfiles), so we embed the pre-compiled PDFs.

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Assignments}

\begin{lecturesummary}
\textbf{Assignments Overview:} ...
\end{lecturesummary}

\subsection{Homework 1 --- Rudin Chapter 1}

\begin{summarybox}
\textbf{Status:} Submitted \\
\textbf{Due:} January 31, 2026 \\
\textbf{Problems:} 1, 5, 9, 18 \quad \textit{Bonus:} 7, 8, 20 \\
\textbf{Related Lectures:} Lecture 1 (Ordered sets, LUBP, fields), Lecture 2 (Construction of $\R$)
\end{summarybox}

\textbf{Key concepts tested:}
\begin{itemize}[nosep]
    \item Irrationality proofs and closure properties of $\Q$ (Problem 1)
    \item Ordered field axioms (Problem 5)
    \item Supremum and infimum computations (Problem 9)
    \item Properties of the complex field (Problem 18)
\end{itemize}

\includepdf[pages=-, pagecommand={}]{../../../hw/hw1/submission/hw1.pdf}

\subsection{Homework 2 --- Rudin Chapter 2}

\begin{summarybox}
... (same pattern)
\end{summarybox}

... (key concepts)

\includepdf[pages=-, pagecommand={}]{../../../hw/hw2/submission/hw2.pdf}

\end{document}
```

### Rationale

- Each HW gets a summary box (status, due date, key concepts) followed by the full submission
- Uses `\includepdf` from the `pdfpages` package to embed pre-compiled hw PDFs
- The hw `.tex` files are standalone documents (own `\documentclass`, `\newtheorem`), so they can't be `\subfile`'d — embedding the PDF is the correct approach
- `pagecommand={}` keeps master's page numbering on the embedded pages
- Path `../../../hw/...` navigates from `notes/latex/assignments/` up to `classes/Math-104/`

---

## Step 4: Create Sessions Subfile

### File: `notes/latex/sessions/sessions.tex`

This is the container that includes individual session logs. The agent will add new `\subfile` lines here after each session.

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Sessions}

\begin{lecturesummary}
\textbf{Study Sessions:} This section logs study sessions with the YouLearn AI companion. Each entry records the date, mode, topics covered, and what was accomplished. Sessions are automatically logged when ending a study session with \texttt{/Done}.
\end{lecturesummary}

% Session logs — newest first
\subfile{session-2026-02-06}

% ADD_SESSION_HERE — agent appends new \subfile lines above this comment

\end{document}
```

### File: `notes/latex/sessions/session-2026-02-06.tex`

An example session log that demonstrates what the agent produces:

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\subsection{February 6, 2026 --- Review Session}

\begin{summarybox}
\textbf{Session Summary} \\
\textbf{Date:} February 6, 2026 \\
\textbf{Mode:} Review (\texttt{/Rev}) \\
\textbf{Duration:} 45 minutes \\
\textbf{Topics:} Compactness, Heine-Borel theorem, perfect sets
\end{summarybox}

\textbf{What we covered:}
\begin{itemize}[nosep]
    \item Reviewed the definition of \defn{compactness} and open covers from Lecture 5
    \item Worked through why $[0,1]$ is compact but $(0,1)$ is not
    \item Practiced applying the Heine-Borel theorem to identify compact subsets of $\R^n$
    \item Discussed the relationship between compactness, closedness, and boundedness
    \item Reviewed the Cantor set as an example of a perfect set
\end{itemize}

\textbf{Areas for further review:}
\begin{itemize}[nosep]
    \item Sequential compactness vs.\ open-cover compactness (Lecture 5, \S5.1)
    \item Proof that compact subsets of Hausdorff spaces are closed (Theorem 2.34)
\end{itemize}

\textbf{Next session:} Work through HW 2, Problem 27 (compactness argument).

\end{document}
```

### Rationale

- Sessions are `.tex` subfiles so they compile into the master PDF
- Container pattern: `sessions.tex` includes individual session files via `\subfile`
- The `ADD_SESSION_HERE` comment gives the agent a clear insertion point
- Example session shows realistic content: mode, duration, topics, what was covered, next steps
- Uses `\defn{}` where appropriate (e.g., compactness) for visual consistency
- Agent creates new session files at `notes/latex/sessions/session-YYYY-MM-DD.tex` and adds a `\subfile` line to `sessions.tex`

---

## Step 5: Create Resources Subfile

### File: `notes/latex/resources/resources.tex`

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Resources}

\begin{lecturesummary}
\textbf{Course Resources:} Textbooks, supplementary materials, and references for Math 104. This section is updated throughout the course as new resources are discovered.
\end{lecturesummary}

\subsection{Primary Textbook}

\begin{summarybox}
\textbf{Walter Rudin}, \textit{Principles of Mathematical Analysis}, 3rd edition. McGraw-Hill, 1976. ISBN: 978-0-07-054235-8.

The standard reference for undergraduate real analysis. Chapters 1--7 are covered in this course. Known for its concise, rigorous style. Expect to read proofs multiple times.
\end{summarybox}

\subsection{Supplementary Materials}

\begin{itemize}
    \item \textbf{Abbott}, \textit{Understanding Analysis}, 2nd ed. --- More accessible introduction. Good for building intuition before tackling Rudin.
    \item \textbf{Tao}, \textit{Analysis I \& II} --- Builds analysis from the ground up. Excellent for students who want to see every detail.
    \item \textbf{Pugh}, \textit{Real Mathematical Analysis} --- Beautiful exposition with great exercises and pictures.
\end{itemize}

\subsection{Online Resources}

\begin{itemize}
    \item Francis Su's \textit{Real Analysis} lecture series (Harvey Mudd, YouTube) --- Exceptional lectures covering Rudin chapter by chapter.
    \item MIT OCW 18.100A --- Problem sets and lecture notes for a similar course.
\end{itemize}

\end{document}
```

### Rationale

- Realistic resources for a Math 104 course
- Rudin is the actual textbook used
- Supplementary texts are the standard recommendations
- Uses summarybox for the primary textbook (visual emphasis)
- Online resources section shows the agent can add links over time

---

## Step 6: Create Glossary Subfile

### File: `notes/latex/glossary/glossary.tex`

This complements the auto-generated Index of Definitions (`\printindex`). The index gives page numbers; the glossary gives actual definitions organized by topic. Both appear in the final PDF.

```latex
\documentclass[../master/master.tex]{subfiles}

\begin{document}

\section{Glossary}

\begin{lecturesummary}
\textbf{Key Definitions:} A glossary of important terms and definitions from the course, organized by topic. Terms marked in \textcolor{red}{\textbf{red bold}} in the lecture notes appear here with their formal definitions and the lecture where they were introduced.
\end{lecturesummary}

\subsection{Ordered Sets \& Real Numbers (Lectures 1--2)}

\begin{description}[style=nextline, leftmargin=2em]
    \item[\defn{Member}] $x \in A$ means $x$ is an element of the set $A$. (Lecture 1)
    \item[\defn{Empty set}] The set $\emptyset$ containing no elements. (Lecture 1)
    \item[\defn{Subset}] $A \subseteq B$ if every element of $A$ is also in $B$. (Lecture 1)
    \item[\defn{Proper subset}] $A \subset B$ if $A \subseteq B$ and $A \neq B$. (Lecture 1)
    \item[\defn{Partial order}] A relation $\leq$ on $S$ that is reflexive, antisymmetric, and transitive. (Lecture 1)
    \item[\defn{Total order}] A partial order where every two elements are comparable. (Lecture 1)
    \item[\defn{Upper bound}] $b$ is an upper bound of $E \subseteq S$ if $x \leq b$ for all $x \in E$. (Lecture 1)
    \item[\defn{Lower bound}] $b$ is a lower bound of $E$ if $b \leq x$ for all $x \in E$. (Lecture 1)
    \item[\defn{Supremum}] The least upper bound of a set $E$, written $\sup E$. (Lecture 1)
    \item[\defn{Infimum}] The greatest lower bound of a set $E$, written $\inf E$. (Lecture 1)
    \item[\defn{Least Upper Bound Property}] Every non-empty subset bounded above has a supremum. (Lecture 1)
    \item[\defn{Field}] A set $F$ with addition and multiplication satisfying the field axioms. (Lecture 1)
    \item[\defn{Ordered field}] A field with a total order compatible with the field operations. (Lecture 1)
    \item[\defn{Dedekind cut}] A partition of $\Q$ into two non-empty sets $A | B$ where every element of $A$ is less than every element of $B$, and $A$ has no maximum. (Lecture 2)
    \item[\defn{Archimedean property}] For any $x, y \in \R$ with $x > 0$, there exists $n \in \N$ such that $nx > y$. (Lecture 2)
\end{description}

\subsection{Set Theory \& Countability (Lecture 3)}

\begin{description}[style=nextline, leftmargin=2em]
    \item[\defn{Countable}] A set $A$ is countable if there exists a bijection $f: A \to \N$ (or $A$ is finite). (Lecture 3)
    \item[\defn{Uncountable}] A set that is not countable. (Lecture 3)
    \item[\defn{Cardinality}] Two sets have the same cardinality if there is a bijection between them, written $A \sim B$. (Lecture 3)
    \item[\defn{Equivalence relation}] A relation that is reflexive, symmetric, and transitive. (Lecture 3)
\end{description}

\subsection{Topology \& Metric Spaces (Lectures 4--5)}

\begin{description}[style=nextline, leftmargin=2em]
    \item[\defn{Metric space}] A set $X$ with a distance function $d: X \times X \to \R$ satisfying positivity, symmetry, and the triangle inequality. (Lecture 4)
    \item[\defn{Open ball}] $B_r(x) = \{y \in X : d(x, y) < r\}$ for $r > 0$. Also called a neighborhood. (Lecture 4)
    \item[\defn{Open set}] A set $G$ is open if every point of $G$ is an interior point. (Lecture 4)
    \item[\defn{Closed set}] A set $F$ is closed if its complement $F^c$ is open. Equivalently, $F$ contains all its limit points. (Lecture 4)
    \item[\defn{Limit point}] $p$ is a limit point of $E$ if every neighborhood of $p$ contains a point $q \in E$ with $q \neq p$. (Lecture 4)
    \item[\defn{Interior point}] $p$ is an interior point of $E$ if there exists $r > 0$ such that $B_r(p) \subseteq E$. (Lecture 4)
    \item[\defn{Closure}] $\overline{E} = E \cup E'$ where $E'$ is the set of limit points of $E$. (Lecture 4)
    \item[\defn{Dense}] $E$ is dense in $X$ if $\overline{E} = X$. (Lecture 4)
    \item[\defn{Open cover}] A collection of open sets $\{G_\alpha\}$ such that $E \subseteq \bigcup G_\alpha$. (Lecture 5)
    \item[\defn{Compact}] A set $K$ is compact if every open cover has a finite subcover. (Lecture 5)
    \item[\defn{Perfect set}] A closed set in which every point is a limit point. (Lecture 5)
\end{description}

\end{document}
```

### Rationale

- Complements the auto-generated Index of Definitions (index has page numbers, glossary has definitions)
- Grouped by topic/lecture range rather than alphabetically (more useful for studying)
- Each term uses `\defn{}` for consistent red bold styling (and generates index entries too)
- Includes the lecture number where the term was introduced (cross-reference)
- Uses `description` environment with `style=nextline` for clean formatting
- The agent can append new terms to the appropriate subsection during `/Done` sessions
- Demo impact: shows both a curated glossary AND an auto-generated index — two views of the same data

---

## Step 7: Update master.tex

### Preamble Changes

- **Added**: `\usepackage{pdfpages}` — for embedding homework submission PDFs

### Lecture Nesting in PDF Outline

Lectures are nested under a `\section{Lectures}` parent using `\let`-based section demoting. This avoids modifying any lecture files:

```latex
\section{Lectures}

\let\origsection\section
\let\origsubsection\subsection
\let\origsubsubsection\subsubsection
\let\section\origsubsection          % \section in lectures → \subsection
\let\subsection\origsubsubsection    % \subsection in lectures → \subsubsection

% ... lecture \subfile includes ...

% Restore original sectioning commands
\renewcommand{\section}{\origsection}
\renewcommand{\subsection}{\origsubsection}
\renewcommand{\subsubsection}{\origsubsubsection}
```

**Why `\let` not `\renewcommand`**: `\let` captures the value at assignment time. `\renewcommand{\section}{\subsection}` followed by `\renewcommand{\subsection}{\subsubsection}` would cause `\section` to chain through to `\subsubsection` (since `\subsection` is re-evaluated at call time). `\let` avoids this.

**Effect on theorem numbering**: Theorems are `[section]`-numbered. With lectures demoted to `\subsection`, theorems become e.g. `Theorem 2.1.1` instead of `Theorem 2.1`. This is expected and more precise.

### What Changed vs Original master.tex

- **Added**: `\usepackage{pdfpages}` in preamble
- **Added**: `\section{Lectures}` parent with `\let`-based section demoting/restoring
- **Added**: `\subfile` includes for syllabus, assignments, sessions, resources, glossary
- **Added**: Section comment headers for visual organization
- **Added**: `ADD_LECTURE_HERE` marker comment for agent to find insertion point
- **Moved**: `\printindex` to the very end (after glossary) — was previously right after lectures
- **Added**: `\newpage` before each major section for clean page breaks
- **Kept**: `\makeindex`/`\printindex` unchanged, `\defn{}` unchanged

---

## Step 8: Makefile — No Changes

The existing Makefile already works correctly:

```makefile
master:
	cd notes/latex/master && pdflatex -interaction=nonstopmode master.tex
	cd notes/latex/master && makeindex master.idx
	cd notes/latex/master && pdflatex -interaction=nonstopmode master.tex
	cp notes/latex/master/master.pdf ./Math104-Notes.pdf
```

The three-pass build (pdflatex → makeindex → pdflatex) is needed for the TOC and Index of Definitions. This is proven and working — no reason to change it for a hackathon.

**Post-hackathon**: Can switch to tectonic for Docker deployment (smaller image, no TeX Live). Would need to either drop makeindex or add a workaround. Not worth the risk now.

---

## Step 9: Create `sessions/` Runtime Directory

Create `classes/Math-104/sessions/` as an empty directory with a `.gitkeep`:

```bash
mkdir -p classes/Math-104/sessions
touch classes/Math-104/sessions/.gitkeep
```

This is the runtime directory where the agent writes session logs as `.tex` files. The `notes/latex/sessions/` directory holds the compilable subfiles that get included in master.tex. The agent creates .tex files in `notes/latex/sessions/` (for compilation) and could optionally also drop quick .md logs in `sessions/` for non-compiled notes, but the primary output is .tex.

**Clarification on session flow**:
1. Agent writes `notes/latex/sessions/session-YYYY-MM-DD.tex` (compilable subfile)
2. Agent adds `\subfile{session-YYYY-MM-DD}` line to `notes/latex/sessions/sessions.tex`
3. On next `make`, the session appears in the compiled PDF

---

## Implementation Order

This is the build order for a developer:

### Phase 1: Create New Directories and Files (~20 min)

1. Create directories:
   ```bash
   mkdir -p classes/Math-104/notes/latex/syllabus
   mkdir -p classes/Math-104/notes/latex/assignments
   mkdir -p classes/Math-104/notes/latex/sessions
   mkdir -p classes/Math-104/notes/latex/resources
   mkdir -p classes/Math-104/notes/latex/glossary
   mkdir -p classes/Math-104/sessions
   ```

2. Create all 7 new `.tex` files (syllabus.tex, assignments.tex, sessions.tex, session-2026-02-06.tex, resources.tex, glossary.tex, .gitkeep)

### Phase 2: Modify master.tex (~5 min)

3. Replace document body with new structure (syllabus → lectures → assignments → sessions → resources → glossary → index)
4. Preamble stays unchanged

### Phase 3: Test Compilation (~5 min)

5. Run `make clean` to remove old aux files
6. Run `make` to compile with pdflatex + makeindex
7. Verify the PDF has the correct TOC structure
8. Verify all sections render correctly (colored boxes, theorem numbering, glossary, index)
9. Verify no compilation errors from the existing lecture files

---

## Success Criteria

1. `make` produces `Math104-Notes.pdf` via pdflatex + makeindex (no errors)
2. PDF Table of Contents shows: Syllabus → **Lectures (with nested 2.1–2.5)** → Assignments → Sessions → Resources → Glossary → Index of Definitions
3. Lectures are nested under a "2 Lectures" section in the PDF outline (2.1 Lecture 1, 2.2 Lecture 2, etc.)
4. Syllabus section has orange overview box, blue info box, calendar table
5. Existing lectures 1-5 render correctly (theorem numbering shifts to 2.x.y format due to nesting — this is expected)
6. Assignments section has summary boxes for hw1/hw2 **plus full submission PDFs embedded inline**
7. Sessions section contains the example session log
8. Resources section lists textbook and supplementary materials
9. Glossary section has organized key terms with red bold formatting
10. Index of Definitions auto-generated from `\defn{}` with correct page numbers
11. `make lec01` still compiles lec01 standalone
12. Total PDF is ~48 pages and looks professional/impressive for a demo

---

## What This Does NOT Cover

- Backend code changes (see `thoughts/shared/plans/agent-notebook-interaction.md`)
- How the agent creates new sessions at runtime (that's the agent interaction plan)
- You.com or Composio integration
- Class creation scaffolding (demo uses existing Math-104)
- Deployment to Render
