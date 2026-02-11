# Grid Reader - Technical Specification

This document specifies the Grid Reader application at a level of detail sufficient to reproduce it from scratch.

---

## 1. Overview

**Grid Reader** is a web-based Times Cryptic crossword solver with interactive teaching mode. Users import PDF puzzles, solve them interactively, and learn cryptic techniques through step-by-step guidance.

### 1.1 Target Stack
- **Backend**: Flask (Python 3.9+)
- **Database**: Supabase PostgreSQL (required — no local fallback)
- **Frontend**: Static HTML/JS/CSS
- **Deployment**: Local development (Vercel planned for Phase 3)

### 1.2 Key Principles
1. **Progressive Discovery Teaching**: This is a TEACHING app, not a solution viewer. Users should DISCOVER the clue breakdown step-by-step through guided interaction, NOT see the full decode revealed upfront. Each step requires user engagement before revealing the next insight.
2. **Template-Based Architecture**: All clues are represented using predefined step templates that can be combined to construct ANY cryptic clue. Each metadata step type maps 1:1 to a render template in `render_templates.json`. New templates are added incrementally as vertical slices. This enables both human teaching AND future automated annotation (a solver that generates metadata from cold clues).
3. **Stateless Client Architecture**: The trainer UI (`trainer.js`) is a **thin, stateless rendering layer with ZERO local state**. ALL state lives on the server in `training_handler.py`. The client only renders what the server sends—it never decides what to show or maintain any state variables.
4. **No AI/LLM**: Teaching mode uses pre-annotated step data from imported JSON files, NOT dynamically generated explanations.
5. **Server-Driven Rendering**: Client receives a `render` object and displays it - nothing more.

---

## 2. Teaching Philosophy: Progressive Discovery

### 2.1 Design Goal
**Grid Reader is a TEACHING APP, not a solution viewer.**

The end user experience should be:
- Users DISCOVER the clue breakdown through guided interaction
- Each step reveals ONE insight at a time
- Users must engage (tap words, type answers, make choices) before progressing
- The full solution is NEVER displayed all at once

### 2.2 Anti-Pattern: Reveal-All Display
❌ **WRONG:** Showing the full clue breakdown upfront like this:
```
DEFINITION: "Embankment" = ASWAN DAM
CONTAINER: "lengthened with" tells us A takes B inside
  A: "architect" → ADAM (Robert Adam was a famous British architect)
  B: "cob?" → SWAN (A cob is a male swan)
ASSEMBLY: A + (SWAN) + DAM = ASWAN DAM ✓
```

This defeats the purpose of teaching. The user sees the answer without thinking.

### 2.3 Correct Pattern: Step Menu with Inline Expansion
✓ **CORRECT:** Show a roadmap with inline expansion — steps expand/collapse in place:

**Initial Screen - Step Menu (all collapsed):**
```
┌─────────────────────────────────────────────┐
│ 17D: Embankment architect lengthened       │
│      with cob? (5,3)                        │
├─────────────────────────────────────────────┤
│ Answer: [ ][ ][ ][ ][ ] [ ][ ][ ]          │
├─────────────────────────────────────────────┤
│ Steps to solve:                             │
│                                             │
│ ● 1. Find the definition              ▶    │
│ ○ 2. Identify the wordplay                  │
│ ○ 3. Find the container indicator            │
│ ○ 4. Find the outer part                    │
│ ○ 5. Find the inner part                    │
│ ○ 6. Build the answer                       │
└─────────────────────────────────────────────┘
```

**User clicks active step chevron → Expands inline:**
```
│ ● 1. Find the definition              ▼    │
│   ┌─────────────────────────────────┐       │
│   │ [Embankment] [architect] ...    │       │
│   │ Tap the definition words    💡  │       │
│   │ Every cryptic clue contains...  │       │
│   └─────────────────────────────────┘       │
```

**User taps correct word → Step completes, next activates:**
```
│ ✓ 1. Definition found: 'Embankment'        │
│   Can you find a word (5,3) meaning...      │
│ ● 2. Identify the wordplay              ▶    │
│ ○ 3. Find the container indicator            │
│ ○ 4. Find the outer part                    │
```

**Progressive completion:** User works through each step sequentially. Completed steps show green ✓ with completion text. Only after all steps are completed does the completion view appear.

### 2.4 Implementation Status
✅ **Current State (v2 — Redesigned Engine):** The trainer engine has been redesigned from ~4,400 lines to ~550 lines. It uses a simple sequencer with flat steps and render templates stored in external JSON. Steps are collapsed by default and require a click to expand. Each step requires user interaction (tap words, type answers, or choose from options) before advancing. The step menu shows inline expansion — no separate screens.

**Implemented vertical slices:**
- Slice 1: `definition` step (tap_words)
- Slice 2: `wordplay_type` step (multiple_choice — identify the wordplay technique)
- Slice 3: `indicator` step (tap_words — `indicator_type` field drives type-specific menuTitle, prompt, intro, completedTitle)
- Slice 4: `outer_word` and `inner_word` steps (tap_words)
- Slice 5: `fodder` step (tap_words — identify the word being operated on)
- Slice 6: `assembly` step (multi-phase assembly with transforms, auto-skip when last transform equals answer)

### 2.5 Design Rules
1. **One insight per interaction** - Never reveal multiple facts simultaneously
2. **Require engagement** - Users must tap, type, or choose before advancing
3. **Build incrementally** - Each step builds on previous discoveries
4. **Celebrate progress** - Completed steps show green ✓ with completion text
5. **Delayed gratification** - Full solution only visible at the end

---

## 3. System Architecture

**Critical Principle: Thin Stateless Client**

The trainer UI is a **dumb rendering layer**. It has ZERO logic, ZERO decisions, ZERO state. It only:
1. Receives `render` object from server
2. Displays exactly what `render` says
3. Sends user input back to server
4. Repeats

ALL intelligence lives on the server. The client is a pure view layer.

