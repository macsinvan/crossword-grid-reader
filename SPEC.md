# Grid Reader - Technical Specification

This document specifies the Grid Reader application at a level of detail sufficient to reproduce it from scratch.

---

## 1. Overview

**Grid Reader** is a web-based Times Cryptic crossword solver with interactive teaching mode. Users import PDF puzzles, solve them interactively, and learn cryptic techniques through step-by-step guidance.

### 1.1 Target Stack
- **Backend**: Flask (Python 3.9+)
- **Database**: Supabase PostgreSQL (with local file fallback)
- **Frontend**: Static HTML/JS/CSS
- **Deployment**: Local development (Vercel planned for Phase 3)

### 1.2 Key Principles
1. **Progressive Discovery Teaching**: This is a TEACHING app, not a solution viewer. Users should DISCOVER the clue breakdown step-by-step through guided interaction, NOT see the full decode revealed upfront. Each step requires user engagement before revealing the next insight.
2. **Template-Based Architecture**: All clues are represented using predefined step templates (13 core + 6 helper = 19 total) that can be combined to construct ANY cryptic clue. Each metadata step type maps 1:1 to a render template. This enables both human teaching AND future automated annotation (a solver that generates metadata from cold clues).
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

### 2.3 Correct Pattern: Step Menu Overview
✓ **CORRECT:** Show a roadmap, then guide discovery within each step:

**Initial Screen - Step Menu:**
```
┌─────────────────────────────────────────────┐
│ 17D: Embankment architect lengthened       │
│      with cob? (5,3)                        │
├─────────────────────────────────────────────┤
│ Answer: [A][S][W][A][N] [D][A][M]          │
├─────────────────────────────────────────────┤
│ Steps to solve:                             │
│                                             │
│ 1. ⭕ Identify Definition                   │
│ 2. ⭕ Identify Wordplay Indicator           │
│ 3. ⭕ Identify Literal (architect)          │
│ 4. ⭕ Identify Implied Synonym (cob)        │
│ 5. ⭕ Assemble                              │
│                                             │
│ [Click any step to begin]                  │
└─────────────────────────────────────────────┘
```

**User clicks "Identify Definition" → Interactive Step:**
- Prompt: "Tap the definition in this clue"
- User taps "Embankment"
- Feedback: "✓ DEFINITION FOUND: Embankment"
- Returns to menu showing: `1. ✓ Identify Definition` (completed)

**User clicks "Identify Wordplay Indicator" → Interactive Step:**
- Prompt: "This is a container clue. Tap the indicator"
- User taps "lengthened with"
- Teaching: "'lengthened with' means A takes B inside"
- Returns to menu showing: `2. ✓ Identify Wordplay Indicator` (completed)

**Progressive completion:** User works through each step, accumulating breadcrumbs (🎓). Only after completing all steps does the full solution become visible.

### 2.4 Implementation Status
⚠️ **Current State (v1):** The trainer currently reveals too much information upfront. This was a necessary first step to validate the template system works.

🎯 **Target State (v2):** Each step will require user interaction before revealing insights. The full breakdown only appears in the summary page AFTER completion or explicit "Give Up".

### 2.5 Design Rules
1. **One insight per interaction** - Never reveal multiple facts simultaneously
2. **Require engagement** - Users must tap, type, or choose before advancing
3. **Build incrementally** - Each step builds on previous discoveries
4. **Celebrate progress** - Show breadcrumbs (🎓) of accumulated knowledge
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
│  crossword_server.py                                        │
│  ├── /trainer/start    → training_handler.start_session()  │
│  ├── /trainer/input    → training_handler.handle_input()   │
│  ├── /trainer/continue → training_handler.advance_to_next()│
│  ├── /trainer/reveal   → training_handler.reveal_answer()  │
│  └── /trainer/ui-state → training_handler.update_ui_state()│
├─────────────────────────────────────────────────────────────┤
│  training_handler.py                                        │
│  ├── _sessions dict    (all UI state)                       │
│  ├── STEP_TEMPLATES    (19 render templates)                │
│  ├── get_render()      (build render object)                │
│  └── handle_input()    (validate & advance)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage                              │
├─────────────────────────────────────────────────────────────┤
│  Supabase PostgreSQL   │  Local Fallback                    │
│  - publications        │  - puzzles/ directory              │
│  - puzzles             │  - clues_db.json                   │
│  - clues               │                                    │
│  - user_progress       │                                    │
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

### 4.2 Clue Metadata Format (Our Custom Schema)

**Key Principle:** We control this metadata format completely. It's our own design, optimized for interactive teaching.

