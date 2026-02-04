# Grid Reader - Claude Context

## Communication Rules

**When I ask a direct question, answer it directly. Never take my question as a request to take action.**

## IMPORTANT: Implementation Rules

### 0. NO CODING WITHOUT A DESIGN SPEC
**If a feature is not documented in the design spec, DO NOT implement it.** Ask for the specification first.

### 1. Design Documentation Required
**DO NOT IMPLEMENT WITHOUT CONSULTING:**
1. `SPEC.md` - **Technical Specification** (reproducible app spec)

**All design documents MUST be in the working directory and tracked in the repo.**

### 2. Verification Required
**EVERY PLAN MUST:**
1. **Start with verification strategy** - Define how you will test the feature works
2. **End with verification completed** - Actually test in browser, not just API calls

**Verification Checklist:**
- [ ] Server starts without errors
- [ ] UI loads at http://127.0.0.1:8080/
- [ ] Feature works end-to-end in browser (click through the UI)
- [ ] No JavaScript console errors
- [ ] No Python server errors

### 3. Key Constraints

**STATELESS CLIENT ARCHITECTURE**
The trainer UI (`trainer.js`) is a **dumb rendering layer with ZERO state**:
- ALL state lives on the server (session dict in `training_handler.py`)
- Client receives a `render` object and displays it - nothing more
- User interactions call server endpoints which return updated `render` objects
- Client has no local variables for: selections, input values, visibility flags, etc.
- If you're tempted to add `this.foo = ...` in trainer.js, STOP - it belongs on the server

**Exception: Silent server sync for typing**
Answer/step input boxes sync to server on each keystroke BUT don't trigger re-render (to preserve focus). Only re-render when server sets `answerLocked=true`.

**Step state resets on advance**
When `step_index` increments, `reset_step_ui_state()` clears: `hint_visible`, `selected_indices`, `step_text_input`. Answer boxes persist across steps.

**NO AI/LLM in this app.** Teaching mode uses pre-annotated step data from imported JSON files, NOT dynamically generated explanations.

**Auto-reload clues_db.json**
The server checks file modification time on each `/trainer/start` request. If `clues_db.json` has changed, it reloads automatically - no server restart needed.

**Error out, don't fallback**
Don't build in silent fallbacks that get forgotten and cause confusion. Error out explicitly instead.

## What This Is
Web-based Times Cryptic crossword solver. Import PDFs, solve interactively, get step-by-step teaching via template-based step display system.

## Quick Start
```bash
# Ensure .env file exists with Supabase credentials (see .env.example)
python3 crossword_server.py  # port 8080
```
Open http://localhost:8080

## Key Files

| File | Purpose |
|------|---------|
| `crossword_server.py` | Flask server (port 8080) |
| `training_handler.py` | Teaching mode logic: STEP_TEMPLATES, get_render(), handle_input() |
| `step_display_templates.py` | Template definitions for step types |
| `clues_db.json` | Pre-annotated clue database (30 clues with template metadata) |
| `static/trainer.js` | Stateless trainer UI (renders server state) |
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence |
| `puzzle_store_supabase.py` | Supabase database storage |
| `puzzle_store.py` | Local file-based storage (fallback) |
| `pdf_processor.py` | PDF parsing, grid/clue extraction |
| `crossword_processor.py` | Grid structure detection |
| `templates/index.html` | Web UI (bump `?v=N` for cache busting) |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (stateless teaching UI)
     ├── crossword_server.py (Flask)
     │        │
     │        ├── training_handler.py (teaching logic)
     │        ├── puzzle_store_supabase.py → Supabase PostgreSQL
     │        └── puzzle_store.py → Local files (fallback)
     │
     └── clues_db.json (30 annotated clues)
```

### Database Backend
The app auto-detects storage backend:
- **Supabase** (preferred): If `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in `.env`
- **Local files**: Falls back to `puzzles/` directory if Supabase not configured

A status indicator (green LED = Supabase, yellow = local) shows in the header.

## Teaching Mode (Template-Based Step Display)

### Architecture
Server-driven rendering with thin client:

1. User clicks "Solve" → `crossword.js` calls `/trainer/start` with clue_id
2. Server loads clue with pre-annotated `steps` array from `clues_db.json`
3. `training_handler.py` merges raw step + STEP_TEMPLATE → render object
4. `trainer.js` displays phases (tap_words, text input, teaching panels)
5. User input validated via `handle_input()` against `expected` values
6. On completion, answer auto-applies to grid

