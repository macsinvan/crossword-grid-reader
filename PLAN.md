# Plan: Grid Reader → Public Multi-User Web App

## Target Stack
- **Backend**: Flask on Vercel (serverless functions)
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth
- **Frontend**: Static HTML/JS (current) served from Vercel

---

## CRITICAL: Stateless Client Architecture

**The trainer UI is a DUMB RENDERING LAYER with ZERO STATE.**

This is a non-negotiable architectural constraint. Violations cause bugs and must be immediately refactored.

### What This Means

| Belongs on SERVER | Does NOT belong on CLIENT |
|-------------------|---------------------------|
| `session["selected_indices"]` | `this.selectedIndices` |
| `session["user_answer"]` | `this.userAnswer` |
| `session["hint_visible"]` | `this.hintVisible` |
| `session["step_text_input"]` | `this.stepTextInput` |
| `session["answer_locked"]` | `this.answerLocked` |

### Client Responsibilities (ONLY these)
1. Call server endpoints (`/trainer/start`, `/trainer/input`, `/trainer/ui-state`)
2. Receive `render` object from server
3. Display exactly what `render` contains
4. Attach event handlers that call server on user interaction
5. Ephemeral feedback (flash messages that disappear) - OK to track locally

### Server Responsibilities
1. Maintain ALL session state in `training_handler._sessions[clue_id]`
2. Process user input and update state
3. Return complete `render` object with everything client needs to display
4. Include: `words`, `selectedIndices`, `userAnswer`, `hintVisible`, `answerLocked`, `crossLetters`, `enumeration`, etc.

### Why This Matters
- Server is source of truth - no sync bugs
- Client can be refreshed without losing state
- Testing is easier (just test API responses)
- Debugging is easier (inspect session state)
- Future: session state can persist to database

---

## Incremental Phases

### Phase 1: Supabase Database Integration
Replace file-based storage with Supabase PostgreSQL.

**Changes:**
- Create Supabase project with tables: `puzzles`, `clues`, `answers`, `user_progress`
- Replace `puzzle_store.py` with Supabase client
- Store progress server-side (session-based initially)
- Keep localStorage as offline cache

**Validation:** App works locally with Supabase backend

---

### Phase 2: Interactive Teaching Mode (NO AI)

**CRITICAL:** No AI/LLM. Step data is pre-annotated in imported JSON. We port the cryptic-trainer teaching system.

**Data Flow:**
```
clues_db.json (cryptic-trainer) → Import → Supabase clues table (with steps JSON)
                                              ↓
User clicks "Solve" → /trainer/start → training_handler.py → trainer.js renders phases
```

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  Phase 2 Teaching Mode Architecture                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RAW STEP DATA (from imported JSON):                        │
│  {"type": "abbreviation", "fodder": "five", "result": "V"}  │
│                                                             │
│  STEP TEMPLATES (90% generic, ported from cryptic-trainer): │
│  - Phases: fodder → result → teaching                       │
│  - Input modes: tap_words, text, multiple_choice, none      │
│  - Panel text with {placeholders}                           │
│  - onCorrect/onWrong feedback                               │
│                                                             │
│  DECORATION (get_render function):                          │
│  Raw step + Template → Interactive UI render object         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Step Types (13):**
- standard_definition, abbreviation, synonym, literal, literal_phrase
- anagram, reversal, deletion, letter_selection, hidden
- container_verify, charade_verify, double_definition

**API Design (same as cryptic-trainer):**
```
POST /trainer/start {clue_id}
  → start_session() → get_render() → {stepType, phaseId, inputMode, panel, ...}

POST /trainer/input {clue_id, input}
  → handle_input() → validate → advance phase/step → get_render()

POST /trainer/continue {clue_id}
  → advance_to_next() → get_render()

POST /trainer/reveal {clue_id}
  → reveal() → {complete: true, answer, highlights}

POST /solve/input   // User submits tap/text/choice
POST /solve/continue // Advance through teaching
POST /solve/reveal  // Skip to answer + full breakdown
```

**Files to Port from cryptic-trainer:**
| Source | Destination | Purpose |
|--------|-------------|---------|
| `training_handler.py` STEP_TEMPLATES | `training_handler.py` (new) | 13 step type templates |
| `training_handler.py` get_render() | Same file | Merge step + template |
| `training_handler.py` handle_input() | Same file | Validate user input |
| `teaching_hints.json` | `teaching_hints.json` | Expert hints |
| `trainer.js` | Keep existing | UI rendering |