**Template-Based Architecture:**
- The metadata uses **predefined step templates** (13 core + 6 helper = 19 total) that can be combined to construct ANY cryptic clue
- Each step has a `type` field that maps 1:1 to a render template in `training_handler.py`
- Render templates define the interactive phases (fodder → result → teaching)
- By mixing templates, we can represent any cryptic mechanism
- See section 4.2.2 for the complete metadata → render template mapping

**Example: Simple Deletion Clue**
```json
{
  "training_items": {
    "times-29453-25a": {
      "clue": {
        "text": "Urge removal of line from silly speech (5)",
        "answer": "DRIVE",
        "enumeration": "5"
      },
      "words": ["Urge", "removal", "of", "line", "from", "silly", "speech"],
      "steps": [
        {
          "type": "standard_definition",  // Template: identify definition
          "expected": {"text": "Urge", "indices": [0]},
          "position": "start"
        },
        {
          "type": "synonym",  // Template: find synonym
          "fodder": {"text": "silly speech", "indices": [5, 6]},
          "result": "DRIVEL",
          "reasoning": "Silly speech = DRIVEL"
        },
        {
          "type": "deletion",  // Template: remove letter
          "indicator": {"text": "removal of line", "indices": [1, 2, 3]},
          "fodder": {"text": "DRIVEL"},
          "deleted": "L",
          "result": "DRIVE"
        }
      ]
    }
  }
}
```

**Why This Format:**
1. **Flexible:** Can represent any cryptic mechanism by combining templates
2. **Teachable:** Each step maps to interactive phases users work through
3. **Optimizable:** We can refine the format as we learn what works best
4. **Self-Contained:** Includes all data needed for validation and teaching

**Template Reusability:**
The same `synonym` template can be reused across thousands of clues. We just provide different `fodder` and `result` values. This makes annotating new clues efficient.

**Core Step Templates (13 types for annotation):**

These are the primary templates used when annotating clues in `clues_db.json`:

| Template Type | Purpose | Example |
|---------------|---------|---------|
| `standard_definition` | Identify definition at start/end | "Urge" = definition |
| `synonym` | Word → synonym | "silly speech" → DRIVEL |
| `abbreviation` | Word → abbreviation | "five" → V |
| `literal` | Word used as-is | "it" → IT |
| `literal_phrase` | Phrase read literally | "do you mean" → ISIT |
| `anagram` | Rearrange letters | "changed" + "tone" → NOTE |
| `reversal` | Reverse word | "returned" + "dog" → GOD |
| `deletion` | Remove letter(s) | DRIVEL - L → DRIVE |
| `letter_selection` | First/last/middle letters | "initially big" → B |
| `hidden` | Hidden word in phrase | "ma**KING**dom" → KING |
| `container_verify` | One part inside another | AD(A)M → ADAM |
| `charade_verify` | Combine parts in order | RE + PRO + ACH → REPROACH |
| `double_definition` | Two definitions | "bark" = tree covering & dog sound |

**Additional Helper Templates (6 types):**
In addition to the 13 core templates above, there are 6 helper/discovery templates for more advanced workflows:
- `container` - Container clue discovery phase
- `clue_type_identify` - Let user identify clue type
- `wordplay_overview` - Explain wordplay mechanism
- `deletion_discover` - Discovery phase for deletions
- `alternation_discover` - Discovery phase for alternations
- `connector` - Explain linking/connector words

**Total:** 19 render templates in `training_handler.py` (see section 4.2.2 for complete inventory).

**Composability Example:**
A complex clue like "Embankment architect lengthened with cob? (5,3)" uses:
1. `standard_definition` → "Embankment"
2. `container_verify` → "lengthened with" indicates container
3. `synonym` → "architect" → ADAM
4. `synonym` → "cob" → SWAN
5. `charade_verify` → A + SWAN + DAM → ASWAN DAM

By mixing these 5 templates, we construct the full teaching sequence.

### 4.2.1 Critical: Template System Enables Automated Annotation

**Why This Template-Based Architecture Matters:**

The template system is not just for displaying pre-annotated clues. It's the foundation for **automated clue annotation**.

**Future Capability: Cold Clue Solver**
We will build a solver that takes:
- **Input:** A "cold" clue (never seen before) + optionally the answer
- **Output:** Complete clue metadata in our format, using templates