```
┌─────────────────────────────────────────────────────────────┐
│                Browser (Client) - NO STATE                   │
├─────────────────────────────────────────────────────────────┤
│  crossword.js          │  trainer.js                        │
│  - Grid UI             │  - THIN STATELESS RENDERER         │
│  - Keyboard navigation │  - Receives render object          │
│  - localStorage cache  │  - Displays what server sends      │
│                        │  - Sends user input to server      │
│                        │  - NO decisions, NO state          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Flask Server (8080)                        │
├─────────────────────────────────────────────────────────────┤
│  crossword_server.py (infrastructure routes)                │
│  ├── /, /status, /upload, /puzzles, /validate              │
│  └── puzzle_store_supabase.py → Supabase PostgreSQL        │
├─────────────────────────────────────────────────────────────┤
│  trainer_routes.py (~150 lines, thin HTTP layer)             │
│  ├── /trainer/start       → training_handler                │
│  ├── /trainer/input       → training_handler                │
│  ├── /trainer/reveal      → training_handler                │
│  ├── /trainer/check-answer→ training_handler                │
│  └── /trainer/ui-state    → training_handler                │
├─────────────────────────────────────────────────────────────┤
│  training_handler.py (~1100 lines, ALL trainer logic)       │
│  ├── lookup_clue()     (lazy-load from Supabase by key)     │
│  ├── RENDER_TEMPLATES  (loaded from render_templates.json)  │
│  ├── _sessions dict    (all UI state + clue_data per session│
│  ├── get_clue_data()   (read clue_data from active session) │
│  ├── get_render()      (build render object from state)     │
│  ├── handle_input()    (validate & advance step)            │
│  └── _handle_assembly_input() (multi-phase assembly)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage                              │
├─────────────────────────────────────────────────────────────┤
│  Supabase PostgreSQL (required)                             │
│  - publications                                             │
│  - puzzles                                                  │
│  - clues (+ training_metadata JSONB column)                 │
│  - user_progress                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Data Models

### 4.1 Puzzle Structure
```json
{
  "puzzle": {
    "grid": {
      "rows": 15,
      "cols": 15,
      "layout": [[0,1,0,...], ...],  // 0=black, 1=white
      "cellNumbers": [[1,null,2,...], ...]
    },
    "clues": {
      "across": [{"number": 1, "text": "Clue text (5)", ...}],
      "down": [...]
    },
    "numbering": {
      "across": [{"number": 1, "row": 1, "col": 1, "length": 5}, ...],
      "down": [...]
    }
  }
}
```

### 4.2 Clue Metadata Format (Flat Steps)

**Key Principle:** We control this metadata format completely. It's our own design, optimized for interactive teaching. The format uses flat steps — no nesting, no phases within steps (except `assembly` which has sub-phases for transforms).

**Flat Step Architecture:**
- Steps are a flat array in training metadata — each step is one student interaction
- Each step has a `type` field that maps 1:1 to a render template in `render_templates.json`
- Render templates define inputMode, prompt, intro, hint, and onCorrect text
- New templates are added incrementally as vertical slices
- Templates are stored external to code in `render_templates.json` (auto-reloads on change)

**Example: Container Clue (17D — ASWAN DAM)**
```json
{
  "training_items": {
    "times-29453-17d": {
      "id": "times-29453-17d",
      "clue": "Embankment architect lengthened with cob?",
      "number": "17D",
      "enumeration": "5,3",
      "answer": "ASWAN DAM",
      "words": ["Embankment", "architect", "lengthened", "with", "cob"],
      "clue_type": "standard",
      "difficulty": { "definition": "medium", "wordplay": "hard", "overall": "hard" },
      "steps": [
        {
          "type": "definition",
          "indices": [0],
          "position": "start",
          "hint": "A famous structure on the Nile river"
        },
        {
          "type": "indicator",
          "indices": [2],
          "hint": "'Lengthened' is a container indicator — it tells you one word gets stretched by putting letters inside it."
        },
        {
          "type": "outer_word",
          "indices": [1],
          "hint": "The indicator tells you this word gets stretched — which one wraps around the other?"
        },
        {
          "type": "inner_word",
          "indices": [4],
          "hint": "Which remaining word gets placed inside?"
        },
        {
          "type": "assembly",
          "intro": "You've found the container parts. Now work out what each clue word really means — the raw words almost never appear directly in the answer.",
          "transforms": [
            { "role": "outer", "indices": [1], "type": "synonym", "result": "ADAM",
              "hint": "Robert Adam was a famous British architect" },
            { "role": "inner", "indices": [4], "type": "synonym", "result": "SWAN",
              "hint": "A male swan is called a cob" }
          ],
          "result": "ASWAN DAM"
        }
      ]
    }
  }
}
```

**Step Data Fields:**
- `type` (required): Maps to render template in `render_templates.json`
- `indices` (for tap_words steps): Word positions (0-indexed) into the `words` array
- `hint`: Per-step hint text revealed via 💡 lightbulb
- `position`: For definition steps — "start" or "end"
- `expected` (for multiple_choice steps): The correct option string
- `options` (for multiple_choice steps): Array of option strings to display
- `transforms`: For assembly steps — array of `{role, indices, type, result, hint}`
- `result`: For assembly steps — the assembled answer

**Step metadata fields** (beyond type/indices/hint):
- `indicator_type`: For indicator steps — the type of indicator (container, anagram, deletion, reversal, ordering, letter_selection, hidden_word). Used by the template for type-specific prompt, intro, menuTitle, and completedTitle via `{indicatorType}` variable and dict-keyed lookup.
- `failMessage`: Overrides the default assembly fail message

**Why This Flat Format:**
1. **Simple:** No nesting, no phases — each step is one interaction
2. **Teachable:** Each step maps directly to one render template
3. **Data-driven:** All hints, expected answers, and prompts come from the metadata + template
4. **Composable:** Container clues use 6 steps; charades use different combinations; deletion/reversal chains use yet another
5. **Self-contained:** Includes all data needed for validation and teaching

### 4.2.3 Clue Metadata Reference

**Top-level fields:**
```
clue (string), number, enumeration, answer, words (array matching clue text exactly),
clue_type, difficulty ({definition, wordplay, overall}), steps (array)
```

**Step types and flows:**
- Step 1 always: `definition` (tap_words) — indices, position, hint
- Step 2 depends on clue:
  - WITH indicators → `indicator` (tap_words) — can have multiple indicator steps per clue
  - WITHOUT indicators → `wordplay_type` (multiple_choice) with expected, options, hint
- Then type-specific steps: `fodder`, `outer_word`, `inner_word` (all tap_words)
- Final step: `assembly` with intro, failMessage, transforms array, result
- Each transform: `{role, indices, type, result, hint}` — type is synonym/abbreviation/literal/reversal/deletion/anagram/container/letter_selection/homophone
- Transforms can optionally have `lookup: {word, url}` for dictionary links

**Structural rules:**
- Every dependent transform (reversal/deletion/anagram/container) in the assembly MUST have a matching indicator step — `test_indicator_coverage` enforces this
- Never add `prompt` fields to individual steps or transforms in training metadata — all prompts come from `render_templates.json`
- Indicator steps must have `indicator_type` field (container, anagram, deletion, reversal, ordering, letter_selection, hidden_word, homophone) — the template uses this for type-specific text
- Indicator type equivalences: `hidden_word` covers `reversal`
- Container insertions use transform type `container` (not `anagram`)
- Indicator indices must be ONLY the indicator word itself, not connectors like "by", "with", "in"
- Indicator hints must NOT repeat the indicator type label — the `completedTitle` template already prefixes with `{indicatorType} indicator:`
- Transform `type` must be accurate: use "abbreviation" not "synonym" for standard cryptic mappings
- `words` array must exactly match the clue text (case, spelling, punctuation including —)
- When a compound transform is needed, break it into a chain of simple transforms
- Transform `role` fields are formatted for display automatically (`part2a` → `Part 2a`, `outer` → `Outer`)

**Reference clues — study these BEFORE editing any clue:**
- **5D** — deletion + reversal chain (indicator steps, tap_words flow)
- **1A** — container (definition → indicator → outer_word → inner_word → assembly)
- **17D** — container (same pattern as 1A)
- **4A** — pure charade (no indicators, multiple_choice wordplay_type step)
- **25A** — pure charade (same pattern as 4A)
- **6D** — charade with ordering indicator ("after")
- **22A** — charade with anagram indicator ("taking")
- **26A** — charade with reversal + container indicators ("back", "in")
- **28A** — charade with reversal chain (CA + RASE→reversed→ESAR)
- **18D** — charade with reversal of compound (FLEE + G+NIT→reversed→TING)
- **12A** — anagram with fodder pieces (literal parts + final anagram)
- **23D** — hidden reversed word with dictionary lookup on transform

**Current Render Templates (7):**

| Template | inputMode | Purpose |
|----------|-----------|---------|
| `definition` | `tap_words` | Find the definition at start/end of clue |
| `wordplay_type` | `multiple_choice` | Identify the type of wordplay (Charade, Container, Anagram, etc.) |
| `indicator` | `tap_words` | Find indicator word — `indicator_type` field drives type-specific prompt, intro, menuTitle, completedTitle |
| `outer_word` | `tap_words` | Identify which word wraps around (container clues) |
| `inner_word` | `tap_words` | Identify which word goes inside (container clues) |
| `fodder` | `tap_words` | Identify the word being operated on by an indicator |
| `assembly` | `assembly` | Multi-phase: transforms then assembly check (used for containers, charades, and other types) |

More templates will be added as new clue types are implemented.

### 4.2.1 Critical: Template System Enables Automated Annotation

**Why This Template-Based Architecture Matters:**

The template system is not just for displaying pre-annotated clues. It's the foundation for **automated clue annotation**.

**Future Capability: Cold Clue Solver**
We will build a solver that takes:
- **Input:** A "cold" clue (never seen before) + optionally the answer
- **Output:** Complete clue metadata in our flat step format

**Example Workflow:**
```
INPUT:
  Clue: "Embankment architect lengthened with cob? (5,3)"
  Answer: "ASWAN DAM" (optional)

