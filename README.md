# Crossword Grid Reader

A web-based tool for importing, solving, and learning to solve Times Cryptic crossword puzzles from PDF files. Integrates with the cryptic-trainer for guided solving assistance.

## Features

- **PDF Import**: Upload Times Cryptic PDF files to extract grid and clues automatically
- **Puzzle Storage**: Store imported puzzles organized by series (e.g., "Times Cryptic")
- **Interactive Grid**: Solve puzzles in the browser with keyboard navigation
- **Answer Validation**: Optionally provide an answers file to validate your solutions
- **Guided Solving**: Click "Solve" on any clue to get step-by-step solving guidance (requires cryptic-trainer)
- **Cross Letter Support**: Pre-filled letters from intersecting words appear in the trainer
- **Robust Grid Detection**: Uses edge detection and contour analysis to handle various PDF formats

## Requirements

```bash
pip install opencv-python numpy pyyaml flask pdfplumber Pillow requests
```

For guided solving, you also need the cryptic-trainer running:
```bash
cd ../cryptic-trainer/cryptic_trainer_bundle
python3 server.py  # Runs on port 5001
```

## Quick Start

1. Start the web server:
   ```bash
   python crossword_server.py
   ```

2. Open http://localhost:8080 in your browser

3. Click "Import PDF" and upload a Times Cryptic PDF file

4. Click "Play" on a stored puzzle to start solving

5. Click the "Solve" button on any clue for guided assistance

## Web Interface

### My Puzzles Tab

View and manage your imported puzzles:
- **Series Filter**: Filter by puzzle series (Times Cryptic, etc.)
- **Puzzle List**: Shows puzzle number, date, and whether answers are available
- **Play**: Open a puzzle to solve
- **Add Answers**: Upload an answers file for validation
- **Delete**: Remove a puzzle from storage

### Import PDF Tab

Upload new puzzles:
- **PDF File (required)**: A Times Cryptic PDF containing the grid and clues
- **Answers File (optional)**: A JSON or YAML file with answers for validation

The importer automatically extracts:
- Grid layout and structure
- Across and Down clues
- Puzzle date (e.g., "Friday, 16 January 2026")
- Puzzle number (e.g., 29453)
- Series name (e.g., "Times Cryptic")

### Solving Interface

#### Grid Navigation
- **Click** a cell or clue to select it
- **Type** letters to fill in answers (auto-advances to next cell)
- **Space** toggles between Across and Down direction
- **Tab** / **Shift+Tab** moves to next/previous clue
- **Arrow keys** navigate the grid
- **Backspace** clears and moves back

#### Current Clue Bar
Below the grid, showing:
- Current clue number and direction (e.g., "7A")
- Full clue text
- **Solve** button - opens guided solving trainer

#### Controls
- **Check Answers**: Highlights incorrect cells (requires answers)
- **Clear Grid**: Removes all entered letters
- **Reveal All**: Shows the complete solution (requires answers)
- **Back to Puzzles**: Return to puzzle list

### Guided Solving (Trainer Integration)

Click the **Solve** button to open the trainer modal:

1. **Clue Display**: Shows the full clue text
2. **Answer Boxes**: Crossword-style boxes with:
   - Empty boxes for unknown letters
   - Yellow boxes for cross letters (filled from intersecting words)
   - Green boxes for solved letters
3. **Instructions**: Step-by-step guidance through the solving process
4. **Word Selection**: Tap clue words to identify parts (definition, indicator, fodder)
5. **Text Input**: Enter answers or intermediate results
6. **Apply to Grid**: Transfer the solved answer back to the puzzle

The trainer walks you through:
- Finding the definition
- Identifying wordplay indicators
- Recognizing anagram fodder
- Solving the cryptic construction

**Note**: Guided solving requires:
- The cryptic-trainer server running on port 5001
- The clue must be annotated in the trainer database

### Auto-Import from Annotated Files

If you have annotated puzzle files (from Times_Puzzle_Import), the trainer integration supports **automatic import**:

1. Place annotated puzzle files in `../Times_Puzzle_Import/solved/` (relative to Grid Reader)
2. Files should be named `Times_XXXXX_v2.json` (e.g., `Times_29453_v2.json`)
3. When you click "Solve" on a clue, if the puzzle isn't in the trainer database but an annotated file exists, it will be **automatically imported**

This means you don't need to manually import puzzles into the trainer - just have the annotated JSON files in the right location.

## File Formats

### Answers File (Optional)

If you want answer validation, provide a JSON or YAML file:

```yaml
across:
  - number: 1
    answer: "SCREEN"
  - number: 4
    answer: "APELIKE"
  # ... more clues

down:
  - number: 1
    answer: "STOOGE"
  - number: 2
    answer: "OMERTA"
  # ... more clues
```