**Example Workflow:**
```
INPUT:
  Clue: "Embankment architect lengthened with cob? (5,3)"
  Answer: "ASWAN DAM" (optional)

SOLVER PROCESS:
  1. Identify clue type → Container
  2. Find definition → "Embankment"
  3. Parse indicator → "lengthened with" = container indicator
  4. Identify components:
     - "architect" → synonym lookup → ADAM
     - "cob" → synonym lookup → SWAN
  5. Verify assembly → AD + (SWAN) + AM = ASWAN DAM

OUTPUT (generated metadata):
{
  "steps": [
    {"type": "standard_definition", "expected": {"text": "Embankment", ...}},
    {"type": "container_verify", "indicator": {"text": "lengthened with", ...}},
    {"type": "synonym", "fodder": {"text": "architect"}, "result": "ADAM"},
    {"type": "synonym", "fodder": {"text": "cob"}, "result": "SWAN"},
    {"type": "charade_verify", "result": "ASWAN DAM", "assembly": "..."}
  ]
}
```

**Why Templates Make This Possible:**
1. **Finite Set:** Only 19 render templates to generate from (not infinite variations)
2. **Deterministic:** Each template has clear input/output structure
3. **Composable:** Complex clues are just combinations of simple templates
4. **Reusable:** Same templates work for thousands of clues
5. **Validatable:** Generated metadata follows exact schema
6. **1:1 Mapping:** Each metadata step type maps to exactly one render template

**Design Implication:**
Every template must be:
- **Machine-generatable:** Can be produced by algorithmic parsing
- **Complete:** Contains all data needed for validation and teaching
- **Unambiguous:** No ambiguity in what constitutes this step type

This is why we control the metadata format completely. We're not constrained by external schemas—we design it to be both human-teachable AND machine-generatable.

### 4.2.2 Clue Step Templates → Render Templates (The Two-Layer System)

**Critical Architecture:** Each step `type` in clue metadata maps 1:1 to a render template.

**IMPORTANT: ALL Templates Stored EXTERNAL TO CODE**
- **Clue Step Template Schemas:** Stored in `clue_step_templates.json` (EXTERNAL TO CODE)
- **Render Templates:** Stored in `render_templates.json` (EXTERNAL TO CODE)
- **Why external:** Templates must be version-controlled, machine-readable, and reusable independent of implementation code
- **Implementation:** `training_handler.py` loads these template files at runtime

**IMPORTANT: Thin Stateless Client**
The client (`trainer.js`) has ZERO state and ZERO logic. It receives a complete `render` object from the server and displays it. The render object contains EVERYTHING needed: what to show, what input mode, what colors, what text. The client never decides anything—it's a pure rendering layer.

**The Two-Layer System:**

```
LAYER 1: Clue Step Template
  ├─ Schema Definition: clue_step_templates.json (EXTERNAL TO CODE)
  │   └─ Defines required/optional fields, types, validation rules
  │   └─ Example: standard_definition schema with expected, position fields
  │
  └─ Instance: clues_db.json → training_items → {clue_id} → steps[]
      └─ Clue-specific data only
      └─ Must conform to schema in clue_step_templates.json
      └─ Example: {"type": "synonym", "fodder": {...}, "result": "DRIVEL"}
           │
           │ 1:1 mapping ↓
           │
LAYER 2: Render Template (in render_templates.json - EXTERNAL TO CODE)
  └─ Generic step type information
  └─ Accepts clue step data as input
  └─ Defines how to present in teaching mode
  └─ Loaded by training_handler.py at runtime
  └─ Example: render_templates.json → templates → synonym → {
       "phases": [
         {"id": "fodder", "inputMode": "tap_words", ...},
         {"id": "result", "inputMode": "text", ...},
         {"id": "teaching", "inputMode": "none", ...}
       ]
     }
```

**Terminology:**

1. **Clue Step Template Schema** (in `clue_step_templates.json` - EXTERNAL TO CODE):
   - **Purpose:** Capture data from the clue in a form that can be used by the render template. Has NO knowledge of presentation/process. ONLY has knowledge of the clue itself.
   - Formal definition of required/optional fields for extracting clue data
   - Defines field types, validation rules, examples
   - Machine-readable, version-controlled
   - Example: Schema for "synonym" type defining fodder, result, reasoning fields

2. **Clue Step Template Instance** (metadata in `clues_db.json`):
   - **Purpose:** Specific data extracted from this clue, conforming to schema
   - Contains: which words (indices), expected answers, reasoning text
   - Has NO presentation logic - purely data extraction
   - Example: `{"type": "synonym", "fodder": {"text": "silly speech", "indices": [5,6]}, "result": "DRIVEL"}`