SOLVER PROCESS:
  1. Identify clue type → Container
  2. Find definition → "Embankment" (index 0)
  3. Parse indicator → "lengthened" (index 2)
  4. Identify outer/inner → "architect" (outer), "cob" (inner)
  5. Discover transforms → architect→ADAM, cob→SWAN
  6. Verify assembly → A(SWAN)DAM = ASWAN DAM

OUTPUT (generated flat steps):
{
  "steps": [
    {"type": "definition", "indices": [0], "position": "start", "hint": "..."},
    {"type": "indicator", "indices": [2], "hint": "..."},
    {"type": "outer_word", "indices": [1], "hint": "..."},
    {"type": "inner_word", "indices": [4], "hint": "..."},
    {"type": "assembly",
     "transforms": [
       {"role": "outer", "indices": [1], "type": "synonym", "result": "ADAM", "hint": "..."},
       {"role": "inner", "indices": [4], "type": "synonym", "result": "SWAN", "hint": "..."}
     ],
     "result": "ASWAN DAM"}
  ]
}
```

**Why Flat Steps Make This Possible:**
1. **Finite Set:** Small number of render templates to generate from
2. **Deterministic:** Each template has clear input/output structure
3. **Composable:** Complex clues are just combinations of simple flat steps
4. **Reusable:** Same templates work for thousands of clues
5. **Validatable:** Generated metadata follows exact schema
6. **1:1 Mapping:** Each metadata step type maps to exactly one render template

**Design Implication:**
Every template must be:
- **Machine-generatable:** Can be produced by algorithmic parsing
- **Complete:** Contains all data needed for validation and teaching
- **Unambiguous:** No ambiguity in what constitutes this step type

This is why we control the metadata format completely. We're not constrained by external schemas—we design it to be both human-teachable AND machine-generatable.

### 4.2.2 The Two-Layer Template System

**Critical Architecture:** Each step `type` in clue metadata maps 1:1 to a render template in `render_templates.json`.

**Templates Stored EXTERNAL TO CODE:**
- **Render Templates:** `render_templates.json` — auto-reloaded by `training_handler.py` when file changes
- **Clue Metadata:** Supabase `clues.training_metadata` column. Lazy-loaded per request — no restart needed.
- **Why external:** Templates and clue data must be editable without code changes

**The Two-Layer System:**

```
LAYER 1: Clue Step Metadata (Supabase training_metadata)
  └─ Clue-specific data: which words (indices), expected answers, hints
  └─ Flat array of steps — no nesting
  └─ Example: {"type": "definition", "indices": [0], "position": "start", "hint": "..."}
           │
           │ 1:1 mapping (by step "type") ↓
           │
LAYER 2: Render Template (render_templates.json)
  └─ Generic presentation: inputMode, prompt, intro, hint, onCorrect
  └─ Uses {variable} placeholders resolved from clue data
  └─ Example: {"inputMode": "tap_words", "prompt": "Tap the definition words", ...}
```

**How It Works:**

1. **Clue metadata defines WHAT** (clue-specific data):
   - Which word indices to tap (`indices`)
   - What the expected answer is (indices for tap_words, result for assembly)
   - Per-step hint text for the 💡 lightbulb

2. **Render template defines HOW** (generic presentation):
   - Input mode (`tap_words`, `multiple_choice`, or `assembly`)
   - Prompt text, intro text, hint text (with {variable} substitution)
   - Menu titles (before/after completion)
   - Completion message (`onCorrect`)
   - For indicator steps: `indicator_type` drives type-specific text via dict-keyed lookup and `{indicatorType}` variable
   - Assembly steps can override `failMessage`

**Variable Substitution:**
Templates use `{variable}` placeholders resolved from step + clue data:
- `{words}` → joined clue words at step indices
- `{enumeration}` → answer length pattern
- `{hint}` → step hint text
- `{position}` → definition position (start/end)
- `{result}` → step result
- `{expected}` → expected answer (for multiple_choice steps)
- `{indicatorType}` → indicator type from step metadata, display form (e.g. "letter selection" from "letter_selection")

**Example: Definition Step**

**Clue metadata** (in Supabase `training_metadata`):
```json
{"type": "definition", "indices": [0], "position": "start", "hint": "A famous structure on the Nile river"}
```

**Render template** (in `render_templates.json`):
```json
{
  "inputMode": "tap_words",
  "prompt": "Tap the definition words",
  "menuTitle": "Find the definition",
  "completedTitle": "Definition found: '{words}'",
  "intro": "Every cryptic clue contains a straight definition...",
  "expected_source": "indices",
  "onCorrect": "Can you find a word ({enumeration}) meaning '{words}' — {hint}."
}
```

**Current Render Template Inventory:**

| Step Type (metadata) | Render Template | inputMode | Purpose |
|----------------------|-----------------|-----------|---------|
| `definition` | `definition` | `tap_words` | Find definition |
| `wordplay_type` | `wordplay_type` | `multiple_choice` | Identify wordplay technique |
| `indicator` | `indicator` | `tap_words` | Find indicator word — `indicator_type` drives type-specific text |
| `outer_word` | `outer_word` | `tap_words` | Identify outer word (container clues) |
| `inner_word` | `inner_word` | `tap_words` | Identify inner word (container clues) |
| `fodder` | `fodder` | `tap_words` | Identify word being operated on |
| `assembly` | `assembly` | `assembly` | Coaching context, parallel transforms, combined letter entry |

More templates will be added as new clue types are implemented (anagrams, hidden words, etc.).

**Why This Separation Matters:**
1. **Reusability:** Same template works for thousands of different clues
2. **Maintainability:** Update UI behavior once, affects all clues using that template
3. **Validation:** Template's `expected_source` defines what input is validated against
4. **Future-proofing:** Can change templates without re-annotating clues
5. **Thin Client:** Client has no state—everything comes from server's render object
6. **No code changes needed:** Both templates and clue data auto-reload from JSON files

### 4.3 Session State (server-side)
```python
_sessions[clue_id] = {
    "clue_id": clue_id,         # Clue identifier
    "step_index": 0,            # Current step in flat steps array
    "completed_steps": [],      # Indices of completed steps
    "selected_indices": [],     # Selected word indices (tap_words)
    "hint_visible": False,      # Hint panel shown
    "step_expanded": False,     # Active step expanded (collapsed by default)
    "user_answer": [],          # Letters typed in answer boxes
    "answer_locked": False,     # True when answer confirmed
    "highlights": [],           # Word highlights [{indices, color, role}]
    "assembly_transforms_done": {},  # Completed transforms: {index: result}
    "assembly_hint_index": None,     # Which transform hint is showing (or None)
}
```

**State resets on step advance:** `selected_indices`, `hint_visible`, `step_expanded`, `assembly_transforms_done`, `assembly_hint_index` are all reset when `step_index` increments. `user_answer` and `highlights` persist across steps.

---

## 4.4 Stateless Client Architecture (Critical Principle)

**The Golden Rule: Client Has ZERO State**

The trainer UI (`trainer.js`) is intentionally designed as a **thin, stateless rendering layer**. This is a non-negotiable architectural constraint.

**What the Client Does NOT Have:**
- ❌ No state variables (`this.selectedIndices`, `this.userAnswer`, `this.hintVisible`, etc.)
- ❌ No decision logic (doesn't decide what to show next)
- ❌ No business logic (doesn't validate answers)
- ❌ No step progression logic (doesn't know when to advance)
- ❌ No template knowledge (doesn't know how steps work)

**What the Client ONLY Does:**
- ✅ Receives complete `render` object from server
- ✅ Displays exactly what `render` specifies (text, colors, inputs, panels)
- ✅ Attaches event handlers that send user input to server
- ✅ Receives new `render` object from server
- ✅ Replaces entire UI with new render
- ✅ Repeats

**Server is Source of Truth:**
ALL state lives in `training_handler._sessions[clue_id]`:
- Current step index
- Assembly phase index
- User's answers
- Word selections
- Hint visibility
- Answer locked status

**Why This Matters:**
1. **No Sync Bugs:** Server is single source of truth—no client/server drift
2. **Refreshable:** Browser refresh doesn't lose state (can reload from server)
3. **Testable:** Just test API responses—no client logic to test
4. **Debuggable:** Inspect session state on server—no hidden client state
5. **Future-Proof:** Can persist session state to database without client changes
6. **Multi-Device:** Same session could be resumed on different device

**Anti-Pattern to Avoid:**
```javascript
// ❌ WRONG - Client maintaining state
class Trainer {
  constructor() {
    this.selectedIndices = [];  // NO! State belongs on server
    this.hintVisible = false;   // NO! State belongs on server
  }

