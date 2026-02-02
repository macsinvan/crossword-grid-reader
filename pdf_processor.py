#!/usr/bin/env python3
"""
PDF Crossword Processor
=======================

Extracts crossword grid and clues from a Times Cryptic PDF.

Requirements:
    pip install pdfplumber Pillow

Usage:
    from pdf_processor import process_times_pdf
    grid_image_path, clues_yaml = process_times_pdf('crossword.pdf')
"""

import re
import pdfplumber
from PIL import Image
import tempfile
import os


def extract_grid_image(pdf_path, output_path=None):
    """
    Extract the crossword grid image from the PDF.

    Args:
        pdf_path: Path to the PDF file
        output_path: Optional output path for the image

    Returns:
        Path to the extracted grid image
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        # Find grid boundaries by looking for "ACROSS" text which marks end of grid
        words = page.extract_words()
        grid_end_y = None
        for word in words:
            if word['text'] == 'ACROSS':
                grid_end_y = word['top']
                break

        # Get page as image at high resolution for better grid detection
        img = page.to_image(resolution=200)
        pil_img = img.original
        width, height = pil_img.size

        # Calculate crop coordinates
        # Scale factor from PDF points to image pixels
        scale = 200 / 72  # 200 DPI / 72 points per inch

        if grid_end_y:
            # Crop to just above ACROSS text
            crop_bottom = int(grid_end_y * scale) - 20
        else:
            # Fallback: use 55% of page height
            crop_bottom = int(height * 0.55)

        # Find the grid title "Times Cryptic No XXXXX" to set top boundary
        crop_top = int(height * 0.04)  # Small margin from top

        # Crop to grid area only
        grid_region = pil_img.crop((0, crop_top, width, crop_bottom))

        grid_region.save(output_path)

    return output_path


def extract_clues_from_pdf(pdf_path):
    """
    Extract clues text from the PDF and parse into structured format.

    The Times PDF has clues in two columns (ACROSS on left, DOWN on right),
    so we need to extract by position rather than just reading text linearly.

    Returns:
        Dict with 'across' and 'down' clue lists
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        # Get page dimensions
        width = page.width
        height = page.height

        # Find where clues section starts (after grid)
        # Look for "ACROSS" text to find the clue section
        text = page.extract_text()

        # Find the y-position of ACROSS/DOWN headers
        words = page.extract_words()
        clue_start_y = None
        for word in words:
            if word['text'] == 'ACROSS':
                clue_start_y = word['top']
                break

        if clue_start_y is None:
            # Fallback: assume clues start at 60% of page
            clue_start_y = height * 0.6

        # Extract left column (ACROSS) and right column (DOWN)
        mid_x = width / 2

        # Left column - ACROSS
        left_crop = page.crop((0, clue_start_y, mid_x, height))
        across_text = left_crop.extract_text() or ''

        # Right column - DOWN
        right_crop = page.crop((mid_x, clue_start_y, width, height))
        down_text = right_crop.extract_text() or ''

    across_clues = parse_clue_column(across_text, 'ACROSS')
    down_clues = parse_clue_column(down_text, 'DOWN')

    return {
        'across': sorted(across_clues, key=lambda x: x['number']),
        'down': sorted(down_clues, key=lambda x: x['number'])
    }


def parse_clue_column(text, header):
    """
    Parse a column of clues from extracted text.

    Args:
        text: Raw text from the column
        header: 'ACROSS' or 'DOWN' to skip

    Returns:
        List of clue dicts
    """
    clues = []
    lines = text.split('\n')

    current_clue = None

    for line in lines:
        line = line.strip()

        # Skip header
        if line in ['ACROSS', 'DOWN', 'ACROSS DOWN']:
            continue

        # Skip empty lines
        if not line:
            continue

        # Try to match a clue start (number at beginning)
        clue_match = re.match(r'^(\d+)\s+(.+)$', line)

        if clue_match:
            # Save previous clue if exists
            if current_clue:
                clues.append(current_clue)

            number = int(clue_match.group(1))
            clue_text = clue_match.group(2)

            current_clue = {
                'number': number,
                'clue': clue_text,
                'answer': ''
            }
        elif current_clue and line:
            # Continuation of previous clue
            current_clue['clue'] += ' ' + line

    # Don't forget the last clue
    if current_clue:
        clues.append(current_clue)

    # Clean up - extract enumeration
    for clue in clues:
        # Extract enumeration from clue text, e.g., "(5)" or "(5,3)" or "(5-4)"
        enum_match = re.search(r'\([\d,\-]+\)\s*$', clue['clue'])
        if enum_match:
            clue['enumeration'] = enum_match.group(0)

        # Fix common PDF text extraction issues (ligatures become null chars)
        clue['clue'] = (clue['clue']
            .replace('\x00', 'fi')  # fi ligature
            .replace('  ', ' ')
            .strip())

    return clues


def process_times_pdf(pdf_path, output_dir=None):
    """
    Process a Times Cryptic PDF to extract grid image and clues.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Optional output directory

    Returns:
        Tuple of (grid_image_path, clues_dict)
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()

    # Extract puzzle number from filename or text
    puzzle_number = None
    filename = os.path.basename(pdf_path)
    num_match = re.search(r'(\d{5})', filename)
    if num_match:
        puzzle_number = int(num_match.group(1))

    # Extract grid image
    grid_path = os.path.join(output_dir, 'grid.png')
    extract_grid_image(pdf_path, grid_path)

    # Extract clues
    clues = extract_clues_from_pdf(pdf_path)

    # Build YAML-compatible structure
    clues_data = {
        'publication': 'The Times',
        'series': 'Times Cryptic',
        'number': puzzle_number or 'unknown',
        'grid_size': {
            'rows': 15,
            'cols': 15
        },
        'across': clues['across'],
        'down': clues['down']
    }

    return grid_path, clues_data


def main():
    import sys
    import yaml

    if len(sys.argv) < 2:
        print("Usage: python pdf_processor.py <pdf_path> [output_dir]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '.'

    print(f"Processing: {pdf_path}")

    grid_path, clues_data = process_times_pdf(pdf_path, output_dir)

    # Save clues as YAML
    clues_path = os.path.join(output_dir, 'clues.yaml')
    with open(clues_path, 'w') as f:
        yaml.dump(clues_data, f, default_flow_style=False, allow_unicode=True)

    print(f"\nExtracted:")
    print(f"  Grid image: {grid_path}")
    print(f"  Clues YAML: {clues_path}")
    print(f"\n  {len(clues_data['across'])} across clues")
    print(f"  {len(clues_data['down'])} down clues")


if __name__ == '__main__':
    main()
