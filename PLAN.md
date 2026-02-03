# Plan: Grid Reader → Public Multi-User Web App

## Target Stack
- **Backend**: Flask on Vercel (serverless functions)
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth
- **Frontend**: Static HTML/JS (current) served from Vercel

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

### Phase 2: LLM-Powered Teaching Mode
Preserve the step-by-step teaching experience, but use LLM to generate steps dynamically instead of requiring pre-annotated clues.

**Critical Anti-Hallucination Architecture** (from cryptic-trainer DESIGN_SPEC.md):

The current system prevents hallucination through:
1. **Ground Truth Validation** - All answers validated against known correct values
2. **Constraint-First Solving** - No AI guessing; uses lexicon lookups + pattern matching
3. **Static Lexicons** - Small, auditable ABBREVS/SYNONYMS dictionaries
4. **Learned Cache** - Only validated synonyms (confirmed during training) are persisted

**Why this matters:** LLMs are creative and will always produce an answer, but often with flawed hypotheses. The system must VERIFY, not trust.

**New Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 2 Solver Architecture                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. LLM generates hypothesis + step breakdown                │
│     (answer, definition, wordplay components)                │
│                                                              │
│  2. Constraint engine VALIDATES each step:                   │
│     - Abbreviations checked against ABBREVS lexicon          │
│     - Synonyms checked against SYNONYMS + learned cache      │
│     - Letter math verified (fodder letters = result)         │
│     - Container/charade operations verified algebraically    │
│                                                              │
│  3. If validation fails → LLM re-prompts or "Reveal" shows   │
│     honest uncertainty ("Could not verify this step")        │
│                                                              │
│  4. Teaching UI unchanged - server-driven, thin client       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**API Design:**

```
POST /solve/start
{
  "clue": "See boss bungle work (6)",
  "enumeration": "6",
  "cross_letters": [{"position": 2, "letter": "S"}]
}

Response:
{
  "session_id": "abc123",
  "render": { ... },  // First teaching step
  "verified": true,   // All steps passed constraint validation
  "confidence": 0.95
}

POST /solve/input   // User submits tap/text/choice
POST /solve/continue // Advance through teaching
POST /solve/reveal  // Skip to answer + full breakdown
```

**Key Constraint Checks:**
- `ABBREVS` dict: {"golf": ["G"], "husband": ["H"], ...}
- `SYNONYMS` dict: {"pity": ["RUTH"], "help": ["AID"], ...}
- `LEARNED_SYNONYMS`: Validated during training, persisted
- Letter count verification: sum(components) == answer length
- Definition validation: must match in PHRASES/SYNONYMS tables

**Changes:**
- Port `ABBREVS`, `SYNONYMS`, `PHRASES` from cryptic-trainer
- Port `LEARNED_SYNONYMS` persistence (learned_synonyms.json)
- Create LLM interface (Anthropic + OpenAI)
- Add `/solve/*` endpoints with constraint validation
- Keep `trainer.js` UI (server-driven rendering unchanged)
- Delete cryptic-trainer proxy code (self-contained)

**Validation:**
- Teaching mode works on any clue (not just pre-annotated)
- "Reveal" button shows answer + verified breakdown
- Unverified steps show honest uncertainty

---

### Phase 3: Vercel Deployment (No Auth)
Deploy to Vercel as serverless Flask app.

**Changes:**
- Add `vercel.json` configuration
- Adapt Flask app for serverless (stateless)
- Environment variables for Supabase + LLM keys
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
- Rate limiting on `/solve` endpoint
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
1. **Server-driven rendering** - UI has zero phase logic
2. **Thin client** - All business logic on server
3. **Constraint-first validation** - No AI guessing for grading
4. **Hypothesis-driven solving** - Definition → hypothesis → verify wordplay
5. **Two-path verification** - Answer must work via definition AND wordplay

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

## Verification (Phase 1)
1. Create Supabase project
2. Run migrations to create tables
3. Start local server with Supabase connection
4. Import a puzzle → verify in Supabase dashboard
5. Solve partially → verify progress saved to DB