  selectWord(index) {
    this.selectedIndices.push(index);  // NO! Server decides this
  }
}
```

**Correct Pattern:**
```javascript
// ✅ CORRECT - Client only renders
class Trainer {
  render(renderObj) {
    // Display exactly what renderObj specifies
    this.displayWords(renderObj.words);
    this.highlightIndices(renderObj.highlights);
    this.showActionPrompt(renderObj.actionPrompt);
    // No state stored—just pure rendering
  }

  onWordClick(index) {
    // Send to server, get new renderObj back
    fetch('/trainer/input', {body: {input: [index]}})
      .then(r => r.json())
      .then(renderObj => this.render(renderObj));
  }
}
```

---

## 5. Training Flow

### 5.1 Step Types

**See section 4.2.2 for the complete metadata → render template mapping.**

The engine uses a simple sequencer with flat steps. Each step type has one interaction (except `assembly` which has sub-phases). Current templates:

| Type | inputMode | Description |
|------|-----------|-------------|
| `definition` | `tap_words` | Find definition at start/end of clue |
| `wordplay_type` | `multiple_choice` | Identify the wordplay technique (Charade, Container, etc.) |
| `indicator` | `tap_words` | Find indicator word — `indicator_type` drives type-specific text |
| `outer_word` | `tap_words` | Identify the outer (wrapping) word |
| `inner_word` | `tap_words` | Identify the inner (inserted) word |
| `fodder` | `tap_words` | Identify the word being operated on by an indicator |
| `assembly` | `assembly` | Coaching context, parallel transforms, combined letter entry |

**Assembly Layout:**
The `assembly` step has its own sub-state tracked by `assembly_phase` and `assembly_transforms_done` in session state. The layout shows:
1. **Definition line**: Reminds student what they're looking for (template: `definitionLine` with `{enumeration}`, `{definitionWords}`)
2. **Indicator line**: For containers, shows piece layout with roles (template: `indicatorLine` with `{indicatorWords}`, `{innerWords}`, `{outerWords}`). Empty for charades/chains.
3. **Fail message**: Shows that raw clue words don't work (step metadata can override via `failMessage`)
4. **Transform prompts**: Role-labelled coaching prompts from `transformPrompts` in `render_templates.json`. All transforms are always active — no locking. The student sees the full plan and works through them in any order. Each has its own hint lightbulb.
5. **Combined result display**: Editable letter inputs grouped by transform with `+` separators based on `positionMap`. Cross letters shown as overwritable placeholders. Check button submits all filled groups.
6. **Assembly check**: **Auto-skipped** when the last transform result equals the final answer (avoids redundant retyping).

### 5.2 Input Modes

| Mode | User Action | Validation |
|------|-------------|------------|
| `tap_words` | Tap word chips in clue | Check selected indices match `step.indices` |
| `multiple_choice` | Click one of the option buttons | Case-insensitive string match against `step.expected` |
| `text` | Type in a text input | Stripped uppercase comparison against expected |
| `assembly` | Type in letter boxes (transforms then assembly) | Sequential transform validation then final result check |

### 5.3 Render Object Structure

**The Complete Truth:** This object contains EVERYTHING the client needs to render the UI. The client has NO other data sources, NO local state, NO decision-making logic.

```json
{
  "clue_id": "times-29453-17d",
  "words": ["Embankment", "architect", "lengthened", "with", "cob"],
  "answer": "ASWAN DAM",
  "enumeration": "5,3",
  "complete": false,
  "stepExpanded": true,
  "highlights": [{"indices": [0], "color": "GREEN", "role": "definition"}],
  "selectedIndices": [2],
  "userAnswer": [],
  "answerLocked": false,
  "steps": [
    {"index": 0, "type": "definition", "title": "Definition found: 'Embankment' — can you find a 5,3-letter word for this?",
     "status": "completed", "completionText": "Can you find a word (5,3) meaning 'Embankment'..."},
    {"index": 1, "type": "indicator", "title": "Indicator found: 'lengthened' — ...",
     "status": "active", "completionText": null},
    {"index": 2, "type": "outer_word", "title": "Find the outer part",
     "status": "pending", "completionText": null},
    {"index": 3, "type": "inner_word", "title": "Find the inner part",
     "status": "pending", "completionText": null},
    {"index": 4, "type": "assembly", "title": "Build the answer",
     "status": "pending", "completionText": null}
  ],
  "currentStep": {
    "index": 1,
    "type": "indicator",
    "inputMode": "tap_words",
    "prompt": "Tap the indicator word",
    "intro": "Look for a word that signals what to do with the other words — the indicator.",
    "hint": "The indicator often disguises itself...",
    "hintVisible": false,
    "lookup": {"word": "lengthened", "url": "https://www.merriam-webster.com/dictionary/lengthened"}
  }
}
```

**Assembly Step adds `assemblyData` to currentStep:**
```json
{
  "assemblyData": {
    "phase": "transform",
    "definitionLine": "You're looking for a 5,3-letter word meaning 'Embankment'",
    "indicatorLine": "'lengthened' tells us 'cob' (inner) goes inside 'architect' (outer)",
    "failMessage": "Try putting 'architect' and 'cob' together — it doesn't spell anything useful...",
    "transforms": [
      {"index": 0, "role": "outer", "clueWord": "architect", "prompt": "outer, 'architect', has a 4-letter synonym",
       "letterCount": 4, "status": "active", "result": null, "hint": "Robert Adam was...", "hintVisible": false},
      {"index": 1, "role": "inner", "clueWord": "cob", "prompt": "inner, 'cob', has a 4-letter synonym",
       "letterCount": 4, "status": "active", "result": null, "hint": "A male swan...", "hintVisible": false}
    ],
    "resultParts": [5, 3],
    "positionMap": {"0": [0, 4, 5, 6, 7], "1": [1, 2, 3]},
    "completedLetters": [null, null, null, null, null, null, null, null]
  }
}
```

**Client Behavior:**
- Receives this object via `/trainer/start`, `/trainer/input`, `/trainer/ui-state`, `/trainer/check-answer`, `/trainer/reveal` endpoints
- Renders exactly what the object specifies—no interpretation, no decisions
- When user interacts, sends raw input to server, receives new render object
- Replaces entire UI state with new render object

---

## 6. UI Specifications

### 6.1 Step Menu (Inline Expansion)

**Purpose:** Single-screen UI where steps are listed as a roadmap with inline expansion. The active step expands/collapses in place — no separate screens.

**Layout (collapsed — initial state):**
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: 17D Embankment architect lengthened with cob? (5,3) │
│                                                          [X] │
├─────────────────────────────────────────────────────────────┤
│ ANSWER BOXES                      [Check] [Reveal]          │
│ [ ][ ][ ][ ][ ] [ ][ ][ ]                                   │
├─────────────────────────────────────────────────────────────┤
│ Steps to solve:                                             │
│                                                             │
│ ● 1. Find the definition                              ▶    │
│ ○ 2. Find the container indicator                            │
│ ○ 3. Find the outer word                                    │
│ ○ 4. Find the inner word                                    │
│ ○ 5. Put it together                                        │
└─────────────────────────────────────────────────────────────┘
```

