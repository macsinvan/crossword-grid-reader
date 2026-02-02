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

When you click "Solve":

1. The current clue text, enumeration, and puzzle metadata are extracted
2. Cross letters from intersecting words are collected
3. A request is sent to the trainer API to find the matching clue by ID (e.g., `times-29453-11a`)
4. If not found in the trainer database, check for annotated file in `Times_Puzzle_Import/solved/`
5. If annotated file exists, **auto-import** the puzzle to the trainer database
6. Start the training session with step-by-step guidance
7. On completion, the answer is applied back to the grid

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
    └── crossword.js         # Interactive grid + trainer logic
```

## License

MIT
