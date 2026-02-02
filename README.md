# Crossword Grid Reader

A web-based tool for importing and solving Times Cryptic crossword puzzles from PDF files.

## Features

- **PDF Import**: Upload Times Cryptic PDF files to extract grid and clues automatically
- **Interactive Grid**: Solve puzzles in the browser with keyboard navigation
- **Answer Validation**: Optionally provide an answers file to validate your solutions
- **Robust Grid Detection**: Uses edge detection and contour analysis to handle various PDF formats

## Requirements

```bash
pip install opencv-python numpy pyyaml flask pdfplumber Pillow
```

## Quick Start

1. Start the web server:
   ```bash
   python crossword_server.py
   ```

2. Open http://localhost:8080 in your browser

3. Upload a Times Cryptic PDF file

4. Solve the puzzle!

## Web Interface

### Uploading a Puzzle

- **PDF File (required)**: A Times Cryptic PDF containing the grid and clues
- **Answers File (optional)**: A JSON or YAML file with answers for validation

### Solving

- Click a cell or clue to select it
- Type letters to fill in answers
- Press **Space** to toggle between Across and Down
- Press **Tab** to move to the next clue
- Arrow keys navigate the grid

### Controls

- **Check Answers**: Highlights incorrect cells (requires answers file)
- **Clear Grid**: Removes all entered letters
- **Reveal All**: Shows the solution (requires answers file)

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

1. **Extract Grid Image**: Crops the PDF to isolate the crossword grid
2. **Extract Clues**: Parses the two-column clue layout (Across/Down)
3. **Detect Grid Structure**: Finds the grid boundary and cell positions
4. **Identify Black Squares**: Samples cell centers to classify black/white cells
5. **Number Clues**: Assigns sequential numbers based on standard crossword rules

### Grid Detection

The processor uses two methods for finding the grid:

1. **Contour Detection** (primary): Finds the largest square-ish rectangle in the image
2. **Edge Detection** (fallback): Uses Canny edges and Hough transforms to find grid lines

This dual approach handles both screenshots (black cells) and PDFs (grey cells).

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

## Project Structure

```
Grid Reader/
├── crossword_server.py      # Flask web server
├── crossword_processor.py   # Grid structure extraction
├── pdf_processor.py         # PDF parsing and image extraction
├── templates/
│   └── index.html           # Web UI
└── static/
    ├── crossword.css        # Styles
    └── crossword.js         # Interactive grid logic
```

## License

MIT