**Layout (expanded — active step clicked):**
```
│ ● 1. Find the definition                              ▼    │
│   ┌─────────────────────────────────────────────┐           │
│   │ [Embankment] [architect] [lengthened] ...    │           │
│   │ Tap the definition words                💡  │           │
│   │ Every cryptic clue contains a straight...   │           │
│   └─────────────────────────────────────────────┘           │
│ ○ 2. Find the container indicator                            │
```

**State Indicators:**
- ○ = Pending (gray hollow circle)
- ● = Active (blue filled circle)
- ✓ = Completed (green checkmark)
- ▶ = Collapsed (click to expand)
- ▼ = Expanded

**Behavior:**
1. Active step starts collapsed — user clicks chevron to expand
2. Expanded step shows word chips, prompt, intro, hint 💡
3. On correct input → step completes, next step becomes active (collapsed)
4. Completed steps show green ✓ with completion text below
5. Answer boxes always visible at top, editable until locked
6. When all steps completed → completion view

**Data Source:**
- Step list generated by `_build_step_list()` from `clue["steps"]` array
- Step titles from render template `menuTitle` / `completedTitle` (with {variable} substitution)
- `stepExpanded` flag in session state controls active step visibility

### 6.3 Assembly Step Detail

The `assembly` step has a multi-phase inline UI (used for containers, charades, and other clue types):

```
│ ● 6. Build the answer                                 ▼    │
│   ┌─────────────────────────────────────────────────┐       │
│   │ Here's a key cryptic trick: the words in the    │       │
│   │ clue almost never appear directly in the answer.│       │
│   │                                                 │       │
│   │ ⚠️ Try putting 'architect' and 'cob' together   │       │
│   │   — it doesn't spell anything useful, does it?  │       │
│   │                                                 │       │
│   │ ✓ 'architect' → ADAM                            │       │
│   │                                                 │       │
│   │ 'cob' is a clue to a 4-letter word.       💡   │       │
│   │ What's it pointing to?                          │       │
│   │ [ ][ ][ ][ ]  [Check]                           │       │
│   │                                                 │       │
│   │ ○ Now combine them (pending)                    │       │
│   └─────────────────────────────────────────────────┘       │
```

**Assembly Sub-phases:**
1. **Fail message** (amber): Shows raw words don't combine to anything
2. **Transform inputs** (sequential, blue): Active transform shows letter boxes + hint 💡; completed transforms show green ✓ with result; pending transforms are grayed out
3. **Assembly check** (purple): Letter tiles with word spacing + Check Answer button

### 6.4 Completion View

**Trigger:** When all steps completed (`step_index >= len(steps)`) OR Reveal button clicked.

**Implementation:** `_build_completion()` returns render with `complete: true`, `currentStep: None`. The client renders a green gradient header with the answer, all step summaries with their completion text, and an "Update Grid" button.

**Entry Points:**
1. Natural completion: `step_index >= len(steps)` in `get_render()`
2. Reveal button: `reveal_answer()` sets `step_index` past end, locks answer

### 6.5 Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Word highlight (completed steps) | Green | #22c55e |
| Cross letter border | Blue | #3b82f6 |
| Locked answer | Green | #16a34a |
| Incorrect flash | Red | #ef4444 |

---

## 7. API Endpoints

### 7.1 POST /trainer/start
Start a new training session. Triggers auto-reload of `render_templates.json`, then looks up clue by text/puzzle/direction via `training_handler.lookup_clue()`.

**Request:**
```json
{
  "puzzle_number": "29453",
  "clue_number": "17",
  "direction": "down",
  "clue_text": "Embankment architect lengthened with cob?"
}
```

**Response:** Render object (see 5.3)

### 7.2 POST /trainer/input
Submit user input for validation (word taps or text).

**Request:**
```json
{
  "clue_id": "times-29453-17d",
  "value": [0]  // indices for tap_words, or "ADAM" for text/assembly
}
```

**Response:** `{"correct": true/false, "message": "Correct!", "render": {...}}`

The `message` field contains template-driven feedback text from `render_templates.json` (`feedback` section). The client displays this directly — no hardcoded feedback strings in JS.

### 7.3 POST /trainer/ui-state
Update UI state without validating (hint toggle, word selection, typing, expand step).

**Request:**
```json
{
  "clue_id": "times-29453-17d",
  "action": "toggle_hint"
}
```

**Actions:** `toggle_hint`, `select_word` (with `index`), `type_answer` (with `letters`), `expand_step`

**Response:** Updated render object

### 7.4 POST /trainer/reveal
Give up and reveal full answer.

**Request:**
```json
{
  "clue_id": "times-29453-17d"
}
```

**Response:** Completion render with `complete: true`

### 7.5 POST /trainer/check-answer
Check if typed answer is correct.

**Request:**
```json
{
  "clue_id": "times-29453-17d",
  "answer": "ASWANDAM"
}
```

**Response:** `{"correct": true/false, "message": "Correct!", "render": {...}}`

---

## 8. Files Structure