**Implementation Steps:**
1. Port `training_handler.py` to Grid Reader (STEP_TEMPLATES, session mgmt, substitute_variables)
2. Add `steps` JSONB column to clues table in Supabase
3. Update `/trainer/*` endpoints to call local handler (remove proxy)
4. Test with imported annotated clues

**Validation:**
- Import puzzle with annotated clues (clues_db.json format)
- Click "Solve" on a clue with steps
- Complete interactive teaching sequence
- Answer auto-fills in grid on completion

---

### Phase 3: Vercel Deployment (No Auth)
Deploy to Vercel as serverless Flask app.

**Changes:**
- Add `vercel.json` configuration
- Adapt Flask app for serverless (stateless)
- Environment variables for Supabase keys
- Static assets served from Vercel

**Validation:** App accessible at public Vercel URL

---

### Phase 4: User Authentication
Add Supabase Auth for user accounts.

**Changes:**
- Add sign up / login UI (Google OAuth + email/password)
- Progress tied to authenticated user
- Row-level security in Supabase
- Guest mode for trying without account

**Validation:** Login works, progress syncs across devices

---

### Phase 5: Multi-User Features & Security
Polish for public release.

**Changes:**
- Rate limiting on `/trainer/*` endpoints
- Input validation / sanitization
- Usage tracking / analytics
- Error handling improvements

**Validation:** Security review, load testing

---

## Publication-Based Architecture (from cryptic-trainer App.tsx)

The trainer app uses a **publication-focused** home page. Users select their "Dojo" (publication) first, then access features within that context.

**User Flow:**
```
HOME → Select Publication (Dojo) → Publication Page → Training/Solver/Manual Entry
```

**Publications (from data.ts):**
| ID | Name | Description | Strictness |
|----|------|-------------|------------|
| `times` | The Times | Pinnacle of cryptic excellence. Strictly fair. | 10/10 |
| `guardian` | The Guardian | Progressive, playful, humorous. Modern style. | 6/10 |
| `telegraph` | Daily Telegraph | Elegant surfaces, consistent mechanisms. | 8/10 |
| `express` | Daily Express | High fairness, straightforward surfaces. | 9/10 |

**Each Publication has:**
- `id`, `name`, `description`
- `logoColor`, `countryFlag`
- `defaultRules` (DojoRules) - Ximenean strictness, indicator style, biases
- `setters[]` - Named setters with difficulty, tips, common themes

**External Bloggers (community links):**
- Big Dave's Blog
- FifteenSquared
- Times for the Times
- Reddit r/crosswords

**Publication Page Features:**
1. **Training Mode** - Practice with clues in the house style
2. **AI Solver** - Scan/paste clues for AI help
3. **Manual Entry** - Type clues or import puzzle files
4. **Settings** - Letter checking toggle

**Design Decisions for Grid Reader:**
- Keep publication-based navigation (users follow specific publications)
- Port `PUBLICATIONS` data structure
- Port `DojoRules` for publication-specific solving hints
- Port external blogger links (community resources)
- Preserve setter metadata for teaching context

---

## Key Architecture Change: Puzzle-Based vs Clue-Based

**cryptic-trainer (old model):** Clue-based
- Individual clues stored in `clues_db.json`
- Training queue is a flat list of clues
- No puzzle context (clue 1A exists independently)
- Cross letters not naturally available

**Grid Reader (new model):** Puzzle-based
- Puzzles are the primary entity (grid + all clues together)
- Users import and solve complete puzzles
- Clues exist within puzzle context
- Cross letters naturally available from grid state
- Progress tracked per puzzle, not per clue

**Data Model Comparison:**

```
OLD (clue-based):
clues_db.json = {
  "times-29453-1a": { clue, answer, steps, ... },
  "times-29453-4a": { clue, answer, steps, ... },
  ...
}

NEW (puzzle-based):
puzzles table = {
  id, series, number, date, grid_layout, ...
}
clues table = {
  id, puzzle_id, number, direction, text, enumeration, answer, ...
}
user_progress table = {
  user_id, puzzle_id, grid_state, selected_cell, ...
}
```

**Benefits of Puzzle-Based:**
1. **Natural cross-letter support** - Grid state provides intersecting letters
2. **Puzzle-level progress** - Track completion %, time spent per puzzle
3. **Import workflow** - PDF → complete puzzle, not individual clues
4. **Leaderboards** - Compare puzzle solve times
5. **Coherent UX** - Users think in puzzles, not isolated clues

