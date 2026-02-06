# "Show Me" PDF Navigation — Implementation Plan

## Overview

Add "show me" behavior: when the user says "show me [something]", the agent compiles the full master PDF and returns a URL with `#page=N` so the browser opens directly to the relevant page.

## Current State

- `compile_notes("master")` compiles the full PDF, returns a plain URL like `.../Math-104-Notes.pdf`
- `compile_notes("lecXX")` compiles individual lectures (standalone PDFs)
- PDFs served inline via `Content-Disposition: inline` — browser rendering works
- `hyperref` loaded in master.tex — creates PDF bookmarks automatically
- `.aux` file generated during compilation contains `\contentsline` entries with **page numbers** for every section/subsection
- System prompts have no "show me" instructions
- No page metadata is extracted or returned to the agent

## Desired End State

1. When user says "show me lecture 3" or "show me the definition of compactness", the agent:
   - Compiles the master PDF (if not already compiled)
   - Knows which page the relevant content starts on
   - Returns a link like `.../Math-104-Notes.pdf#page=15`
2. The browser opens the full PDF scrolled to the right page
3. Works for lectures, assignments, glossary, sessions, resources, index — any section in the notebook

### Verification
- Say "show me lecture 3" → agent compiles master, responds with URL containing `#page=15`
- Say "show me the glossary" → URL contains `#page=47`
- Say "show me homework 1" → URL contains `#page=34`
- Opening the URL in a browser scrolls to the correct page

## What We're NOT Doing

- No custom `\label` or `\hypertarget` additions to .tex files — the .aux TOC data is sufficient
- No new Python dependencies — we parse .aux with regex (already in stdlib)
- No changes to the PDF serving endpoint — `#page=N` is a client-side fragment, not a server param
- No individual lecture compilation for "show me" — always full master
- No fuzzy search for definitions/theorems within lecture content (the agent uses its context knowledge to pick the right section)

## Implementation Approach

Parse the `.aux` file after master compilation to extract a section→page mapping. Return this mapping to the agent as part of the `compile_notes` result. Update system prompts to tell the agent how to use it.

**Why .aux parsing?** After pdflatex runs, `master.aux` contains lines like:
```
\contentsline {subsection}{\numberline {2.1}Lecture 1: January 20, 2026}{5}{subsection.2.1}
```
The `{5}` is the page number. This is generated automatically — no LaTeX changes needed, no new deps.

---

## Phase 1: Extract page map from .aux after compilation

### Overview
Add a helper method to `NotebookTools` that parses `master.aux` and returns a dict mapping section titles to page numbers.

### Changes Required

#### 1. New helper: `_parse_page_map()`
**File**: `backend/src/youlearn/tools/notebook_tools.py`
**Changes**: Add a private method that parses the .aux file

```python
def _parse_page_map(self) -> dict[str, int]:
    """Parse master.aux to extract section/subsection -> page number mapping.

    Returns a dict like:
        {"Syllabus": 3, "Lectures": 5, "Lecture 1: January 20, 2026": 5,
         "Lecture 2: January 22, 2026": 9, "Assignments": 34, ...}
    """
    aux_path = self.class_dir / "notes" / "latex" / "master" / "master.aux"
    if not aux_path.exists():
        return {}

    content = aux_path.read_text()
    page_map: dict[str, int] = {}

    # Match: \contentsline {section/subsection}{\numberline {X.Y}Title}{PAGE}{...}
    # Also match unnumbered: \contentsline {section}{Index of Definitions}{PAGE}{...}
    pattern = re.compile(
        r'\\contentsline\s*\{(?:section|subsection)\}'
        r'\{(?:\\numberline\s*\{[^}]*\})?(.+?)\}'
        r'\{(\d+)\}'
    )

    for match in pattern.finditer(content):
        title = match.group(1).strip()
        page = int(match.group(2))
        # Clean up LaTeX artifacts from title
        title = re.sub(r'\\[a-zA-Z]+\s*', '', title)  # strip commands
        title = title.replace('{', '').replace('}', '')  # strip braces
        title = title.strip()
        if title:
            page_map[title] = page

    return page_map
```

#### 2. Update `compile_notes` return for master
**File**: `backend/src/youlearn/tools/notebook_tools.py`
**Changes**: After successful master compilation, parse page map and include it in the return string

Replace the current master return block (lines 339-343) with:

```python
# Parse page map from .aux file
page_map = self._parse_page_map()
download_url = f"{self.backend_url}/pdf/{self.class_slug}/{root_pdf.name}"

# Format page map for the agent
if page_map:
    pages_str = "\n".join(f"  - {title}: page {page}" for title, page in page_map.items())
    return (
        f"Compiled successfully ({pdf_path.stat().st_size // 1024}KB).\n"
        f"PDF URL: {download_url}\n\n"
        f"Page map (use #page=N to link to specific pages):\n{pages_str}"
    )
return (
    f"Compiled successfully ({pdf_path.stat().st_size // 1024}KB). "
    f"Download: {download_url}"
)
```