3. **Render Template** (code in `training_handler.py`):
   - Generic information about the step type
   - Accepts clue step template data as input
   - Defines how to present to user in teaching mode
   - Contains: phases, input modes, prompts, panel formatting
   - Example: `STEP_TEMPLATES["synonym"]` with phases array

**How It Works:**

1. **Clue Step Template defines WHAT** (clue-specific data):
   - Which specific words from this clue to tap
   - Expected answer for this specific clue
   - Reasoning text for this specific clue

2. **Render Template defines HOW** (generic presentation logic):
   - How many phases to step through
   - What input modes (tap_words, text, multiple_choice, none)
   - What action prompts to show
   - How to format the teaching panel

**Example: Synonym Step**

**Clue Step Template** (clue-specific data in `clues_db.json`):
```json
{
  "type": "synonym",  // Identifies which render template to use
  "fodder": {"text": "silly speech", "indices": [5, 6]},  // THIS clue's words
  "result": "DRIVEL",  // THIS clue's expected answer
  "reasoning": "Silly speech = DRIVEL"  // THIS clue's explanation
}
```

**Render Template** (generic presentation logic in `training_handler.py`):
```python
"synonym": {
    "phases": [
        {
            "id": "fodder",
            "inputMode": "tap_words",
            "actionPrompt": "Tap the words that need to be converted to a synonym"
        },
        {
            "id": "result",
            "inputMode": "text",
            "actionPrompt": "What's the synonym?"
        },
        {
            "id": "teaching",
            "inputMode": "none",
            "panel": "Synonym\n{fodder.text} = {result}\n{reasoning}"
        }
    ]
}
```

**Template Inventory (19 render templates in training_handler.py):**

| Clue Step Type (metadata) | Render Template (code) | Purpose |
|----------------------------|------------------------|---------|
| `standard_definition` | `standard_definition` | Find definition |
| `synonym` | `synonym` | Word → synonym |
| `abbreviation` | `abbreviation` | Word → abbreviation |
| `literal` | `literal` | Word as-is |
| `literal_phrase` | `literal_phrase` | Phrase literally |
| `anagram` | `anagram` | Rearrange letters |
| `reversal` | `reversal` | Reverse word |
| `deletion` | `deletion` | Remove letter(s) |
| `letter_selection` | `letter_selection` | First/last/middle |
| `hidden` | `hidden` | Hidden word |
| `container_verify` | `container_verify` | One inside another |
| `charade_verify` | `charade_verify` | Combine parts |
| `double_definition` | `double_definition` | Two definitions |
| `container` | `container` | Container discovery |
| `clue_type_identify` | `clue_type_identify` | Identify clue type |
| `wordplay_overview` | `wordplay_overview` | Wordplay explanation |
| `deletion_discover` | `deletion_discover` | Deletion discovery |
| `alternation_discover` | `alternation_discover` | Alternation discovery |
| `connector` | `connector` | Linking words |

**Why This Separation Matters:**
1. **Reusability:** Same template works for thousands of different clues
2. **Maintainability:** Update UI behavior once, affects all clues using that template
3. **Validation:** Template defines what inputs are expected and valid
4. **Future-proofing:** Can change templates without re-annotating clues
5. **Thin Client:** Client has no state—everything comes from server's render object

### 4.3 Session State (server-side)
```python
_sessions[clue_id] = {
    "step_index": 0,           # Current step (-1 for clue type identification)
    "phase_index": 0,          # Current phase within step
    "highlights": [],          # Word highlights [{indices, color}]
    "learnings": [],           # Breadcrumbs [{title, text}]
    "user_answer": [],         # Letters typed in answer boxes
    "answer_locked": False,    # True when answer confirmed
    "answer_known": False,     # True when hypothesis accepted
    "cross_letters": [],       # From grid [{position, letter}]
    "enumeration": "5",        # Answer length pattern
    "selected_indices": [],    # Selected word indices (tap_words)
    "step_text_input": [],     # Letters in step input boxes
    "hint_visible": False      # Hint panel shown
}
```

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
- Current phase index
- User's answers
- Word selections
- Hint visibility
- Breadcrumbs (learnings)
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

### 5.1 Step Types (19 render templates)

**See section 4.2.2 for the complete metadata → render template mapping.**

The system has 19 render templates in `training_handler.py`. The most commonly used core templates for basic clue annotation are:

