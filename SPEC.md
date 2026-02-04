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
1. **Stateless Client Architecture**: The trainer UI (`trainer.js`) is a dumb rendering layer with ZERO local state. ALL state lives on the server in `training_handler.py`.
2. **No AI/LLM**: Teaching mode uses pre-annotated step data from imported JSON files, NOT dynamically generated explanations.
3. **Server-Driven Rendering**: Client receives a `render` object and displays it - nothing more.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Client)                        │
├─────────────────────────────────────────────────────────────┤
│  crossword.js          │  trainer.js                        │
│  - Grid UI             │  - Stateless render of phases      │
│  - Keyboard navigation │  - Receives render object          │
│  - localStorage cache  │  - Sends user input to server      │
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
│  ├── STEP_TEMPLATES    (13 step types)                      │
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

## 3. Data Models

### 3.1 Puzzle Structure
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

### 3.2 Clue Annotation Structure (clues_db.json)
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
          "type": "standard_definition",
          "expected": {"text": "Urge", "indices": [0]}
        },
        {
          "type": "synonym",
          "fodder": {"text": "silly speech", "indices": [5, 6]},
          "result": "DRIVEL"
        },
        {
          "type": "deletion",
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

### 3.3 Session State (server-side)
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

## 4. Training Flow

### 4.1 Step Types (13 types)

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

### 4.2 Input Modes

| Mode | User Action | Validation |
|------|-------------|------------|
| `tap_words` | Tap words in clue | Check selected indices match expected |
| `text` | Type answer in boxes | Check text matches expected |
| `multiple_choice` | Select from options | Check selection index |
| `none` | Read teaching panel | No validation, just "Continue" |

### 4.3 Render Object Structure
```json
{
  "stepIndex": 1,
  "phaseIndex": 0,
  "stepType": "synonym",
  "phaseId": "fodder",
  "inputMode": "tap_words",
  "actionPrompt": "Tap the word(s) that mean 'silly speech'",
  "highlights": [{"indices": [0], "color": "GREEN"}],
  "learnings": [{"title": "DEFINITION FOUND: Urge", "text": ""}],
  "words": ["Urge", "removal", "of", "line", "from", "silly", "speech"],
  "answer": "DRIVE",
  "userAnswer": ["D", "", "", "", ""],
  "answerLocked": false,
  "crossLetters": [{"position": 0, "letter": "D"}],
  "enumeration": "5",
  "hint": "Look for words describing foolish talk"
}
```

---

## 5. UI Specifications

### 5.1 Trainer Popup Layout
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Clue number + text                              [X] │
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

### 5.2 Summary Page (Completion Screen)

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

### 5.3 Color Scheme

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

## 6. API Endpoints

### 6.1 POST /trainer/start
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

**Response:** Render object (see 4.3)

### 6.2 POST /trainer/input
Submit user input for validation.

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "input": "DRIVEL"  // or [5,6] for tap_words indices
}
```

**Response:** Updated render object

### 6.3 POST /trainer/continue
Advance past teaching phase.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Updated render object

### 6.4 POST /trainer/reveal
Give up and reveal full answer.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Completion render with `complete: true`, `learnings` for all steps

### 6.5 POST /trainer/ui-state
Update UI state (hint toggle, word selection, typing).

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "action": "toggle_hint"  // or "select_word", "type_answer", etc.
}
```

**Response:** Updated render object

### 6.6 POST /trainer/hypothesis
Submit answer hypothesis (user typed correct answer in boxes).

**Request:**
```json
{
  "clue_id": "times-29453-25a",
  "answer": "DRIVE"
}
```

**Response:** If correct, sets `answer_known: true`, returns updated render

### 6.7 POST /trainer/solve-step
Reveal answer for current step only.

**Request:**
```json
{
  "clue_id": "times-29453-25a"
}
```

**Response:** Reveals expected answer, advances to teaching phase

---

## 7. Files Structure

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

## 8. Database Schema

### 8.1 Supabase Tables

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

## 9. Behavioral Specifications

### 9.1 Answer Auto-Population
When a step's `result` matches the final answer, automatically:
1. Fill answer boxes with the result
2. Set `answer_locked = True`
3. Continue to teaching phase

**Trigger:** In `handle_input()` when `phase_id == "result"` completes successfully.

### 9.2 Skip Redundant Input
When `answer_known = True` (user already typed correct answer), skip any phase where:
- `inputMode == "text"`
- Expected answer equals the final answer

**Implementation:** In `get_render()`, auto-advance past such phases.

### 9.3 Cross Letters Display
- Cross letters (from intersecting clues) shown in answer boxes
- Blue border and light blue background
- Not editable (locked)
- Must match when user types answer

### 9.4 Hint System
- 💡 icon shown for phases with hints available
- Click toggles `hint_visible` in session
- Hint text from: step.hint, onWrong.message, or teaching_hints.json
- Reset to hidden when advancing to next step

### 9.5 Solve Step (🔓)
- Reveals expected answer for current step only
- Records "REVEALED: {answer}" in learnings
- Advances to teaching phase

### 9.6 Solve Button (Full Give Up)
- Reveals complete answer
- Populates learnings with all step breakdowns
- Shows summary page with "Update Grid" button

### 9.7 Multi-word Answers
Answers with spaces (e.g., "LOW TAR"):
- Strip spaces for answer box count
- Strip spaces for comparison
- Strip spaces when applying to grid

### 9.8 Auto-reload clues_db.json
Server checks file modification time on each `/trainer/start` request. If changed, reloads automatically without server restart.

---

## 10. Mobile Responsive Design

### 10.1 Grid Scaling Strategy

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

### 10.2 CSS Structure

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

### 10.3 JavaScript Grid Rendering

```javascript
// crossword.js - renderGrid()
gridEl.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
gridEl.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
// NOT: `repeat(${cols}, 40px)` - this breaks responsive scaling
```

### 10.4 Trainer Modal on Mobile

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

### 10.5 Key Measurements

| Screen Width | Grid Width | Cell Size (approx) |
|--------------|------------|-------------------|
| 390px (iPhone) | 364px | 24px |
| 500px | 474px | 31px |
| 800px | 500px (max) | 33px |
| >800px | 616px | 40px |

---

## 11. Development Phases

### Phase 1: Supabase Database Integration ✓
- Supabase PostgreSQL backend
- Publications, puzzles, clues, user_progress tables
- Auto-fallback to local storage
- DB status indicator in header

### Phase 2: Interactive Teaching Mode ✓
- Ported training_handler.py from cryptic-trainer
- 13 step types with templates
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

---

## 11. Testing Checklist

### 11.1 Core Flow
- [ ] Import PDF puzzle
- [ ] Grid displays correctly
- [ ] Clue selection highlights grid cells
- [ ] Click "Solve" opens trainer

### 11.2 Trainer Flow
- [ ] Step phases advance correctly
- [ ] tap_words validates selection
- [ ] text input validates answer
- [ ] teaching panels display
- [ ] Continue advances to next step

### 11.3 Answer Entry
- [ ] Cross letters displayed and locked
- [ ] Typing fills boxes and auto-advances
- [ ] Correct answer shows green, locks boxes
- [ ] Incorrect answer flashes red

### 11.4 Completion
- [ ] All steps complete → summary page
- [ ] Summary shows 🎉 + answer
- [ ] Summary shows all breadcrumbs with 🎓
- [ ] "Update Grid" applies answer and closes

### 11.5 Give Up Options
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
