# Grid Reader - Claude Context

## What This Is
Web-based Times Cryptic crossword solver. Import PDFs, solve interactively, get AI-assisted solving via cryptic-trainer integration.

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

### Trainer Integration Flow (Legacy)
1. User clicks "Solve" → `crossword.js` calls `/trainer/start`
2. Server looks up clue by ID (e.g., `times-29453-1a`)
3. Auto-imports from `../Times_Puzzle_Import/solved/` if needed
4. Proxies to cryptic-trainer `/training/start`
5. `trainer.js` renders the training UI
6. On completion, answer auto-applies to grid

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

### Phase 2: LLM-Powered Teaching Mode (Next)
- Replace pre-annotated clues with dynamic LLM solving
- Constraint-based validation (anti-hallucination)
- `/solve/*` endpoints

### Phase 3: Vercel Deployment
- Serverless Flask on Vercel
- Environment variables for keys

### Phase 4: User Authentication
- Supabase Auth (Google OAuth + email/password)
- Row-level security

### Phase 5: Multi-User Features
- Rate limiting, analytics, polish