| Type | Phases | Description |
|------|--------|-------------|
| `standard_definition` | select → teaching | Find definition at start/end of clue |
| `abbreviation` | fodder → result → teaching | five → V |
| `synonym` | fodder → result → teaching | help → AID |
| `literal` | fodder → teaching | Word stays as-is (IT → IT) |
| `literal_phrase` | fodder → result → teaching | "do you mean?" → ISIT |
| `anagram` | indicator → fodder → result → teaching | Rearrange letters |
| `reversal` | indicator → result → teaching | Reverse letters |
| `deletion` | indicator → result → teaching | Remove letters |
| `letter_selection` | indicator → fodder → result → teaching | First/last/middle |
| `hidden` | indicator → result → teaching | Letters hidden in phrase |
| `container_verify` | order → teaching | One piece inside another |
| `charade_verify` | result → teaching | Combine pieces |
| `double_definition` | first_def → second_def → solve → teaching | Two meanings |

### 5.2 Input Modes

| Mode | User Action | Validation |
|------|-------------|------------|
| `tap_words` | Tap words in clue | Check selected indices match expected |
| `text` | Type answer in boxes | Check text matches expected |
| `multiple_choice` | Select from options | Check selection index |
| `none` | Read teaching panel | No validation, just "Continue" |

### 5.3 Render Object Structure

**The Complete Truth:** This object contains EVERYTHING the client needs to render the UI. The client has NO other data sources, NO local state, NO decision-making logic.

```json
{
  "stepIndex": 1,
  "phaseIndex": 0,
  "stepType": "synonym",
  "phaseId": "fodder",
  "inputMode": "tap_words",  // Client reads this to know what UI to show
  "actionPrompt": "Tap the word(s) that mean 'silly speech'",  // Client displays this exactly
  "highlights": [{"indices": [0], "color": "GREEN"}],  // Client applies these colors
  "learnings": [{"title": "DEFINITION FOUND: Urge", "text": ""}],  // Client lists these
  "words": ["Urge", "removal", "of", "line", "from", "silly", "speech"],  // Client displays these
  "answer": "DRIVE",  // Client knows the target answer
  "userAnswer": ["D", "", "", "", ""],  // Client shows these in boxes
  "answerLocked": false,  // Client uses this to disable/enable boxes
  "crossLetters": [{"position": 0, "letter": "D"}],  // Client renders these as locked
  "enumeration": "5",  // Client shows this
  "hint": "Look for words describing foolish talk"  // Client shows this if toggled
}
```

**Client Behavior:**
- Receives this object via `/trainer/start`, `/trainer/input`, `/trainer/continue` endpoints
- Renders exactly what the object specifies—no interpretation, no decisions
- When user interacts, sends raw input to server, receives new render object
- Replaces entire UI state with new render object

---

## 6. UI Specifications

### 6.1 Step Menu (Overview Screen)