Or in JSON (Times Puzzle Import format):

```json
{
  "times-29453-1a": {
    "clue": {
      "number": "1A",
      "answer": "SCREEN"
    }
  }
}
```

## Storage Structure

Imported puzzles are stored in the `puzzles/` directory:

```
puzzles/
├── Times Cryptic/
│   ├── 29453/
│   │   ├── puzzle.json    # Grid, clues, numbering
│   │   ├── original.pdf   # Original PDF file
│   │   └── answers.json   # Answers (if provided)
│   └── 29454/
│       └── ...
└── Times Quick Cryptic/
    └── ...
```

## API Endpoints

### Puzzle Management
- `GET /puzzles` - List all puzzles (optional `?series=` filter)
- `GET /puzzles/<series>/<number>` - Get specific puzzle
- `POST /upload` - Import a PDF (multipart form)
- `POST /puzzles/<series>/<number>/answers` - Add answers file
- `DELETE /puzzles/<series>/<number>` - Delete a puzzle

### Validation
- `POST /validate` - Check answers against solution

### Trainer Proxy (requires cryptic-trainer on port 5001)
- `POST /trainer/start` - Start a training session for a clue (auto-imports if annotated file exists)
- `POST /trainer/input` - Submit user input to trainer
- `POST /trainer/continue` - Skip to next training step
- `POST /trainer/import-puzzle` - Manually import a puzzle from annotated files
- `GET /trainer/check-puzzle?puzzle_number=XXXXX` - Check if annotated data exists for a puzzle

## Command Line Usage

The grid processor can also be used from the command line:

```bash
python crossword_processor.py <grid_image> <clues_yaml> [output_yaml]
```

### Example

```bash
python crossword_processor.py puzzle.png clues.yaml output.yaml
```

## How It Works

### PDF Processing

1. **Extract Metadata**: Parse date, puzzle number, and series from PDF header
2. **Extract Grid Image**: Crop the PDF to isolate the crossword grid
3. **Extract Clues**: Parse the two-column clue layout (Across/Down)
4. **Detect Grid Structure**: Find grid boundary and cell positions
5. **Identify Black Squares**: Sample cell centers to classify black/white cells
6. **Number Clues**: Assign sequential numbers based on standard crossword rules

### Grid Detection

The processor uses two methods for finding the grid:

1. **Contour Detection** (primary): Finds the largest square-ish rectangle in the image
2. **Edge Detection** (fallback): Uses Canny edges and Hough transforms to find grid lines

This dual approach handles both screenshots (black cells) and PDFs (grey cells).

### Trainer Integration