### Success Criteria

#### Automated Verification:
- [x] `compile_notes("master")` returns a string containing "Page map" with correct page numbers
- [x] `_parse_page_map()` correctly parses the .aux file and returns a non-empty dict (30 entries)
- [x] Page numbers match what's in the actual compiled PDF (spot-check lec01=5, glossary=47)
- [x] `compile_notes("lec03")` still works unchanged (no page map for individual lectures)
- [x] Server starts without errors: `cd backend && PYTHONPATH=src python3 -c "from youlearn.tools.notebook_tools import NotebookTools; print('OK')"`

#### Manual Verification:
- [ ] Compile master via the chat agent, verify page map appears in tool result
- [ ] Spot-check 2-3 page numbers against the actual PDF

---

## Phase 2: Update system prompts for "show me" behavior

### Overview
Add instructions to the base prompt and relevant mode prompts telling the agent how to handle "show me" requests.

### Changes Required

#### 1. Add "show me" section to BASE_PROMPT
**File**: `backend/src/youlearn/modes.py`
**Changes**: Add a new section to `BASE_PROMPT` after the Rules section (after line 85)

```python
### "Show Me" Requests
When the student asks to "show me" something (e.g., "show me lecture 3", "show me the glossary", "show me the definition of compactness"):
1. Compile the **master** PDF using `compile_notes("master")` — always the full notebook, never individual lectures
2. The tool will return a page map showing which page each section starts on
3. Find the most relevant section in the page map for what the student asked about
4. Give them the PDF URL with `#page=N` appended, e.g.: `{url}#page=15`
5. Briefly describe what they'll find on that page

The `#page=N` fragment makes the browser open the PDF directly at that page. Always use the full master PDF URL with the page fragment — never link to individual lecture PDFs for "show me" requests.

Examples:
- "Show me lecture 3" → compile master, find "Lecture 3: ..." in page map, respond with URL#page=N
- "Show me the glossary" → compile master, find "Glossary" in page map, respond with URL#page=N
- "Show me compactness" → compile master, find the lecture covering compactness, respond with URL#page=N for that lecture's page
```

#### 2. Remove "don't compile" restrictions for "show me"
**File**: `backend/src/youlearn/modes.py`
**Changes**: In the `/Lec` mode prompt (line 141) and `/Work` mode prompt (line 208), soften the "never compile" rules to allow "show me" as an exception.

In `/Lec` mode, change:
```
- Never compile unless the student asks
```
to:
```
- Never compile unless the student asks or says "show me"
```

In `/Work` mode, change:
```
- Don't compile unless asked
```
to:
```
- Don't compile unless asked or the student says "show me"
```

### Success Criteria

#### Automated Verification:
- [x] Server starts without errors after prompt changes
- [x] `build_system_prompt("default", "", "Math 104")` contains "Show Me" section
- [x] All mode prompts still render correctly

#### Manual Verification:
- [ ] In default mode, say "show me lecture 3" — agent compiles master and returns URL with #page=N
- [ ] In /Lec mode, say "show me what we have so far" — agent compiles and returns page-specific link
- [ ] In /Rev mode, say "show me the glossary" — agent returns glossary page link
- [ ] Clicking the URL in the browser opens the PDF at the correct page

---

## Testing Strategy

### Manual Testing Steps:
1. Start the backend: `cd backend && make server`
2. Send a chat message: "show me lecture 1" — verify agent calls `compile_notes("master")`, gets page map, returns URL with `#page=5`
3. Send: "show me the assignments" — verify URL has `#page=34`
4. Send: "show me the definition of compactness" — verify agent picks the lecture covering compactness (lec05) and returns `#page=29`
5. Open returned URL in browser — verify it scrolls to the correct page
6. Send: "show me lecture 3" in /Lec mode — verify compilation still happens despite "/Lec" mode
7. Verify `compile_notes("lec03")` still works normally (no page map, plain URL)

### Edge Cases:
- "Show me everything" → agent should return URL with `#page=1` (beginning)
- "Show me" with no specific target → agent should compile and return URL to beginning
- Agent already compiled recently → should still recompile (content may have changed)
- New lecture created then "show me" → page map should include the new lecture

## References

- .aux file format: Standard LaTeX output, `\contentsline` entries with page numbers
- `#page=N` fragment: Supported by all major browsers' PDF viewers (Chrome, Firefox, Edge, Safari)
- Current compilation: `notebook_tools.py:262-353`
- Current system prompts: `modes.py:36-261`
- Master structure: `master.tex:1-185`
