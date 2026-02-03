# Grid Reader - Claude Context

## IMPORTANT: Implementation Rules

### 1. Design Documentation Required
**DO NOT IMPLEMENT WITHOUT CONSULTING:**
1. `PLAN.md` - Full roadmap and architecture decisions
2. `/Users/andrewmackenzie/.claude/plans/elegant-swimming-lollipop.md` - Active implementation plan

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

## What This Is
Web-based Times Cryptic crossword solver. Import PDFs, solve interactively, get step-by-step teaching via ported cryptic-trainer system.

## Quick Start
```bash
# Ensure .env file exists with Supabase credentials (see .env.example)

# Terminal: Grid Reader
python3 crossword_server.py  # port 8080

# Optional: Trainer API (for guided solving - legacy)
cd ../cryptic-trainer/cryptic_trainer_bundle && python3 server.py  # port 5001
```
Open http://localhost:8080

## Key Files

| File | Purpose |
|------|---------|
| `crossword_server.py` | Flask server (port 8080), proxies to trainer |
| `puzzle_store_supabase.py` | Supabase database storage (Phase 1) |
| `puzzle_store.py` | Local file-based storage (fallback) |
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence |
| `static/trainer.js` | TemplateTrainer (ported from React) |
| `pdf_processor.py` | PDF parsing, grid/clue extraction |
| `crossword_processor.py` | Grid structure detection |
| `templates/index.html` | Web UI (bump `?v=N` for cache busting) |
| `migrations/001_initial_schema.sql` | Supabase database schema |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (solving UI)
     ├── crossword_server.py (Flask)
     │        │
     │        ├── puzzle_store_supabase.py → Supabase PostgreSQL (cloud)
     │        └── puzzle_store.py → Local files (fallback)
     │
     └──proxy──► cryptic-trainer (5001) [optional, legacy]
```

### Database Backend
The app auto-detects storage backend:
- **Supabase** (preferred): If `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in `.env`
- **Local files**: Falls back to `puzzles/` directory if Supabase not configured

A status indicator (green LED = Supabase, yellow = local) shows in the header.

### Teaching Mode Flow (Phase 2)
**Architecture:** Server-driven rendering, thin client

1. User clicks "Solve" → `crossword.js` calls `/trainer/start` with clue_id
2. Server loads clue with pre-annotated `steps` array from database
3. `training_handler.py` merges raw step + STEP_TEMPLATE → render object
4. `trainer.js` displays phases (tap_words, text input, teaching panels)
5. User input validated via `handle_input()` against `expected` values
6. On completion, answer auto-applies to grid

**Step Types:** standard_definition, abbreviation, synonym, literal, anagram, reversal, deletion, letter_selection, hidden, container_verify, charade_verify, double_definition, literal_phrase

**Data Source:** Steps come from pre-annotated `clues_db.json` format (NO AI generation)

## Recent Features
- **Supabase integration**: Cloud database storage (Phase 1 complete)
- **DB status indicator**: Shows connection status in header
- **Progress persistence**: localStorage auto-saves puzzle progress (survives refresh)
- **Auto-apply answers**: Trainer answers auto-fill grid when solved (no button)
- **Keyboard shortcuts**: Cmd+R etc. work (not intercepted by grid)

## Storage

### Supabase Tables (Phase 1)
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
git status && git diff                    # Check changes
git add <files> && git commit -m "msg"    # Commit
git push                                  # Push to main
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=14"></script>
```

## Development Roadmap

See `PLAN.md` for full roadmap. Summary:

### Phase 1: Supabase Database Integration ✓ Complete
- Supabase PostgreSQL backend
- Publications, puzzles, clues, user_progress tables
- Auto-fallback to local storage
- DB status indicator

### Phase 2: Interactive Teaching Mode (Next) - NO AI
- Port `training_handler.py` from cryptic-trainer (STEP_TEMPLATES, get_render, handle_input)
- Step data is PRE-ANNOTATED in imported JSON (clues_db.json format)
- Templates decorate raw steps into interactive phases (tap_words, text, multiple_choice)
- Remove proxy to cryptic-trainer; run locally
- See `PLAN.md` for full architecture

### Phase 3: Vercel Deployment
- Serverless Flask on Vercel
- Environment variables for keys

### Phase 4: User Authentication
- Supabase Auth (Google OAuth + email/password)
- Row-level security

### Phase 5: Multi-User Features
- Rate limiting, analytics, polish
