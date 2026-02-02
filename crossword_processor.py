#!/usr/bin/env python3
"""
Crossword Grid Processor
========================

Extracts grid structure from a crossword image and generates complete YAML
with validation against provided clue answers.

Requirements:
    pip install opencv-python numpy pyyaml

Usage:
    python crossword_processor.py <grid_image> <clues_yaml> [output_yaml]

Example:
    python crossword_processor.py puzzle.png clues.yaml output.yaml

Input YAML format:
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
      ...
    down:
      - number: 1
        clue: "When travelling, grandma tours one American high street (4,4)"
        answer: "MAIN DRAG"
      ...

What this script does:
    1. Loads grid image and detects cell size from black squares
    2. Extracts grid structure (black/white cells only - NO OCR of letters)
    3. Finds clue start positions automatically (numbered sequentially from 1)
    4. Validates that answers from YAML fit the detected grid structure
    5. Generates complete YAML with layout, filled grid, and numbering

What this script does NOT do:
    - OCR letters from the grid (letters come from YAML answers)
    - Work with incomplete/partial answer sets
"""

import cv2
import numpy as np
import yaml
import sys
from pathlib import Path


class CrosswordGridProcessor:
    def __init__(self, image_path, clues_yaml_path, grid_size=None):
        """
        Initialize processor with image and clues YAML
        
        Args:
            image_path: Path to crossword grid image
            clues_yaml_path: Path to YAML file with clue data
            grid_size: Tuple (rows, cols) or None to read from YAML
        """
        self.image_path = image_path
        self.clues_yaml_path = clues_yaml_path
        self.grid_size = grid_size
        self.image = None
        self.gray = None
        self.cell_size = None
        self.grid_origin = None
        self.layout = None
        self.clue_data = None
        self.rows = None
        self.cols = None
        
    def load_image(self):
        """Load and prepare image"""
        print(f"Loading image: {self.image_path}")
        self.image = cv2.imread(self.image_path)
        if self.image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        self.gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        print(f"  Image size: {self.image.shape[1]}x{self.image.shape[0]}")
        
    def load_clues(self):
        """Load clue data from YAML"""
        print(f"\nLoading clues: {self.clues_yaml_path}")
        with open(self.clues_yaml_path, 'r') as f:
            self.clue_data = yaml.safe_load(f)
        
        # Determine grid size
        if self.grid_size:
            self.rows, self.cols = self.grid_size
        elif 'grid_size' in self.clue_data:
            self.rows = self.clue_data['grid_size']['rows']
            self.cols = self.clue_data['grid_size']['cols']
        elif 'grid' in self.clue_data and 'rows' in self.clue_data['grid']:
            self.rows = self.clue_data['grid']['rows']
            self.cols = self.clue_data['grid']['cols']
        else:
            # Default to 15x15
            self.rows = 15
            self.cols = 15
        
        print(f"  Grid size: {self.rows}×{self.cols}")
        
        across_count = len(self.clue_data.get('across', []))
        down_count = len(self.clue_data.get('down', []))
        print(f"  Loaded {across_count} across clues, {down_count} down clues")
        
    def find_cell_size(self):
        """
        Find cell size and grid origin using edge detection and Hough transform.

        This approach detects grid lines directly rather than relying on black squares,
        making it robust against grids with adjacent black cells that might merge
        in binary thresholding.
        """
        print("\nFinding cell size using edge detection...")

        # Step 1: Edge detection to find grid lines
        edges = cv2.Canny(self.gray, 50, 150)

        # Step 2: Hough transform to detect lines
        # Use probabilistic Hough for better line segment detection
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=200, maxLineGap=10)

        if lines is None or len(lines) == 0:
            raise ValueError("Could not detect grid lines in image")

        # Step 3: Separate horizontal and vertical lines
        h_lines = []  # y-coordinates of horizontal lines
        v_lines = []  # x-coordinates of vertical lines

        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Horizontal line: y values are similar
            if abs(y2 - y1) < 10:
                h_lines.append((y1 + y2) // 2)
            # Vertical line: x values are similar
            elif abs(x2 - x1) < 10:
                v_lines.append((x1 + x2) // 2)

        if not h_lines or not v_lines:
            raise ValueError(f"Insufficient grid lines detected (h:{len(h_lines)}, v:{len(v_lines)})")

        print(f"  Detected {len(h_lines)} horizontal, {len(v_lines)} vertical line segments")

        # Step 4: Find grid boundaries from line positions
        grid_x = min(v_lines)
        grid_y = min(h_lines)
        grid_x_max = max(v_lines)
        grid_y_max = max(h_lines)

        grid_w = grid_x_max - grid_x
        grid_h = grid_y_max - grid_y

        # Step 5: Calculate cell size from grid dimensions and known grid size
        cell_w = grid_w / self.cols
        cell_h = grid_h / self.rows

        # Store as float for more accurate cell center calculations
        self.cell_size_w = cell_w
        self.cell_size_h = cell_h
        self.cell_size = (cell_w + cell_h) / 2  # Keep average for backwards compatibility
        self.grid_origin = (grid_x, grid_y)
        self.grid_width = grid_w
        self.grid_height = grid_h

        print(f"  Grid boundary: ({grid_x}, {grid_y}) to ({grid_x_max}, {grid_y_max})")
        print(f"  Grid dimensions: {grid_w}x{grid_h} pixels")
        print(f"  Cell size: {cell_w:.1f}x{cell_h:.1f} pixels (avg: {self.cell_size:.1f})")
        print(f"  Grid origin: {self.grid_origin}")
        
    def extract_grid_structure(self):
        """
        Extract grid structure (black/white cells) by sampling cell centers.

        Uses the grid origin and cell size calculated by find_cell_size() to
        determine the center of each cell, then samples a small region around
        that center to determine if it's a black or white cell.
        """
        print("\nExtracting grid structure...")

        grid_x, grid_y = self.grid_origin

        # Use the precise cell dimensions if available
        cell_w = getattr(self, 'cell_size_w', self.cell_size)
        cell_h = getattr(self, 'cell_size_h', self.cell_size)

        layout = []

        for row in range(self.rows):
            row_str = ""
            for col in range(self.cols):
                # Calculate cell center (using 0.5 offset for true center)
                cx = int(grid_x + (col + 0.5) * cell_w)
                cy = int(grid_y + (row + 0.5) * cell_h)

                # Sample a small region around the center (5px radius)
                sample_radius = 5
                y_start = max(0, cy - sample_radius)
                y_end = min(self.gray.shape[0], cy + sample_radius)
                x_start = max(0, cx - sample_radius)
                x_end = min(self.gray.shape[1], cx + sample_radius)

                region = self.gray[y_start:y_end, x_start:x_end]

                if region.size == 0:
                    row_str += '.'
                    continue

                avg_brightness = np.mean(region)

                # Black square threshold (dark = black cell)
                if avg_brightness < 128:
                    row_str += '#'
                else:
                    row_str += '.'

            layout.append(row_str)

        self.layout = layout

        # Verify grid dimensions
        if len(layout) != self.rows:
            raise ValueError(f"❌ CRITICAL: Extracted {len(layout)} rows but expected {self.rows} rows!")
        for i, row in enumerate(layout, 1):
            if len(row) != self.cols:
                raise ValueError(f"❌ CRITICAL: Row {i} has {len(row)} columns but expected {self.cols} columns!")

        # Report results
        num_black = sum(row.count('#') for row in layout)
        print(f"  Detected {num_black} black squares")
        print(f"  ✓ Grid dimensions confirmed: {self.rows}×{self.cols}")

        # Print the detected layout for verification
        print("\n  Detected layout:")
        for row in layout:
            print(f"    {row}")

        return layout
    
    def find_clue_positions(self):
        """Find all clue start positions and assign numbers"""
        print("\nFinding clue positions...")
        
        clue_number = 1
        across_starts = {}
        down_starts = {}
        
        # Scan in reading order
        for row in range(self.rows):
            for col in range(self.cols):
                if self.layout[row][col] != '.':
                    continue
                
                starts_across = False
                starts_down = False
                
                # Check ACROSS start
                if col == 0:
                    left_is_block = True
                else:
                    left_is_block = (self.layout[row][col-1] == '#')
                
                if col == self.cols - 1:
                    right_is_white = False
                else:
                    right_is_white = (self.layout[row][col+1] == '.')
                
                if left_is_block and right_is_white:
                    starts_across = True
                
                # Check DOWN start
                if row == 0:
                    above_is_block = True
                else:
                    above_is_block = (self.layout[row-1][col] == '#')
                
                if row == self.rows - 1:
                    below_is_white = False
                else:
                    below_is_white = (self.layout[row+1][col] == '.')
                
                if above_is_block and below_is_white:
                    starts_down = True
                
                # Assign number if starts any clue
                if starts_across or starts_down:
                    if starts_across:
                        across_starts[clue_number] = (row + 1, col + 1)
                    if starts_down:
                        down_starts[clue_number] = (row + 1, col + 1)
                    clue_number += 1
        
        print(f"  Found {len(across_starts)} across positions")
        print(f"  Found {len(down_starts)} down positions")
        print(f"  Total clue numbers: {clue_number - 1}")
        
        # CRITICAL VALIDATION: Clue numbers must start at 1
        all_clue_numbers = sorted(set(across_starts.keys()) | set(down_starts.keys()))
        
        if not all_clue_numbers:
            raise ValueError("❌ CRITICAL: No clue positions found!")
        
        if all_clue_numbers[0] != 1:
            raise ValueError(
                f"❌ CRITICAL: First clue number is {all_clue_numbers[0]}, not 1!\n"
                f"   This means the first row was not detected.\n"
                f"   Clue numbers must start at 1 and be sequential.\n"
                f"   Found clue numbers: {all_clue_numbers[:10]}{'...' if len(all_clue_numbers) > 10 else ''}"
            )
        
        # Check for sequential numbering
        for i, num in enumerate(all_clue_numbers, 1):
            if num != i:
                raise ValueError(
                    f"❌ CRITICAL: Clue numbering is not sequential!\n"
                    f"   Expected clue {i} but found {num}.\n"
                    f"   Found clues: {all_clue_numbers}"
                )
        
        print(f"  ✓ Clue numbering validated: sequential from 1 to {clue_number - 1}")
        
        return across_starts, down_starts
    
    def calculate_clue_lengths(self, across_starts, down_starts):
        """Calculate length of each clue"""
        print("\nCalculating clue lengths...")
        
        across_lengths = {}
        down_lengths = {}
        
        # ACROSS lengths
        for num, (row, col) in across_starts.items():
            r, c = row - 1, col - 1
            length = 0
            while c < self.cols and self.layout[r][c] == '.':
                length += 1
                c += 1
            across_lengths[num] = length
        
        # DOWN lengths
        for num, (row, col) in down_starts.items():
            r, c = row - 1, col - 1
            length = 0
            while r < self.rows and self.layout[r][c] == '.':
                length += 1
                r += 1
            down_lengths[num] = length
        
        return across_lengths, down_lengths
    
    def validate_with_answers(self, across_starts, down_starts):
        """
        Fill grid with answers from YAML and check for conflicts.
        Returns filled grid and list of errors.
        """
        print("\nValidating answers against grid structure...")
        
        # Create empty grid
        grid = [['-' for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Place black squares
        for r in range(self.rows):
            for c in range(self.cols):
                if self.layout[r][c] == '#':
                    grid[r][c] = '#'
        
        errors = []
        
        # Get answers from YAML
        across_answers = {c['number']: c['answer'] for c in self.clue_data.get('across', [])}
        down_answers = {c['number']: c['answer'] for c in self.clue_data.get('down', [])}
        
        # Fill ACROSS answers
        print("  Filling across answers...")
        for num, answer in across_answers.items():
            if num not in across_starts:
                errors.append(f"Across {num}: No start position found in grid")
                continue
            
            row, col = across_starts[num]
            r, c = row - 1, col - 1
            
            # Clean answer (remove spaces/hyphens)
            clean_answer = answer.replace(' ', '').replace('-', '')
            
            # Place letters
            for i, letter in enumerate(clean_answer):
                if c + i >= self.cols:
                    errors.append(f"Across {num}: Goes past grid edge")
                    break
                if grid[r][c + i] == '#':
                    errors.append(f"Across {num}: Hits black square at position {i}")
                    break
                if grid[r][c + i] != '-' and grid[r][c + i] != letter:
                    errors.append(f"Across {num}: Conflict at ({r+1},{c+i+1}): has {grid[r][c+i]}, wants {letter}")
                
                grid[r][c + i] = letter
        
        # Fill DOWN answers
        print("  Filling down answers...")
        for num, answer in down_answers.items():
            if num not in down_starts:
                errors.append(f"Down {num}: No start position found in grid")
                continue
            
            row, col = down_starts[num]
            r, c = row - 1, col - 1
            
            clean_answer = answer.replace(' ', '').replace('-', '')
            
            for i, letter in enumerate(clean_answer):
                if r + i >= self.rows:
                    errors.append(f"Down {num}: Goes past grid bottom")
                    break
                if grid[r + i][c] == '#':
                    errors.append(f"Down {num}: Hits black square at position {i}")
                    break
                if grid[r + i][c] != '-' and grid[r + i][c] != letter:
                    errors.append(f"Down {num}: Conflict at ({r+i+1},{c+1}): has {grid[r+i][c]}, wants {letter}")
                
                grid[r + i][c] = letter
        
        return grid, errors
    
    def generate_yaml_output(self, grid, across_starts, down_starts, 
                           across_lengths, down_lengths):
        """Generate complete YAML with all grid data"""
        print("\nGenerating YAML output...")
        
        # Create blank grid (human readable)
        blank_grid_lines = []
        clue_num_grid = [['-' for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Place clue numbers
        all_starts = {}
        all_starts.update(across_starts)
        all_starts.update(down_starts)
        
        for num, (row, col) in all_starts.items():
            clue_num_grid[row-1][col-1] = str(num)
        
        # Format blank grid
        for r in range(self.rows):
            row_parts = []
            for c in range(self.cols):
                if self.layout[r][c] == '#':
                    row_parts.append('#')
                elif clue_num_grid[r][c] != '-':
                    row_parts.append(clue_num_grid[r][c])
                else:
                    row_parts.append('-')
            blank_grid_lines.append('|'.join(row_parts))
        
        # Format filled grid
        filled_grid_lines = []
        for r in range(self.rows):
            row_parts = [grid[r][c] for c in range(self.cols)]
            filled_grid_lines.append('|'.join(row_parts))
        
        # Create filled_cells list
        filled_cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if grid[r][c] not in ['-', '#']:
                    filled_cells.append({
                        'row': r + 1,
                        'col': c + 1,
                        'letter': grid[r][c]
                    })
        
        # Create numbering section
        numbering_across = []
        for num in sorted(across_starts.keys()):
            row, col = across_starts[num]
            numbering_across.append({
                'number': num,
                'row': row,
                'col': col,
                'length': across_lengths[num]
            })
        
        numbering_down = []
        for num in sorted(down_starts.keys()):
            row, col = down_starts[num]
            numbering_down.append({
                'number': num,
                'row': row,
                'col': col,
                'length': down_lengths[num]
            })
        
        # Build complete YAML structure
        output = {
            'puzzle': {
                'publication': self.clue_data.get('publication', 'Unknown'),
                'series': self.clue_data.get('series', ''),
                'number': self.clue_data.get('number', 'unknown'),
                'grid': {
                    'rows': self.rows,
                    'cols': self.cols,
                    'blank_grid': '\n'.join(blank_grid_lines),
                    'filled_grid': '\n'.join(filled_grid_lines),
                    'layout': self.layout,
                    'filled_cells': filled_cells
                },
                'numbering': {
                    'across': numbering_across,
                    'down': numbering_down
                },
                'across': self.clue_data.get('across', []),
                'down': self.clue_data.get('down', [])
            }
        }
        
        return output
    
    def process(self, output_path):
        """Run complete processing pipeline"""
        print("="*70)
        print("CROSSWORD GRID PROCESSOR")
        print("="*70)
        
        # Load inputs
        self.load_image()
        self.load_clues()
        
        # Extract grid structure
        self.find_cell_size()
        self.extract_grid_structure()
        
        # Find clue positions
        across_starts, down_starts = self.find_clue_positions()
        across_lengths, down_lengths = self.calculate_clue_lengths(
            across_starts, down_starts)
        
        # Validate with answers
        grid, errors = self.validate_with_answers(across_starts, down_starts)
        
        # Report validation results
        print("\n" + "="*70)
        print("VALIDATION RESULTS")
        print("="*70)
        
        if errors:
            print(f"\n❌ Found {len(errors)} error(s):")
            for error in errors:
                print(f"  - {error}")
            raise ValueError(
                f"\n❌ STOPPING: {len(errors)} validation error(s) found.\n"
                f"   Fix the errors above before continuing."
            )
        else:
            print("\n✓ All answers fit perfectly!")
            
            # Check for unfilled cells
            unfilled = sum(1 for row in grid for cell in row if cell == '-')
            if unfilled > 0:
                raise ValueError(
                    f"\n❌ STOPPING: {unfilled} unfilled cells found.\n"
                    f"   All cells must be filled by answers."
                )
            else:
                print("✓ All cells filled")
        
        # Generate YAML
        yaml_output = self.generate_yaml_output(
            grid, across_starts, down_starts, 
            across_lengths, down_lengths)
        
        # Write output
        print(f"\nWriting output to: {output_path}")
        with open(output_path, 'w') as f:
            yaml.dump(yaml_output, f, default_flow_style=False, 
                     allow_unicode=True, sort_keys=False)
        
        print("\n" + "="*70)
        print("PROCESSING COMPLETE")
        print("="*70)
        
        return errors


def main():
    if len(sys.argv) < 3:
        print("Usage: python crossword_processor.py <image_path> <clues_yaml_path> [output_path]")
        print("\nExample:")
        print("  python crossword_processor.py grid.png clues.yaml output.yaml")
        sys.exit(1)
    
    image_path = sys.argv[1]
    clues_yaml_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else 'crossword_complete.yaml'
    
    processor = CrosswordGridProcessor(image_path, clues_yaml_path)
    errors = processor.process(output_path)
    
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