**Purpose:** First screen shown when user clicks "Solve". Displays all steps as a roadmap before diving into interactive solving.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: 17D Embankment architect lengthened with cob? (5,3) │
│                                                          [X] │
├─────────────────────────────────────────────────────────────┤
│ ANSWER BOXES (crossword-style)                              │
│ [A][S][W][A][N] [D][A][M]                                   │
│  ↑cross letters shown, others empty                         │
├─────────────────────────────────────────────────────────────┤
│ STEPS TO SOLVE:                                             │
│                                                             │
│ ⭕ 1. Identify Definition                                   │
│ ⭕ 2. Identify Wordplay Indicator                           │
│ ⭕ 3. Identify Literal (architect)                          │
│ ⭕ 4. Identify Implied Synonym (cob)                        │
│ ⭕ 5. Assemble                                              │
│                                                             │
│ [Each step is clickable]                                    │
└─────────────────────────────────────────────────────────────┘
```

**State Indicators:**
- ⭕ = Not started (gray circle)
- 🔄 = In progress (blue circle)
- ✓ = Completed (green checkmark)

**Behavior:**
1. User clicks any step → Navigate to that step's interactive phases
2. After completing a step → Return to menu with updated status
3. When all steps completed → Show summary page
4. Answer boxes are always visible and editable (hypothesis entry allowed)

**Data Source:**
- Step list generated from `clue_data["steps"]` array in `clues_db.json`
- Step titles derived from `step["type"]` and optional `step["label"]`

### 6.3 Step Detail (Interactive Solving)

When user clicks a step from the menu, they enter the interactive solving view:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Step 2 of 5: Identify Wordplay Indicator       [X] │
│ ← Back to Steps                                             │
├─────────────────────────────────────────────────────────────┤
│ SECTION 1: Clue words with highlights                       │
│ [Urge] removal of line from [silly] [speech] (5)            │
│  ↑green                      ↑blue   ↑blue                  │
├─────────────────────────────────────────────────────────────┤
│ SECTION 2: Answer boxes + Solve button                      │
│ [D][R][I][V][E]                                    [Solve]  │
│  ↑blue=cross letter, ↑green=locked                          │
├─────────────────────────────────────────────────────────────┤
│ SECTION 3: Step progress                                    │
│ Step 2 of 3                                                 │
├─────────────────────────────────────────────────────────────┤
│ SECTION 4: Action prompt + hints                            │
│ What's a synonym for 'silly speech'?              💡 🔓     │
├─────────────────────────────────────────────────────────────┤
│ SECTION 5: Input area (varies by inputMode)                 │
│ [D][R][I][V][E][L]                              [Check]     │
├─────────────────────────────────────────────────────────────┤
│ SECTION 6: Teaching panel (when phaseId=teaching)           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Synonym                                                 │ │
│ │ "silly speech" = DRIVEL                                 │ │
│ │ Common synonyms: drivel, babble, nonsense...            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                               [Continue]    │
├─────────────────────────────────────────────────────────────┤
│ SECTION 7: Learnings (breadcrumbs)                          │
│ 🎓 DEFINITION FOUND: Urge                                   │
│ 🎓 SYNONYM: silly speech → DRIVEL                           │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Summary Page (Completion Screen)

**Trigger:** When all steps completed OR Solve button clicked

**Layout:**
```
┌─────────────────────────────────────────┐
│  🎉 DRIVE                               │  ← Green header
├─────────────────────────────────────────┤
│  Urge = DRIVE                           │  ← Plain English summary
│  To push or propel forward, or a        │
│  strong motivation                      │
│                                         │
│  Definition: ⭐  Wordplay: ⭐           │  ← Difficulty ratings
├─────────────────────────────────────────┤
│  🎓 DEFINITION FOUND: Urge              │  ← All breadcrumbs
│  🎓 SYNONYM: silly speech → DRIVEL      │
│  🎓 DELETION: DRIVEL - L → DRIVE        │
├─────────────────────────────────────────┤
│           [ Update Grid ]               │  ← Applies answer, closes
└─────────────────────────────────────────┘
```

**Plain English Summary:**
- Format: `"{definition} = {ANSWER}. {hint}"`
- Example: `"Urge = DRIVE. To push or propel forward, or a strong motivation"`

**Difficulty Ratings:**
- Definition rating: ⭐ (easy), ⭐⭐ (medium), ⭐⭐⭐ (hard)
- Wordplay rating: ⭐ (easy), ⭐⭐ (medium), ⭐⭐⭐ (hard)
- Data source: `clue.difficulty.definition.rating` and `clue.difficulty.wordplay.rating`

**Data Structure (from clues_db.json):**
```json
{
  "difficulty": {
    "definition": {
      "rating": "easy",
      "hint": "To push or propel forward, or a strong motivation"
    },
    "wordplay": {
      "rating": "easy",
      "hint": "Remove a letter from a word meaning nonsense"
    }
  }
}
```

**Breadcrumbs Data Source:** `session["learnings"]` array accumulated during training.

**Entry Points:**
1. Natural completion: `step_index >= len(steps)` in `get_render()`
2. Solve button: `reveal_answer()` returns with `complete: True`

### 6.5 Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Definition highlight | Green | #22c55e |
| Indicator highlight | Orange/Yellow | #f59e0b |
| Fodder highlight | Blue | #3b82f6 |
| Cross letter border | Blue | #3b82f6 |
| Locked answer | Green | #16a34a |
| Incorrect flash | Red | #ef4444 |
| Teaching panel bg | Light blue | #eff6ff |
| Hint panel bg | Amber | #fef3c7 |

---

## 7. API Endpoints

### 7.1 POST /trainer/start
Start a new training session.

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "puzzle_number": "29453",
  "clue_number": 25,
  "direction": "across",
  "clue_text": "Urge removal of line from silly speech (5)",
  "cross_letters": [{"position": 0, "letter": "D"}],
  "enumeration": "5"
}
```

**Response:** Render object (see 5.3)

### 7.2 POST /trainer/input
Submit user input for validation.

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "input": "DRIVEL"  // or [5,6] for tap_words indices
}
```

**Response:** Updated render object

### 7.3 POST /trainer/continue
Advance past teaching phase.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Updated render object

### 7.4 POST /trainer/reveal
Give up and reveal full answer.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Completion render with `complete: true`, `learnings` for all steps

### 7.5 POST /trainer/ui-state
Update UI state (hint toggle, word selection, typing).

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "action": "toggle_hint"  // or "select_word", "type_answer", etc.
}
```

