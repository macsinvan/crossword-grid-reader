# Crossword Grid Processor

Extracts grid structure from a crossword puzzle image and generates a complete YAML file with validation against provided clue answers.

## Requirements

```bash
pip install opencv-python numpy pyyaml
```

## Usage

```bash
python crossword_processor.py <grid_image> <clues_yaml> [output_yaml]
```

### Example

```bash
python crossword_processor.py puzzle.png clues.yaml output.yaml
```

## Input Files

### 1. Grid Image (PNG/JPG)

A screenshot or scan of the crossword grid. The processor will:
- Detect black squares automatically
- Calculate cell size from black square dimensions
- Extract grid structure (which cells are black vs white)

**Important:** The image must include the complete grid. If the first row is cropped, clue numbering will fail.

### 2. Clues YAML

A YAML file containing the puzzle metadata and clue answers:

```yaml
publication: "The Times"
series: "Times Quick Cryptic"
number: 3177
grid_size:
  rows: 13
  cols: 13

across:
  - number: 7
    clue: "Take out fruit (4)"
    answer: "DATE"
  - number: 8
    clue: "Passing remarks? (8)"
    answer: "OBITUARY"
  # ... more clues

down:
  - number: 1
    clue: "When travelling, grandma tours one American high street (4,4)"
    answer: "MAIN DRAG"
  - number: 2
    clue: "Fairly new part of leisure centre (6)"
    answer: "RECENT"
  # ... more clues
```

**Notes:**
- `grid_size` must match the actual grid dimensions
- Answers can include spaces or hyphens (they are stripped automatically)
- All clues must be provided - partial grids are not supported

## Output

The processor generates a complete YAML file with:

```yaml
puzzle:
  publication: "The Times"
  series: "Times Quick Cryptic"
  number: 3177
  grid:
    rows: 13
    cols: 13
    blank_grid: |
      #|1|#|2|#|3|#|4|#|5|#|6|#
      7|-|-|-|#|8|-|-|-|-|-|-|-
      ...
    filled_grid: |
      #|M|#|R|#|F|#|T|#|G|#|B|#
      D|A|T|E|#|O|B|I|T|U|A|R|Y
      ...
    layout:
      - '#.#.#.#.#.#.#'
      - '....#........'
      ...
    filled_cells:
      - row: 1
        col: 2
        letter: M
      ...
  numbering:
    across:
      - number: 7
        row: 2
        col: 1
        length: 4
      ...
    down:
      - number: 1
        row: 1
        col: 2
        length: 8
      ...
  across:
    # Original clue data
  down:
    # Original clue data
```

## What the Processor Does

1. **Loads grid image** and converts to grayscale
2. **Finds cell size** by detecting black squares (square-ish contours with area 2000-10000 px²)
3. **Extracts grid structure** - marks each cell as black (#) or white (.)
4. **Finds clue positions** - scans in reading order, assigns sequential numbers
5. **Validates answers** - fills grid with YAML answers, checks for conflicts
6. **Generates output** - complete YAML with all grid data

## What the Processor Does NOT Do

- **OCR letters from the grid** - Letters come from YAML answers only
- **Work with partial answer sets** - All answers must be provided
- **Guess missing data** - Stops with error if validation fails

## Validation

The processor stops immediately if:

- Grid dimensions don't match YAML `grid_size`
- Clue numbering doesn't start at 1
- Clue numbering has gaps
- Answers don't fit grid structure
- Answers conflict at crossing points
- Cells remain unfilled

## Common Issues

### "First clue number is X, not 1"
The first row of the grid wasn't detected. Check:
- Image includes complete grid (not cropped)
- Grid size in YAML matches actual grid

### "Goes past grid edge"
Answer is longer than available cells. Check:
- `grid_size` is correct (e.g., 13x13 not 12x12)
- Answer spelling is correct

### "Conflict at (row, col)"
Two answers have different letters at the same crossing point. Check:
- Both answers are spelled correctly
- Answers match the actual puzzle solution

## Grid Sizes

Common crossword grid sizes:
- **15×15** - Standard Times crossword
- **13×13** - Times Quick Cryptic
- **11×11** - Some quick puzzles

Always verify the grid size from the image before processing.
