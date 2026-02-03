# Crossword Grid Reader

A web-based tool for importing, solving, and learning to solve Times Cryptic crossword puzzles from PDF files.

> **Developers**: See [CLAUDE.md](CLAUDE.md) for architecture, key files, and development context.

## Features

- **PDF Import**: Upload Times Cryptic PDF files to extract grid and clues automatically
- **Puzzle Storage**: Store imported puzzles organized by series (e.g., "Times Cryptic")
- **Interactive Grid**: Solve puzzles in the browser with keyboard navigation
- **Answer Validation**: Optionally provide an answers file to validate your solutions
- **Guided Solving**: Click "Solve" on any clue for AI-assisted solving (requires cryptic-trainer)
- **Progress Persistence**: Puzzle progress auto-saves to browser localStorage

## Quick Start

```bash
# Install dependencies
pip install opencv-python numpy pyyaml flask pdfplumber Pillow requests

# Start the server
python crossword_server.py
```

Open http://localhost:8080

For guided solving, also run cryptic-trainer on port 5001 (see [CLAUDE.md](CLAUDE.md)).

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

- **Check Answers**: Highlights incorrect cells (requires answers)
- **Clear Grid**: Removes all entered letters
- **Reveal All**: Shows the complete solution (requires answers)
- **Solve**: Opens guided solving for current clue (requires cryptic-trainer)

### Progress Saving

Your progress auto-saves to browser localStorage and survives page refresh.

## Guided Solving

Click **Solve** on any clue to open the trainer:

1. **Clue Display**: Shows the full clue with tappable words
2. **Answer Boxes**: Shows progress with cross letters highlighted
3. **Step-by-step Guidance**: Walks through definition, indicators, and wordplay
4. **Auto-Apply**: Solved answers automatically fill the grid

**Requirements**:
- cryptic-trainer server running on port 5001
- Annotated clue data in `../Times_Puzzle_Import/solved/`

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

### Validation
- `POST /validate` - Check answers against solution

### Trainer (requires cryptic-trainer)
- `POST /trainer/start` - Start training session
- `POST /trainer/input` - Submit user input
- `POST /trainer/continue` - Next step

## Common Issues

### Grid not detected
- Ensure PDF contains a clear grid image
- Grid should be roughly square (aspect ratio 0.8-1.2)

### "Clue not found in trainer database"
Place annotated files in `../Times_Puzzle_Import/solved/` named `Times_XXXXX_v2.json`

### Cannot connect to trainer
```bash
cd ../cryptic-trainer/cryptic_trainer_bundle
python3 server.py
```

## Supported Formats

- **Times Cryptic** (15x15 grid)
- **Times Quick Cryptic** (13x13 grid)

## License

MIT