```
Grid Reader/
├── crossword_server.py      # Flask server — infrastructure routes only
├── trainer_routes.py        # Flask Blueprint — thin HTTP layer (~150 lines)
├── training_handler.py      # ALL trainer logic: clue DB, sessions, sequencer (~1120 lines)
├── puzzle_store_supabase.py # Supabase database client (required)
├── pdf_processor.py         # PDF parsing, OCR correction
├── render_templates.json    # Render templates (auto-reloaded)
├── upload_training_metadata.py  # Upload training data to Supabase
├── test_regression.py       # Fully dynamic regression tests — zero hardcoded clue data
├── validate_training.py     # Training metadata validator (4 layers — see Section 14)
├── migrations/
│   ├── 001_initial_schema.sql       # Publications, puzzles, clues, user_progress
│   └── 002_add_training_metadata.sql # training_metadata JSONB column on clues
├── static/
│   ├── crossword.js         # Grid UI, keyboard navigation
│   ├── trainer.js           # Stateless trainer UI (~800 lines)
│   └── crossword.css        # Styles
├── templates/
│   └── index.html           # Main page template
├── requirements.txt
└── .env                      # SUPABASE_URL, SUPABASE_ANON_KEY, TRAINING_SOURCE
```

---

## 9. Database Schema

### 9.1 Supabase Tables

```sql
-- Publications (Times, Guardian, etc.)
CREATE TABLE publications (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  logo_color TEXT,
  ximenean_strictness INTEGER
);

-- Puzzles (primary entity)
CREATE TABLE puzzles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  publication_id TEXT REFERENCES publications(id),
  puzzle_number TEXT NOT NULL,
  title TEXT,
  date DATE,
  grid_layout JSONB NOT NULL,
  grid_size INTEGER NOT NULL,
  UNIQUE(publication_id, puzzle_number)
);

-- Clues (belong to puzzles)
CREATE TABLE clues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  direction TEXT CHECK (direction IN ('across', 'down')),
  text TEXT NOT NULL,
  enumeration TEXT NOT NULL,
  answer TEXT,
  start_row INTEGER NOT NULL,
  start_col INTEGER NOT NULL,
  training_metadata JSONB,  -- Pre-annotated step data (words, clue_type, difficulty, steps)
  UNIQUE(puzzle_id, number, direction)
);

-- User progress (per puzzle)
CREATE TABLE user_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  grid_state JSONB NOT NULL,
  selected_cell JSONB,
  direction TEXT,
  UNIQUE(session_id, puzzle_id)
);
```

---

## 10. Behavioral Specifications

### 10.1 Step Expansion
- Active step starts collapsed (chevron ▶)
- Click chevron to expand (▼) — reveals prompt, word chips, intro, hint 💡
- `stepExpanded` flag in session state, toggled via `expand_step` UI action
- On step completion, next step starts collapsed

### 10.2 Hint System
- 💡 lightbulb icon shown for steps/transforms with hints
- Click toggles `hint_visible` in session
- Hint text from `step.hint` field in clue metadata
- For assembly transforms, each transform has its own `hint` and `hintVisible`
- Font size 1.5rem, opacity 0.75 when inactive, 1.0 when active
- Reset to hidden when advancing to next step or transform

### 10.3 Word Highlights
- Completed `tap_words` steps add highlights: `{indices, color: "GREEN", role}`
- Highlights persist across steps and accumulate
- Applied to word chips in the step menu

### 10.4 Answer Boxes
- Always visible at top of trainer modal
- Typed letters sync silently to server via `type_answer` UI action (no re-render)
- Check button validates against `clue.answer` (stripped, uppercased)
- Reveal button skips to completion, locks answer boxes
- Correct check answer locks boxes with green border

### 10.5 Multi-word Answers
Answers with spaces (e.g., "ASWAN DAM"):
- Enumeration "5,3" → 5 boxes + gap + 3 boxes
- Strip spaces for comparison (`re.sub(r'[^A-Z]', '', ...)`)
- Assembly resultParts mirrors enumeration for letter tile spacing

### 10.6 Auto-reload
Two mechanisms keep the server current during development:

**Data file reload (no restart):**
- `render_templates.json`: Server checks file mtime on each `/trainer/start` request — auto-reloads without restart
- Supabase training data: Lazy-loaded per request — always fresh, no restart needed

