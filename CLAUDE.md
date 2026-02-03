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

## Architecture

```
Grid Reader (8080) ──proxy──► cryptic-trainer (5001)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (solving UI)
     └── crossword_server.py (Flask, /trainer/* proxy)
```

## Recent Features
- **Progress persistence**: localStorage auto-saves puzzle progress (survives refresh)
- **Auto-apply answers**: Trainer answers auto-fill grid when solved (no button)
- **Keyboard shortcuts**: Cmd+R etc. work (not intercepted by grid)

## TODO (Major)
Replace complex trainer integration with simple `/solve` endpoint:
```
POST /solve { clue, enumeration, cross_letters }
Response: { answer, confidence, explanation }
```
This would eliminate cryptic-trainer dependency and session state issues.

## Common Commands
```bash
git status && git diff                    # Check changes
git add <files> && git commit -m "msg"    # Commit
git push                                  # Push to main
```

## Cache Busting
When changing JS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=13"></script>
```

## Storage
Puzzles stored in `puzzles/{series}/{number}/`:
- `puzzle.json` - grid, clues
- `original.pdf` - source PDF
- `answers.json` - optional answers