The trainer UI is a vanilla JavaScript port of the React `TemplateTrainer` component from cryptic-trainer. This allows Grid Reader to provide the same guided solving experience without requiring the React app.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Grid Reader (port 8080)                      │
├─────────────────────────────────────────────────────────────────┤
│  crossword.js          │  trainer.js (TemplateTrainer)          │
│  - Grid UI             │  - 4-section layout                    │
│  - Cell selection      │  - Word tap selection                  │
│  - Keyboard nav        │  - Multiple choice                     │
│  - openTrainer()       │  - Text input                          │
│    └──────────────────►│  - Feedback display                    │
│                        │  - Solved view                         │
├────────────────────────┴────────────────────────────────────────┤
│                    crossword_server.py (Flask)                   │
│  - Serves static files and puzzle data                          │
│  - Proxies /trainer/* requests to cryptic-trainer API           │
│  - Looks up clues by ID (e.g., times-29453-1a)                  │
│  - Auto-imports annotated puzzles if not in trainer DB          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ HTTP API calls
┌─────────────────────────────────────────────────────────────────┐
│               cryptic-trainer server (port 5001)                 │
│  cryptic_trainer_bundle/server.py                               │
├─────────────────────────────────────────────────────────────────┤
│  /clues              - List/search annotated clues              │
│  /clues/import       - Import puzzle from annotated JSON        │
│  /training/start     - Start training session for a clue       │
│  /training/input     - Submit user answer (returns feedback)    │
│  /training/continue  - Advance to next step                     │
│  /training/learnings - Get all learnings for early solve        │
└─────────────────────────────────────────────────────────────────┘
```

#### Trainer UI Layout (4 Sections)

The TemplateTrainer displays a fixed 4-section layout:

1. **Section 1 - Clue Words**: Displays clue text as tappable words. In `tap_words` mode, clicking words selects/deselects them (highlighted in gray). Confirmed selections from server show colored highlights (GREEN=definition, ORANGE=indicator, BLUE=fodder, PURPLE=other).

2. **Section 2 - Input Area**: Shows either:
   - **Answer boxes**: Empty boxes for the final answer (filled on completion)
   - **Text input**: For intermediate steps like typing extracted letters

3. **Section 3 - Action + Button**: Shows the current instruction/prompt and action button:
   - **Check**: Submit current selection/input for validation
   - **Continue**: Advance after viewing teaching content

4. **Section 4 - Details** (scrollable): Contains:
   - **Feedback**: Red/green message for wrong/correct answers
   - **Multiple choice**: Radio-button options for clue type selection
   - **Intro panel**: Blue box with hints for new users
   - **Teaching panel**: Yellow box explaining the current step
   - **Learnings**: Accumulated insights shown as collapsed badges

#### Data Flow

When you click "Solve":

1. `crossword.js` extracts clue text, enumeration, puzzle number, clue number, direction
2. Sends POST to `/trainer/start` with this data
3. `crossword_server.py` looks up clue by constructed ID (e.g., `times-29453-1a`)
4. If not found, checks for annotated file and auto-imports
5. Proxies to cryptic-trainer `/training/start` endpoint
6. Returns `render` object describing what to display
7. `trainer.js` creates TemplateTrainer instance with render state
8. User interacts (tap words, select options, type text)
9. Submissions go to `/trainer/input`, returns new render state
10. On completion, "Apply to Grid" transfers answer back to puzzle

## Supported Formats

- **Times Cryptic** (15x15 grid)
- **Times Quick Cryptic** (13x13 grid)

## Common Issues

### Grid not detected

- Ensure the PDF contains a clear grid image
- The grid should be roughly square (aspect ratio 0.8-1.2)

### Missing clues

- The PDF clue section must have "ACROSS" and "DOWN" headers
- Clues should be in two columns

### Ligature characters

Some PDFs encode ligatures (fi, fl) as special characters. The processor attempts to fix common issues automatically.

### "Clue not found in trainer database"

The Solve feature only works for clues that have been annotated. If you have annotated puzzle files:

1. Ensure they're in `../Times_Puzzle_Import/solved/` (relative to Grid Reader)
2. Files should be named `Times_XXXXX_v2.json`
3. The auto-import will load them when you click Solve

If no annotated file exists, you can still solve normally without the trainer.

### Cannot connect to trainer service

Make sure the cryptic-trainer server is running:
```bash
cd ../cryptic-trainer/cryptic_trainer_bundle
python3 server.py
```

## Running Both Servers

For full functionality, you need both servers running:

```bash
# Terminal 1: cryptic-trainer API server (port 5001)
cd /path/to/cryptic-trainer/cryptic_trainer_bundle
python3 server.py

# Terminal 2: Grid Reader web server (port 8080)
cd /path/to/Grid\ Reader
python3 crossword_server.py
```

Then open http://localhost:8080 in your browser.

## Project Structure

```
Grid Reader/
├── crossword_server.py      # Flask web server
├── crossword_processor.py   # Grid structure extraction
├── pdf_processor.py         # PDF parsing and image extraction
├── puzzle_store.py          # Puzzle storage management
├── puzzles/                 # Stored puzzles (created automatically)
├── templates/
│   └── index.html           # Web UI
└── static/
    ├── crossword.css        # Styles
    ├── crossword.js         # Interactive grid logic
    └── trainer.js           # TemplateTrainer (ported from React)
```

## TODO

### Replace trainer integration with simple LLM solve

**Current state (deprecated/experimental):** The trainer integration is overly complex and fragile:
- Requires pre-annotated clues in a separate database
- Maintains session state on the cryptic-trainer server
- Multiple API calls back and forth for each interaction
- State easily gets out of sync between browser and server
- Ported React UI adds complexity without clear benefit

**Target architecture:** Merge LLM solving into Grid Reader as a single `/solve` endpoint:

```
POST /solve
{
  "clue": "See boss bungle work (6)",
  "enumeration": "6",
  "cross_letters": [{"position": 2, "letter": "S"}]  // optional hints
}

Response:
{
  "answer": "BISHOP",
  "confidence": 0.95,
  "explanation": "Definition: 'See boss' (a BISHOP runs a diocese/see). Wordplay: bungle=BISH (slang) + work=OP (opus). BISH+OP=BISHOP"
}
```

**Benefits:**
- Single server - no cryptic-trainer dependency
- No session state to manage
- No pre-annotation required
- Single request/response
- Works on any clue
- Grid Reader becomes fully self-contained

**Implementation:**
- Copy LLM solving logic from cryptic-trainer into Grid Reader
- Delete trainer.js and all proxy code
- Add simple `/solve` endpoint that calls LLM and returns answer
- UI: modal shows "Solving..." then displays answer + explanation with "Apply" button

## License

MIT