### Template System
Templates define how each step type is displayed:

**Step Templates** (in `training_handler.py`):
- `charade_with_parts` - Multi-part wordplay assembly
- `anagram_with_fodder_pieces` - Anagram with letter mixing
- `insertion_with_two_synonyms` - Container clues (A inside B)
- `insertion_with_charade_inner` - Container with charade components
- `transformation_chain` - Multi-step transformations

**Part Types** (within templates):
- `synonym` - Word meaning another
- `abbreviation` - Standard abbrev (piano=P, five=V)
- `literal` - Word used as-is
- `literal_phrase` - Phrase read literally
- `synonym_then_deletion` - Synonym with letter removal
- `synonym_then_reversal` - Synonym reversed
- `abbreviation_synonym_reversed` - Abbrev of reversed synonym
- `letter_selection` - First/last/middle letters
- `hidden` - Hidden word in phrase

### Step Types (in clues_db.json)
- `standard_definition` - Definition identification
- `charade` - Parts assembled in sequence
- `anagram` - Letters rearranged
- `container` - One word inside another
- `reversal` - Word reversed
- `deletion` - Letter(s) removed
- `hidden` - Answer hidden in clue text
- `double_definition` - Two definitions
- `transformation_chain` - Multiple operations

### Clue Metadata Format
```json
{
  "id": "times-29453-4a",
  "clue": {"number": "4A", "text": "...", "answer": "REPROACH"},
  "words": ["Twit", "copying", "antique", ...],
  "steps": [
    {
      "type": "standard_definition",
      "expected": {"indices": [0], "text": "Twit"},
      "position": "start"
    },
    {
      "type": "charade",
      "template": "charade_with_parts",
      "parts": [
        {
          "fodder": {"indices": [1, 2], "text": "copying antique"},
          "result": "REPRO",
          "type": "synonym",
          "reasoning": "A repro is a reproduction"
        }
      ],
      "result": "REPROACH",
      "assembly": "REPRO + ACH = REPROACH"
    }
  ]
}
```

## Current State

### Completed Features
- ✅ Supabase integration (Phase 1)
- ✅ Template-based step display system (Phase 2)
- ✅ 30 clues fully annotated with templates
- ✅ Mobile responsive grid
- ✅ Progress persistence (localStorage)
- ✅ Auto-apply answers to grid

### Data
- 30 annotated clues from Times puzzle 29453
- All step types have working templates
- clues_db.json auto-reloads on change

## Mobile Design Principles

**Grid uses CSS Grid with `1fr` units, NOT fixed pixel sizes.**

Key implementation:
- `crossword.js` sets `grid-template-columns: repeat(N, 1fr)`
- Cells use `aspect-ratio: 1` to stay square
- Mobile breakpoint at 600px uses `width: calc(100vw - 26px)`
- Font sizes use `clamp()` for fluid scaling

See `SPEC.md` Section 10 for full details.

## Storage

### Supabase Tables
- `publications` - Times, Guardian, Telegraph, Express
- `puzzles` - Primary entity (grid + metadata)
- `clues` - Belong to puzzles
- `user_progress` - Per-puzzle progress tracking

### Local Fallback
Puzzles stored in `puzzles/{series}/{number}/`:
- `puzzle.json` - grid, clues
- `original.pdf` - source PDF
- `answers.json` - optional answers

## Environment Variables
Create `.env` file (see `.env.example`):
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

## Common Commands
```bash
# Start server
python3 crossword_server.py

# Git workflow
git status && git diff
git add <files> && git commit -m "msg"
git push

# Validate clues_db.json
python3 -c "import json; json.load(open('clues_db.json')); print('Valid')"
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=21"></script>
```

## Development Roadmap

### Phase 1: Supabase Database Integration ✅ Complete
### Phase 2: Template-Based Teaching Mode ✅ Complete
### Phase 3: Vercel Deployment (Next)
- Serverless Flask on Vercel
- Environment variables for keys

### Phase 4: User Authentication
- Supabase Auth (Google OAuth + email/password)
- Row-level security

### Phase 5: Multi-User Features
- Rate limiting, analytics, polish

See `PLAN.md` for full roadmap.

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch
- `/Users/andrewmackenzie/Desktop/Grid Reader/upbeat-driscoll` - upbeat-driscoll branch

To switch work between branches, cd to the appropriate directory.