**Response:** Updated render object

### 7.6 POST /trainer/hypothesis
Submit answer hypothesis (user typed correct answer in boxes).

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "answer": "DRIVE"
}
```

**Response:** If correct, sets `answer_known: true`, returns updated render

### 7.7 POST /trainer/solve-step
Reveal answer for current step only.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Reveals expected answer, advances to teaching phase

---

## 8. Files Structure

```
Grid Reader/
├── crossword_server.py      # Flask server, routes
├── training_handler.py      # Session state, STEP_TEMPLATES, get_render()
├── puzzle_store_supabase.py # Supabase database client
├── puzzle_store.py          # Local file fallback
├── pdf_processor.py         # PDF parsing, OCR correction
├── clues_db.json            # Pre-annotated clue steps
├── teaching_hints.json      # Expert hints for step types
├── static/
│   ├── crossword.js         # Grid UI, keyboard navigation
│   ├── trainer.js           # Stateless trainer UI
│   └── crossword.css        # Styles
├── templates/
│   └── index.html           # Main page template
├── puzzles/                  # Local puzzle storage (fallback)
├── requirements.txt
└── .env                      # SUPABASE_URL, SUPABASE_ANON_KEY
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

### 10.1 Answer Auto-Population
When a step's `result` matches the final answer, automatically:
1. Fill answer boxes with the result
2. Set `answer_locked = True`
3. Continue to teaching phase

**Trigger:** In `handle_input()` when `phase_id == "result"` completes successfully.

### 10.2 Skip Redundant Input
When `answer_known = True` (user already typed correct answer), skip any phase where:
- `inputMode == "text"`
- Expected answer equals the final answer

**Implementation:** In `get_render()`, auto-advance past such phases.

### 10.3 Cross Letters Display
- Cross letters (from intersecting clues) shown in answer boxes
- Blue border and light blue background
- Not editable (locked)
- Must match when user types answer

### 10.4 Hint System
- 💡 icon shown for phases with hints available
- Click toggles `hint_visible` in session
- Hint text from: step.hint, onWrong.message, or teaching_hints.json
- Reset to hidden when advancing to next step

### 10.5 Solve Step (🔓)
- Reveals expected answer for current step only
- Records "REVEALED: {answer}" in learnings
- Advances to teaching phase

### 10.6 Solve Button (Full Give Up)
- Reveals complete answer
- Populates learnings with all step breakdowns
- Shows summary page with "Update Grid" button

### 10.7 Multi-word Answers
Answers with spaces (e.g., "LOW TAR"):
- Strip spaces for answer box count
- Strip spaces for comparison
- Strip spaces when applying to grid

### 10.8 Auto-reload clues_db.json
Server checks file modification time on each `/trainer/start` request. If changed, reloads automatically without server restart.

### 10.9 Check Answer Button
A "Check" button appears next to the Reveal and Solve buttons in the answer box area.

**Visibility:** Shown when answer boxes are editable (not locked or complete).

**Behavior:**
1. On click: collects user's typed letters, sends to `POST /trainer/check-answer`
2. Server validates answer (stripped, uppercased comparison)
3. If correct → returns solved view data (`mode: "solved_view"`), client navigates to summary page
4. If incorrect → returns error, client shows brief red feedback ("Incorrect — try again") that auto-clears after 2 seconds

**Endpoint:** `POST /trainer/check-answer`
- Request: `{"clue_id": "...", "answer": "BISHOP"}`
- Success response: same as `/trainer/solved-view` (includes `mode: "solved_view"`)
- Failure response: `{"success": false, "error": "Incorrect answer"}`

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
- Supabase PostgreSQL backend
- Publications, puzzles, clues, user_progress tables
- Auto-fallback to local storage
- DB status indicator in header

### Phase 2: Interactive Teaching Mode ✓
- Ported training_handler.py from cryptic-trainer
- 19 render templates (13 core + 6 helper)
- 1:1 mapping between metadata step types and render templates
- Server-driven rendering
- Summary page with breadcrumbs

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
Currently, clues must be manually annotated in `clues_db.json`. The solver will automate this process, allowing us to rapidly expand the teaching library. The template-based architecture makes this possible because we only need to generate from a finite set of 19 render templates (13 core + 6 helper), not infinite variations. Each generated metadata step type maps 1:1 to an existing render template.

---

## 13. Testing Checklist

### 13.1 Core Flow
- [ ] Import PDF puzzle
- [ ] Grid displays correctly
- [ ] Clue selection highlights grid cells
- [ ] Click "Solve" opens trainer

