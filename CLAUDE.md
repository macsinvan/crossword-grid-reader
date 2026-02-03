# Grid Reader - Claude Context

## What This Is
Web-based Times Cryptic crossword solver. Import PDFs, solve interactively, get AI-assisted solving via cryptic-trainer integration.

## Quick Start
```bash
# Terminal 1: Trainer API (optional, for guided solving)
cd ../cryptic-trainer/cryptic_trainer_bundle && python3 server.py  # port 5001

# Terminal 2: Grid Reader
python3 crossword_server.py  # port 8080
```
Open http://localhost:8080

## Key Files

| File | Purpose |
|------|---------|
| `crossword_server.py` | Flask server (port 8080), proxies to trainer |
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence |
| `static/trainer.js` | TemplateTrainer (ported from React) |
| `pdf_processor.py` | PDF parsing, grid/clue extraction |
| `crossword_processor.py` | Grid structure detection |
| `puzzle_store.py` | Puzzle storage in `puzzles/` directory |
| `templates/index.html` | Web UI (bump `?v=N` for cache busting) |

## Architecture

```
Grid Reader (8080) ──proxy──► cryptic-trainer (5001)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (solving UI)
     └── crossword_server.py (Flask, /trainer/* proxy)
```

### Trainer Integration Flow
1. User clicks "Solve" → `crossword.js` calls `/trainer/start`
2. Server looks up clue by ID (e.g., `times-29453-1a`)
3. Auto-imports from `../Times_Puzzle_Import/solved/` if needed
4. Proxies to cryptic-trainer `/training/start`
5. `trainer.js` renders the training UI
6. On completion, answer auto-applies to grid

## Recent Features
- **Progress persistence**: localStorage auto-saves puzzle progress (survives refresh)
- **Auto-apply answers**: Trainer answers auto-fill grid when solved (no button)
- **Keyboard shortcuts**: Cmd+R etc. work (not intercepted by grid)

## Storage
Puzzles stored in `puzzles/{series}/{number}/`:
- `puzzle.json` - grid, clues
- `original.pdf` - source PDF
- `answers.json` - optional answers

## Common Commands
```bash
git status && git diff                    # Check changes
git add <files> && git commit -m "msg"    # Commit
git push                                  # Push to main
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=13"></script>
```

## TODO

### Replace trainer integration with simple LLM solve

**Current state (deprecated/experimental):** The trainer integration is complex and fragile:
- Requires pre-annotated clues in a separate database
- Maintains session state on the cryptic-trainer server
- State easily gets out of sync between browser and server
- Ported React UI adds complexity

**Target architecture:** Single `/solve` endpoint:

```
POST /solve
{
  "clue": "See boss bungle work (6)",
  "enumeration": "6",
  "cross_letters": [{"position": 2, "letter": "S"}]
}

Response:
{
  "answer": "BISHOP",
  "confidence": 0.95,
  "explanation": "Definition: 'See boss' (BISHOP runs a diocese/see). Wordplay: bungle=BISH + work=OP"
}
```

**Benefits:**
- Single server - no cryptic-trainer dependency
- No session state to manage
- No pre-annotation required
- Works on any clue

**Implementation:**
- Copy LLM solving logic from cryptic-trainer
- Delete trainer.js and proxy code
- Add `/solve` endpoint
- Simple UI: "Solving..." → answer + explanation