**Migration Path:**
- cryptic-trainer's annotated clues can still be imported
- Map `times-29453-1a` → puzzle `times/29453`, clue `1A`
- Step templates and validation logic unchanged

---

## Key Assets to Port from cryptic-trainer

| Asset | Source | Purpose |
|-------|--------|---------|
| `PUBLICATIONS` | `data.ts` | Publication metadata (Times, Guardian, etc.) |
| `DojoRules` | `data.ts` | Publication-specific solving rules/biases |
| `EXTERNAL_BLOGGERS` | `App.tsx` | Community resource links |
| `CRYPTIC_GLOSSARY` | `data.ts` | Indicators by type, abbreviations |
| `ABBREVS` dict | `cryptic_trainer.py` | Standard abbreviations (king→R, five→V) |
| `SYNONYMS` dict | `cryptic_trainer.py` | Common cryptic synonyms |
| `PHRASES` dict | `cryptic_trainer.py` | Definition phrase mappings |
| `STEP_TEMPLATES` | `training_handler.py` | 15+ step types (anagram, container, etc.) |
| `teaching_hints.json` | `cryptic_trainer_bundle/` | Expert-level explanations |
| `learned_synonyms.json` | `cryptic_trainer_bundle/` | Validated synonym cache |
| Validation logic | `training_handler.py` | Constraint-based answer checking |

**Design Principles to Preserve:**
1. **Stateless client** - See "CRITICAL: Stateless Client Architecture" section above
2. **Constraint-first validation** - No AI guessing for grading
3. **Hypothesis-driven solving** - Definition → hypothesis → verify wordplay
4. **Two-path verification** - Answer must work via definition AND wordplay

---

## Decisions Made

- **LLM Provider**: Abstract interface, decide in Phase 2 (support both Anthropic/OpenAI)
- **Auth method**: Both Google OAuth and email/password
- **Pricing model**: TBD (decide before Phase 5)

---

## Files to Modify (Phase 1)

| File | Changes |
|------|---------|
| `puzzle_store.py` | Replace file ops with Supabase client |
| `crossword_server.py` | Use new puzzle_store, add session progress |
| `requirements.txt` | Add `supabase` package |
| `.env` | Supabase URL + key |

## Supabase Project

**Project URL:** `https://tycvflrjvlvmsiokjaef.supabase.co`
**Anon Key:** `sb_publishable_ZJKuj06UILTJewkA_gy2xg_U7fSYEwr`

Note: Service role key needed for server-side operations (get from Supabase dashboard → Settings → API)

---

## Database Schema (Phase 1)

```sql
-- Publications (Times, Guardian, etc.)
CREATE TABLE publications (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  logo_color TEXT,
  country_flag TEXT,
  ximenean_strictness INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Puzzles (the primary entity)
CREATE TABLE puzzles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  publication_id TEXT REFERENCES publications(id),
  puzzle_number TEXT NOT NULL,
  title TEXT,
  date DATE,
  grid_layout JSONB NOT NULL,  -- 2D array of cell types
  grid_size INTEGER NOT NULL,  -- e.g., 15 for 15x15
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(publication_id, puzzle_number)
);

-- Clues (belong to puzzles)
CREATE TABLE clues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('across', 'down')),
  text TEXT NOT NULL,
  enumeration TEXT NOT NULL,  -- e.g., "6" or "3-4"
  answer TEXT,  -- NULL if answers not provided
  start_row INTEGER NOT NULL,
  start_col INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(puzzle_id, number, direction)
);

-- User progress (per puzzle)
CREATE TABLE user_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,  -- anonymous session initially, user_id later
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  grid_state JSONB NOT NULL,  -- 2D array of entered letters
  selected_cell JSONB,  -- {row, col}
  direction TEXT,  -- 'across' or 'down'
  started_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  UNIQUE(session_id, puzzle_id)
);

-- Indexes for common queries
CREATE INDEX idx_puzzles_publication ON puzzles(publication_id);
CREATE INDEX idx_clues_puzzle ON clues(puzzle_id);
CREATE INDEX idx_progress_session ON user_progress(session_id);
CREATE INDEX idx_progress_puzzle ON user_progress(puzzle_id);
```

---

## Verification (Phase 1)
1. ~~Create Supabase project~~ ✓ Done
2. Run migrations to create tables
3. Start local server with Supabase connection
4. Import a puzzle → verify in Supabase dashboard
5. Solve partially → verify progress saved to DB