### 13.2 Trainer Flow
- [ ] Step phases advance correctly
- [ ] tap_words validates selection
- [ ] text input validates answer
- [ ] teaching panels display
- [ ] Continue advances to next step

### 13.3 Answer Entry
- [ ] Cross letters displayed and locked
- [ ] Typing fills boxes and auto-advances
- [ ] Correct answer shows green, locks boxes
- [ ] Incorrect answer flashes red

### 13.4 Completion
- [ ] All steps complete → summary page
- [ ] Summary shows 🎉 + answer
- [ ] Summary shows all breadcrumbs with 🎓
- [ ] "Update Grid" applies answer and closes

### 13.5 Give Up Options
- [ ] 🔓 reveals current step only
- [ ] Solve button reveals full answer
- [ ] Both show summary page

---

## Appendix A: Implementation History

The following bugs and features were implemented during development:

1. **CRITICAL REGRESSION FIX**: Added `numbering` object to Supabase response
2. **Cross Letters Regression**: Store and display cross letters from grid
3. **Interactive Answer Entry**: Editable answer boxes with hypothesis submission
4. **Crossword-Style Text Input**: Individual boxes for step input
5. **Hint Lightbulb Icon**: Proactive hint reveal
6. **Solve Step Feature**: Reveal single step answer
7. **Skip Redundant Input**: Auto-advance when answer known
8. **Solve Button**: Full give-up option
9. **Summary Page**: Breadcrumbs display on completion
10. **OCR Validation**: Spell-checking for PDF import
11. **Annotation Mismatch Fixes**: Align clues_db.json with puzzle text
12. **Multi-word Answer Fixes**: Handle spaces in answers
13. **Mobile Responsive Grid**: CSS Grid with `1fr` units, `aspect-ratio: 1` cells, viewport-based sizing
14. **Cross Letters in Solve Phase**: Fixed `isFinalAnswerStep` condition to include `phaseId === 'solve'`
15. **Duplicate Hypothesis Fix**: Prevent duplicate HYPOTHESIS entries in learnings

---

## Appendix B: Clue Step Template Schema Reference

**Authoritative Source:** `clue_step_templates.json` - This file contains the formal, machine-readable schema definitions for all template types.

**Purpose:** This appendix documents the formal schema for each clue step template type. These schemas define the exact structure of step metadata stored in `clues_db.json` → `training_items` → `{clue_id}` → `steps[]`.

**Key Principle:** We control these templates completely. They are our custom design, optimized for interactive teaching and future automated annotation.

**How to Use:**
1. When creating new clue metadata → Reference `clue_step_templates.json` for field requirements
2. When validating existing metadata → Check against schemas in `clue_step_templates.json`
3. When implementing new features → Use template definitions to understand what data is available

---

### B.1 standard_definition

**Purpose:** Identify the definition portion of a cryptic clue (always at start or end).

**Schema:**
```json
{
  "type": "standard_definition",
  "expected": {
    "indices": number[],    // REQUIRED: Word indices in clue (0-indexed)
    "text": string          // REQUIRED: The actual definition words
  },
  "position": string,       // REQUIRED: "start" | "end"
  "explicit": boolean       // OPTIONAL: true if obvious, false if cryptic/indirect
}
```

**Required Fields:**
- `type`: Must be `"standard_definition"`
- `expected.indices`: Array of word positions (e.g., `[0]` or `[0, 1]`)
- `expected.text`: The definition text extracted from clue
- `position`: Either `"start"` or `"end"` (definitions are never in middle)

**Optional Fields:**
- `explicit`: Indicates if definition is straightforward (default: true)

**Related Metadata (at clue level):**
- `clue.difficulty.definition.rating`: "easy" | "medium" | "hard"
- `clue.difficulty.definition.hint`: Context explaining the definition

**Example:**
```json
{
  "type": "standard_definition",
  "expected": {
    "indices": [0],
    "text": "Embankment"
  },
  "position": "start",
  "explicit": true
}
```

**Validation Rules:**
1. `indices` must reference valid word positions in `clue.words` array
2. `text` must match the concatenation of words at specified indices
3. `position` must be either "start" or "end" (never "middle")
4. If `explicit` is false, `clue.difficulty.definition.hint` should be provided

**Render Template Mapping:**
- Maps to: `STEP_TEMPLATES["standard_definition"]` in `training_handler.py`
- Phases: select → teaching
- Input mode: tap_words (user selects definition words)

**Display in Step Menu:**
- Title: "Identify Definition"
- No sub-steps (atomic operation)
