# Crossword Grid Reader

A web-based tool for importing, solving, and learning to solve Times Cryptic crossword puzzles from PDF files.

> **Developers**: See [CLAUDE.md](CLAUDE.md) for architecture and [TECH_DEBT_AUDIT.md](TECH_DEBT_AUDIT.md) for cleanup plan.

## Features

- **PDF Import**: Upload Times Cryptic PDF files to extract grid and clues automatically
- **Cloud Storage**: Puzzles stored in Supabase PostgreSQL (with local fallback)
- **Interactive Grid**: Solve puzzles in the browser with keyboard navigation
- **Guided Solving**: Step-by-step teaching mode for learning cryptic techniques
- **Answer Validation**: Optionally provide an answers file to validate your solutions
- **Progress Persistence**: Puzzle progress auto-saves to browser localStorage

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (copy and edit with your Supabase credentials)
cp .env.example .env

# Start the server
python crossword_server.py
```

Open http://localhost:8080

A green status indicator shows when connected to Supabase cloud database.

## Usage

### Importing Puzzles

1. Click "Import PDF" tab
2. Upload a Times Cryptic PDF file
3. Optionally add an answers file for validation

### Solving

- **Click** a cell or clue to select it
- **Type** letters to fill in answers (auto-advances)
- **Space** toggles between Across and Down
- **Arrow keys** navigate the grid
- **Tab/Shift+Tab** moves between clues
- **Backspace** clears and moves back

### Controls

- **Solve**: Opens guided teaching mode for selected clue (requires annotated clues)
- **Check Answers**: Highlights incorrect cells (requires answers)
- **Clear Grid**: Removes all entered letters
- **Reveal All**: Shows the complete solution (requires answers)

### Guided Solving (Teaching Mode)

For clues with pre-annotated step data:
1. Select a clue and click "Solve"
2. Follow step-by-step guidance through the clue
3. Learn cryptic techniques: abbreviations, anagrams, reversals, etc.
4. Answer auto-fills in grid on completion

### Progress Saving

Your progress auto-saves to browser localStorage and survives page refresh.

## File Formats

### Answers File (Optional)

YAML format:
```yaml
across:
  - number: 1
    answer: "SCREEN"
down:
  - number: 1
    answer: "STOOGE"
```

Or JSON (Times Puzzle Import format):
```json
{
  "times-29453-1a": {
    "clue": { "number": "1A", "answer": "SCREEN" }
  }
}
```

## API Endpoints

### Puzzle Management
- `GET /puzzles` - List all puzzles
- `GET /puzzles/<series>/<number>` - Get specific puzzle
- `POST /upload` - Import a PDF
- `POST /puzzles/<series>/<number>/answers` - Add answers
- `DELETE /puzzles/<series>/<number>` - Delete puzzle

### Status
- `GET /status` - Check database connection status

### Validation
- `POST /validate` - Check answers against solution

## Common Issues

### Grid not detected
- Ensure PDF contains a clear grid image
- Grid should be roughly square (aspect ratio 0.8-1.2)

### Supabase connection failed
- Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_ANON_KEY`
- Run migrations in Supabase SQL Editor (see `migrations/001_initial_schema.sql`)
- App falls back to local file storage if Supabase unavailable

## Supported Formats

- **Times Cryptic** (15x15 grid)
- **Times Quick Cryptic** (13x13 grid)

## Development Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Supabase Integration | ✅ Complete | Cloud database storage |
| 2. Teaching Mode | ✅ Complete | Local step-by-step guided solving |
| 3. Vercel Deployment | 🔜 Next | Serverless Flask deployment |
| 4. User Authentication | Planned | Supabase Auth integration |
| 5. Multi-User Features | Planned | Rate limiting, analytics |

See [PLAN.md](PLAN.md) for detailed roadmap.

## Technical Notes

- Teaching mode uses pre-annotated step data (no AI/LLM)
- 30 clues pre-loaded in `clues_db.json`
- See [TECH_DEBT_AUDIT.md](TECH_DEBT_AUDIT.md) for architecture details

## License

MIT