**Python code restart (automatic):**
- `crossword_server.py` runs with `debug=True`, which enables Werkzeug's reloader
- Any `.py` file change triggers an automatic server restart
- `render_templates.json` is also listed in `extra_files` so changes trigger a restart (belt-and-suspenders with the mtime check above)
- The reloader spawns a child process — this is normal (you'll see the startup message twice)

### 10.7 Check Answer Button
- "Check" button next to answer boxes
- Visible when answer not locked
- Sends typed letters to `POST /trainer/check-answer`
- Correct → locks answer with green styling
- Incorrect → brief red feedback, auto-clears after 1.5 seconds

### 10.8 Keyboard Input Isolation
Assembly letter inputs (`.assembly-transform-letter`, `.assembly-result-letter`) are excluded from the crossword grid's global keydown handler in `crossword.js` to prevent keystroke leaking.

### 10.9 Step Hints from Clue Metadata
Interactive step hints are sourced from the `hint` field in each step of the training metadata. No hardcoded hint strings in code. For assembly transforms, each transform has its own `hint` field.

### 10.10 Dictionary Lookup

**Purpose:** Show a dictionary icon that links to Merriam-Webster when a word lookup would help the student understand a non-obvious meaning. For example, most students know "twit" as a silly person — the MW entry reveals it's also a verb meaning "to reproach."

**Where it appears:**
1. **Definition step** — lookup the definition word(s) to show meanings the student may not know
2. **Assembly transforms** — lookup the clue word for synonym/abbreviation transforms where the connection is non-obvious

**Data model — training metadata:**

Add an optional `lookup` field to definition steps and assembly transforms:

```json
// Definition step
{
  "type": "definition",
  "indices": [0],
  "position": "start",
  "hint": "To criticize or scold someone",
  "lookup": {
    "word": "twit",
    "url": "https://www.merriam-webster.com/dictionary/twit"
  }
}

// Assembly transform
{
  "role": "outer",
  "indices": [1],
  "type": "synonym",
  "result": "STALK",
  "hint": "To 'track' someone is to follow or stalk them",
  "lookup": {
    "word": "track",
    "url": "https://www.merriam-webster.com/dictionary/track"
  }
}
```

The `lookup` field is optional — only add it when Merriam-Webster has an entry for the word. Not every step or transform needs one.

**Server → Client:**

The `lookup` object passes through to the render object unchanged:
- In `currentStep.lookup` for definition/indicator/fodder steps
- In `currentStep.assemblyData.transforms[n].lookup` for assembly transforms

No server-side logic needed beyond passing the field through (it's static metadata like `hint`).

**UI — dictionary icon:**

A small book icon (📖) rendered as a clickable link, positioned next to the existing hint `?` icon:

```
┌─────────────────────────────────────────────────────────┐
│ Tap the definition words                        [?] [📖] │
└─────────────────────────────────────────────────────────┘
```

- Icon: `📖` (or an SVG book icon) in a 20×20px circle, matching the hint `?` icon style
- Background: `#e2e8f0` (same as inactive hint)
- Clicking opens the MW URL in a new tab (`target="_blank"`)
- Visible whenever `lookup` is present on the current step or transform — no toggle state needed
- The icon is always visible (not gated behind hint reveal) because it's a reference link, not a spoiler

**Rendering rules (trainer.js):**
- After rendering the hint `?` icon, check for `step.lookup` or `transform.lookup`
- If present, render the dictionary icon as an `<a>` tag with `href` and `target="_blank"`
- Style matches the hint icon: 20×20px circle, same colours, same alignment
- No state management — it's a plain link

**When to add `lookup` to training metadata:**
- Add it wherever Merriam-Webster has an entry for the word
- Particularly valuable where the definition word has a lesser-known meaning (e.g. "twit" as verb, "see" as noun, "raven" as verb, "fugitive" as adjective)
- Also useful on synonym transforms where the connection isn't obvious
- No downside to including it whenever MW has a result — if it doesn't help, the student simply doesn't click it

---

## 11. Mobile Responsive Design

### 11.1 Grid Scaling Strategy

The crossword grid scales to fit any screen width using CSS Grid with fractional units (`1fr`), not fixed pixel sizes.

**Key Techniques:**
1. **CSS Grid with `1fr` columns**: JavaScript sets `grid-template-columns: repeat(15, 1fr)` instead of fixed pixel widths
2. **`aspect-ratio: 1` on cells**: Cells maintain square shape at any size
3. **`clamp()` for font sizes**: `font-size: clamp(0.8rem, 2.5vw, 1.4rem)` scales between min/max
4. **Viewport-based grid width**: `width: calc(100vw - 26px)` accounts for padding/borders

**Why NOT fixed pixel sizes:**
- Fixed sizes (e.g., `40px`) don't adapt to different screen widths
- Media queries with fixed breakpoints require guessing device sizes
- Viewport units (`vw`) automatically scale to any screen

### 11.2 CSS Structure

```css
/* Base cell - no fixed dimensions */
.cell {
    aspect-ratio: 1;
    font-size: clamp(0.8rem, 2.5vw, 1.4rem);
    /* ... other styles */
}

/* Desktop - fixed width for consistency */
.crossword-grid {
    width: 616px; /* 15 cells × 40px + gaps + border */
}

/* Tablet (≤800px) */
@media (max-width: 800px) {
    .crossword-grid {
        width: 100%;
        max-width: 500px;
    }
}

/* Mobile (≤600px) */
@media (max-width: 600px) {
    body { padding: 8px; }
    .puzzle-section { padding: 4px; }

    .crossword-grid {
        /* Fill screen minus padding: body 8×2 + section 4×2 + border 2 = 26px */
        width: calc(100vw - 26px) !important;
        max-width: calc(100vw - 26px) !important;
    }

    .cell-number {
        font-size: clamp(6px, 1.5vw, 10px);
    }
}
```

### 11.3 JavaScript Grid Rendering

```javascript
// crossword.js - renderGrid()
gridEl.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
gridEl.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
// NOT: `repeat(${cols}, 40px)` - this breaks responsive scaling
```

### 11.4 Trainer Modal on Mobile

```css
@media (max-width: 768px) {
    .trainer-modal-wrapper {
        width: 100%;
        height: 100vh;
        border-radius: 0;
    }

    /* Larger touch targets */
    .answer-box, .answer-box-input {
        width: 44px !important;
        height: 52px !important;
    }
}
```

### 11.5 Key Measurements

| Screen Width | Grid Width | Cell Size (approx) |
|--------------|------------|-------------------|
| 390px (iPhone) | 364px | 24px |
| 500px | 474px | 31px |
| 800px | 500px (max) | 33px |
| >800px | 616px | 40px |

---

## 12. Development Phases

### Phase 1: Supabase Database Integration ✓
- Supabase PostgreSQL backend (required — no local fallback)
- Publications, puzzles, clues, user_progress tables
- `training_metadata` JSONB column on clues table for pre-annotated step data
- `upload_training_metadata.py` script to populate database
- DB status indicator in header

### Phase 2: Interactive Teaching Mode ✓
- Redesigned training_handler.py — simple sequencer (~550 lines)
- Flat clue metadata with render templates in external JSON
- 1:1 mapping between metadata step types and render templates
- Server-driven rendering, stateless client
- Step menu with inline expansion (collapsed by default)
- Container clue full flow: definition → wordplay_type → indicator → outer/inner → assembly with transforms
- Charade clue flow: definition → wordplay_type → assembly with transforms
- Deletion/reversal chain flow: definition → indicator(s) → fodder → assembly with transforms
- Step metadata `hint` fields for clue-specific teaching text (no per-clue prompt overrides)

### Phase 3: Vercel Deployment (Planned)
- Serverless Flask on Vercel
- Environment variables for keys
- Static assets from Vercel CDN

### Phase 4: User Authentication (Planned)
- Supabase Auth (Google OAuth + email/password)
- Row-level security
- Progress tied to user accounts

### Phase 5: Multi-User Features (Planned)
- Rate limiting
- Analytics
- Security hardening

### Phase 6: Automated Clue Annotation (Future)
- Build solver that generates metadata from cold clues
- Input: Raw clue text + optional answer
- Output: Complete clue metadata using templates
- Enables scaling annotation to thousands of clues
- Validates template system completeness

**Why This Matters:**
Currently, clues must be manually annotated in Supabase training metadata. The solver will automate this process, allowing us to rapidly expand the teaching library. The template-based architecture makes this possible because we only need to generate from a finite, growing set of render templates, not infinite variations. Each generated metadata step type maps 1:1 to an existing render template.

---

## 13. Testing Checklist

### 13.1 Core Flow
- [ ] Import PDF puzzle
- [ ] Grid displays correctly
- [ ] Clue selection highlights grid cells
- [ ] Click "Solve" opens trainer

### 13.2 Trainer Flow
- [ ] Steps expand/collapse on click
- [ ] tap_words validates selection
- [ ] Correct input advances to next step
- [ ] Completed steps show green ✓ with completion text
- [ ] Assembly step transforms validate sequentially
- [ ] Assembly check validates final result
- [ ] `python3 test_regression.py` passes all tests (dynamically tests every clue in Supabase)

### 13.3 Answer Entry
- [ ] Answer boxes always visible at top
- [ ] Typing fills boxes and auto-advances
- [ ] Check button: correct → green lock, incorrect → red flash
- [ ] Reveal button skips to completion, locks answer

### 13.4 Completion
- [ ] All steps complete → completion view
- [ ] "Update Grid" applies answer and closes

### 13.5 Regression Test Suite (`test_regression.py`)

**Strategy:** Fully dynamic black-box API integration tests against a running server. Zero external dependencies (stdlib `urllib` only). Zero hardcoded clue data — the test runner discovers and tests every clue with training data in Supabase.

**Running:** `python3 test_regression.py` (server must be running on port 8080, or use `--server URL`)

#### Fully Dynamic — No Hardcoded Clue Data

The test runner fetches all clues from `/trainer/clue-ids?full=1`, builds test data from live Supabase metadata using `build_clue_test_data()`, and runs all test types against every clue. Adding training data for a new clue automatically includes it in the next test run — no regeneration or manual maintenance needed.

#### 11 Test Types Per Clue

| Test | What It Verifies |
|------|-----------------|
| **Response contract** | `/trainer/start` returns all required fields with correct types (`clue_id`, `words`, `answer`, `enumeration`, `answerGroups`, `steps`, `currentStep`) |
| **Full walkthrough** | Happy path: correct input at every step → `complete=true`, `answerLocked=true`, `userAnswer` matches |
| **Wrong input** | Wrong value at step 0 → `correct=false`, step index unchanged (no advancement) |
| **Assembly transform status** | All transforms start `active` (no locking) |
| **Check answer** | Wrong answer → rejected, `answerLocked=false`. Correct answer → accepted, `answerLocked=true` |
| **Reveal** | Reveal → all steps `completed`, `complete=true`, `answerLocked=true` |
| **Template text** | Indicator step titles contain correct `indicator_type` text; hints don't redundantly repeat indicator type label |
| **Assembly completion text** | Container clues show insertion notation; charade+anagram clues show parenthesised arrows |
| **Indicator coverage** | Every dependent transform (reversal/deletion/anagram) has a matching indicator step |
| **Assembly combined check** | Assembly combined check validates letter groups correctly |
| **Dependent prompt update** | Dependent transform prompts update after prerequisite transforms complete |

---

## Appendix A: Implementation History

1. **Supabase Integration**: Added `numbering` object to response, cross letters from grid
2. **OCR Validation**: Spell-checking for PDF import
3. **Annotation Fixes**: Align training metadata with puzzle text
4. **Multi-word Answers**: Handle spaces in answers (e.g. "ASWAN DAM")
5. **Mobile Responsive Grid**: CSS Grid with `1fr` units, `aspect-ratio: 1` cells, viewport-based sizing
6. **Engine Redesign (v2)**: Replaced ~4,400-line engine with simple sequencer, flat steps, external render templates (now ~950 lines after adding clue DB management and strict validation)
7. **Container Assembly**: Multi-phase assembly step with transforms
8. **Template Expansion**: Renamed `container_indicator` → `indicator` (generic for any indicator type), unified `container_assembly`/`charade_assembly` → `assembly`, added `wordplay_type` (multiple_choice), `fodder` (tap_words)
9. **Indicator Type System**: Indicator steps use `indicator_type` field to drive type-specific template text (menuTitle, prompt, intro, completedTitle) via dict-keyed lookup and `{indicatorType}` variable. Assembly steps can override `failMessage`.
10. **Auto-skip Assembly Check**: When last transform result equals the final answer, assembly auto-completes without redundant retyping
11. **Architecture Compliance**: Fixed all V-list violations — moved all feedback strings and display text to `render_templates.json`, eliminated silent `.get()` fallbacks (replaced with explicit `ValueError` raises), moved clue DB management and lookup logic from `trainer_routes.py` to `training_handler.py` (routes are now a thin HTTP layer). Added 72-test regression suite (`test_regression.py`): 12 clues × 6 tests covering all 7 step flow patterns, all indicator types, and all transform types.
12. **Training Data in Supabase**: Added `training_metadata` JSONB column to `clues` table via migration 002. Training handler loads from Supabase. Upload script (`upload_training_metadata.py`) populates database.
13. **Indicator Hint Deduplication**: Fixed 16 indicator hints that redundantly repeated the indicator type label (e.g. "a classic anagram indicator") — the `completedTitle` template already prefixes with the type. Added guard test in `test_template_text` to prevent regression.
14. **Puzzle 29147 Test Coverage**: Added puzzle 29147 clues to regression suite.
15. **Fully Dynamic Test Suite**: Rewrote `test_regression.py` to fetch all clues dynamically from Supabase via `/trainer/clue-ids?full=1`. Zero hardcoded clue data — test data built from live metadata at runtime. Removed `generate_test_clues.py` (no longer needed). Added `/trainer/clue-ids` endpoint with `?full=1` parameter.

---

## 14. Training Metadata Validation

`validate_training.py` runs four layers of checks on every training item. Errors block upload; on server load, errors exclude the clue (non-fatal). Warnings are logged but don't block.

### 14.1 Integration Points

- `upload_training_metadata.py` — validates before uploading (errors skip item)
- `training_handler.py` `lookup_clue()` — validates per request when fetching from Supabase. Invalid clues raise `ValueError` with error details.
- `trainer_routes.py` `/trainer/start` — returns 422 with `validation_errors` for invalid clues, 404 for unannotated clues, 200 for success
- `crossword.js` — displays `data.message` from server (not hardcoded text) for both 422 and 404 errors
- Standalone: `python3 validate_training.py` — validates all items in Supabase

### 14.2 Layer 1: Structural Checks

- Required top-level fields exist (clue, number, enumeration, answer, words, clue_type, difficulty, steps)
- `words` array matches clue text (punctuation-tolerant comparison)
- Steps is non-empty, each has valid `type` (must be a key in `render_templates.json`)
- Indices in bounds for steps and transforms
- Step-specific required fields (e.g. `indicator` needs `indices`, `hint`, `indicator_type`)
- Valid `indicator_type` values

### 14.3 Layer 2: Semantic Checks

- Assembly `result` == `answer`
- Terminal transform letters match assembly result (chain-aware: dependent transforms consume predecessors)
- Total letter count matches enumeration
- Each transform has required fields (`role`, `indices`, `type`, `result`, `hint`)
- Valid transform `type` (synonym/abbreviation/literal/reversal/deletion/anagram/container/letter_selection/homophone)
- No `prompt` field on individual transforms (architecture rule)
- Indicator coverage: every dependent transform (reversal/deletion/anagram/container) has a matching indicator step

### 14.4 Layer 3: Convention Checks (Per-Transform)

Deterministic checks — **hard errors**:
- **literal**: result == uppercase of clue word(s)
- **reversal**: result == reverse of consumed predecessor(s)
- **deletion**: result is predecessor with letter(s) removed (subsequence check)
- **anagram**: sorted letters of input == sorted letters of result
- **container**: result is one piece inserted inside another
- **letter_selection**: result extractable by first/last/alternating/hidden letters

Lookup-based — **warnings**:
- **abbreviation**: checked against `CRYPTIC_ABBREVIATIONS` (~200 entries) + publication-specific dictionary
- **synonym**: no check yet (no external API)

### 14.5 Layer 4: Publication-Specific Checks

Publication is extracted from item ID (e.g. `times-29453-11a` → `times`). All publication checks produce **warnings**, not errors.

**Times (`times`) conventions:**
- **British spelling** — answers checked against ~35 American spelling patterns (COLOR→COLOUR, CENTER→CENTRE, GRAY→GREY, etc.). Ambiguous words with valid shared meanings (tire, curb, draft) are excluded.
- **Times abbreviation dictionary** (`TIMES_ABBREVIATIONS`, ~70 entries) — extends the general dictionary with UK-specific mappings:
  - British institutions: RA (Royal Academy), NT (National Trust), BBC, NHS, BM, VA
  - UK politics: CON, LAB, LIB, MP, PM, TORY
  - British royalty/honours: ER, HM, OBE, MBE, CBE, MC, DSO, VC
  - British military: RA (gunners), RE (sappers), RM (marines), RN (fleet/navy), TA (reserves), OR (ranks)
  - UK education: ETON, SCH, UNI
  - UK rivers: CAM, DEE, DON, EXE, TAY, URE, USK, WYE, AVON, etc. (including cryptic misdirections: "flower"/"banker"/"runner" = river)
  - Cricket: duck=O, maiden=M, eleven=XI
  - Old British currency: bob=S, quid=L, guinea=G/GN, copper=D
  - British slang: chap=MAN, pub=INN/PH, loo=WC/LAV

**Adding a new publication:** Add a new entry to `PUBLICATION_CONVENTIONS` dict in `validate_training.py` with `spelling_checks` and `extra_abbreviations` keys.

