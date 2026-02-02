/**
 * Crossword Puzzle Interactive Grid
 *
 * Handles all interactive functionality for the crossword puzzle:
 * - Grid rendering and cell selection
 * - Keyboard navigation and input
 * - Clue highlighting and selection
 * - Answer validation
 */

class CrosswordPuzzle {
    constructor() {
        this.puzzle = null;
        this.userGrid = [];
        this.selectedCell = null;
        this.direction = 'across'; // 'across' or 'down'
        this.currentClueNumber = null;

        this.initEventListeners();
    }

    initEventListeners() {
        // File input display
        document.getElementById('pdf-file').addEventListener('change', (e) => {
            const fileName = e.target.files[0]?.name || 'No file selected';
            document.getElementById('pdf-file-name').textContent = fileName;
        });

        document.getElementById('answers-file').addEventListener('change', (e) => {
            const fileName = e.target.files[0]?.name || 'No file selected';
            document.getElementById('answers-file-name').textContent = fileName;
        });

        // PDF upload form
        document.getElementById('pdf-upload-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadPDF();
        });

        // Grid controls
        document.getElementById('check-btn').addEventListener('click', () => {
            this.checkAnswers();
        });

        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearGrid();
        });

        document.getElementById('reveal-btn').addEventListener('click', () => {
            this.revealAll();
        });

        // Keyboard input
        document.addEventListener('keydown', (e) => {
            if (this.puzzle && this.selectedCell) {
                this.handleKeydown(e);
            }
        });
    }

    async uploadPDF() {
        const pdfFile = document.getElementById('pdf-file').files[0];
        const answersFile = document.getElementById('answers-file').files[0];

        if (!pdfFile) {
            this.showError('Please select a PDF file.');
            return;
        }

        const formData = new FormData();
        formData.append('pdf_file', pdfFile);

        // Optional answers file for validation
        if (answersFile) {
            formData.append('answers_file', answersFile);
        }

        await this.processUpload(formData);
    }

    async processUpload(formData) {
        document.body.classList.add('loading');
        this.hideError();

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            this.puzzle = data.puzzle;
            this.initUserGrid();
            this.renderPuzzle();

            // Show warnings if any
            if (data.warnings && data.warnings.length > 0) {
                this.showWarnings(data.warnings);
            }

            // Show puzzle section, hide upload section
            document.getElementById('upload-section').classList.add('hidden');
            document.getElementById('puzzle-section').classList.remove('hidden');

        } catch (error) {
            this.showError(error.message);
        } finally {
            document.body.classList.remove('loading');
        }
    }

    showError(message) {
        const errorEl = document.getElementById('upload-error');
        errorEl.textContent = message;
        errorEl.classList.add('visible');
    }

    hideError() {
        document.getElementById('upload-error').classList.remove('visible');
    }

    showWarnings(warnings) {
        const warningEl = document.getElementById('validation-warnings');
        if (!warningEl) {
            // Create warning element if it doesn't exist
            const container = document.getElementById('puzzle-section');
            const div = document.createElement('div');
            div.id = 'validation-warnings';
            div.className = 'validation-warnings';
            container.insertBefore(div, container.firstChild);
        }
        const el = document.getElementById('validation-warnings');
        el.innerHTML = `<strong>Data Warnings (${warnings.length}):</strong><ul>${warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
        el.classList.add('visible');
    }

    initUserGrid() {
        const { rows, cols, layout } = this.puzzle.grid;
        this.userGrid = [];

        for (let r = 0; r < rows; r++) {
            const row = [];
            for (let c = 0; c < cols; c++) {
                if (layout[r][c] === '#') {
                    row.push('#');
                } else {
                    row.push('');
                }
            }
            this.userGrid.push(row);
        }
    }

    renderPuzzle() {
        this.renderGrid();
        this.renderClues();
        this.updatePuzzleInfo();
    }

    updatePuzzleInfo() {
        const { publication, series, number } = this.puzzle;
        let info = '';
        if (publication) info += publication;
        if (series) info += (info ? ' - ' : '') + series;
        if (number) info += (info ? ' #' : '#') + number;
        document.getElementById('puzzle-info').textContent = info;
    }

    renderGrid() {
        const gridEl = document.getElementById('crossword-grid');
        const { rows, cols, layout, cellNumbers } = this.puzzle.grid;

        gridEl.innerHTML = '';
        gridEl.style.gridTemplateColumns = `repeat(${cols}, 40px)`;
        gridEl.style.gridTemplateRows = `repeat(${rows}, 40px)`;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.row = r;
                cell.dataset.col = c;

                if (layout[r][c] === '#') {
                    cell.classList.add('black');
                } else {
                    // Check if cell has a number
                    const key = `${r + 1},${c + 1}`;
                    if (cellNumbers[key]) {
                        const numSpan = document.createElement('span');
                        numSpan.className = 'cell-number';
                        numSpan.textContent = cellNumbers[key];
                        cell.appendChild(numSpan);
                    }

                    // Letter display
                    const letterSpan = document.createElement('span');
                    letterSpan.className = 'cell-letter';
                    letterSpan.textContent = this.userGrid[r][c];
                    cell.appendChild(letterSpan);

                    // Click handler
                    cell.addEventListener('click', () => {
                        this.selectCell(r, c);
                    });
                }

                gridEl.appendChild(cell);
            }
        }
    }

    renderClues() {
        const acrossEl = document.getElementById('across-clues');
        const downEl = document.getElementById('down-clues');

        acrossEl.innerHTML = '';
        downEl.innerHTML = '';

        for (const clue of this.puzzle.clues.across) {
            const li = document.createElement('li');
            li.dataset.direction = 'across';
            li.dataset.number = clue.number;
            li.innerHTML = `<span class="clue-number">${clue.number}</span>${clue.clue}`;
            li.addEventListener('click', () => {
                this.selectClue('across', clue.number);
            });
            acrossEl.appendChild(li);
        }

        for (const clue of this.puzzle.clues.down) {
            const li = document.createElement('li');
            li.dataset.direction = 'down';
            li.dataset.number = clue.number;
            li.innerHTML = `<span class="clue-number">${clue.number}</span>${clue.clue}`;
            li.addEventListener('click', () => {
                this.selectClue('down', clue.number);
            });
            downEl.appendChild(li);
        }
    }

    selectCell(row, col) {
        // If clicking already selected cell, toggle direction
        if (this.selectedCell &&
            this.selectedCell.row === row &&
            this.selectedCell.col === col) {
            this.toggleDirection();
            return;
        }

        this.selectedCell = { row, col };
        this.clearValidation();
        this.updateHighlights();
        this.updateCurrentClue();
    }

    selectClue(direction, number) {
        this.direction = direction;

        // Find the start position for this clue
        const numbering = this.puzzle.numbering[direction];
        const clueInfo = numbering.find(n => n.number === number);

        if (clueInfo) {
            this.selectedCell = {
                row: clueInfo.row - 1,
                col: clueInfo.col - 1
            };
            this.currentClueNumber = number;
            this.clearValidation();
            this.updateHighlights();
            this.updateCurrentClue();
        }
    }

    toggleDirection() {
        // Only toggle if both directions are valid at this cell
        const { row, col } = this.selectedCell;

        const canGoAcross = this.canStartAcross(row, col) || this.isPartOfAcross(row, col);
        const canGoDown = this.canStartDown(row, col) || this.isPartOfDown(row, col);

        if (canGoAcross && canGoDown) {
            this.direction = this.direction === 'across' ? 'down' : 'across';
            this.updateHighlights();
            this.updateCurrentClue();
        }
    }

    canStartAcross(row, col) {
        const numbering = this.puzzle.numbering.across;
        return numbering.some(n => n.row - 1 === row && n.col - 1 === col);
    }

    canStartDown(row, col) {
        const numbering = this.puzzle.numbering.down;
        return numbering.some(n => n.row - 1 === row && n.col - 1 === col);
    }

    isPartOfAcross(row, col) {
        const { layout } = this.puzzle.grid;
        if (layout[row][col] === '#') return false;

        // Check if there's a white cell to the left or right
        const hasLeft = col > 0 && layout[row][col - 1] !== '#';
        const hasRight = col < layout[0].length - 1 && layout[row][col + 1] !== '#';

        return hasLeft || hasRight;
    }

    isPartOfDown(row, col) {
        const { layout } = this.puzzle.grid;
        if (layout[row][col] === '#') return false;

        const hasAbove = row > 0 && layout[row - 1][col] !== '#';
        const hasBelow = row < layout.length - 1 && layout[row + 1][col] !== '#';

        return hasAbove || hasBelow;
    }

    updateHighlights() {
        // Clear all highlights
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('selected', 'highlighted');
        });

        // Clear clue highlights
        document.querySelectorAll('.clue-list li').forEach(li => {
            li.classList.remove('active');
        });

        if (!this.selectedCell) return;

        const { row, col } = this.selectedCell;
        const { layout } = this.puzzle.grid;

        // Highlight current cell
        const selectedEl = document.querySelector(
            `.cell[data-row="${row}"][data-col="${col}"]`
        );
        if (selectedEl) {
            selectedEl.classList.add('selected');
        }

        // Find and highlight word cells
        const wordCells = this.getWordCells(row, col);
        for (const { r, c } of wordCells) {
            const cellEl = document.querySelector(
                `.cell[data-row="${r}"][data-col="${c}"]`
            );
            if (cellEl) {
                cellEl.classList.add('highlighted');
            }
        }

        // Highlight active clue
        const clueNumber = this.getCurrentClueNumber();
        if (clueNumber) {
            const clueEl = document.querySelector(
                `.clue-list li[data-direction="${this.direction}"][data-number="${clueNumber}"]`
            );
            if (clueEl) {
                clueEl.classList.add('active');
                clueEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    }

    getWordCells(row, col) {
        const { layout } = this.puzzle.grid;
        const cells = [];

        if (this.direction === 'across') {
            // Find start of word
            let startCol = col;
            while (startCol > 0 && layout[row][startCol - 1] !== '#') {
                startCol--;
            }
            // Collect all cells in word
            let c = startCol;
            while (c < layout[0].length && layout[row][c] !== '#') {
                cells.push({ r: row, c });
                c++;
            }
        } else {
            // Find start of word
            let startRow = row;
            while (startRow > 0 && layout[startRow - 1][col] !== '#') {
                startRow--;
            }
            // Collect all cells in word
            let r = startRow;
            while (r < layout.length && layout[r][col] !== '#') {
                cells.push({ r, c: col });
                r++;
            }
        }

        return cells;
    }

    getCurrentClueNumber() {
        if (!this.selectedCell) return null;

        const { row, col } = this.selectedCell;
        const wordCells = this.getWordCells(row, col);

        if (wordCells.length === 0) return null;

        const startCell = wordCells[0];
        const key = `${startCell.r + 1},${startCell.c + 1}`;

        // Find matching clue number
        const numbering = this.puzzle.numbering[this.direction];
        const match = numbering.find(n =>
            n.row - 1 === startCell.r && n.col - 1 === startCell.c
        );

        return match ? match.number : null;
    }

    updateCurrentClue() {
        const clueNumber = this.getCurrentClueNumber();
        const numberEl = document.getElementById('current-clue-number');
        const textEl = document.getElementById('current-clue-text');

        if (!clueNumber) {
            numberEl.textContent = '';
            textEl.textContent = '';
            return;
        }

        const clues = this.puzzle.clues[this.direction];
        const clue = clues.find(c => c.number === clueNumber);

        if (clue) {
            const dirLabel = this.direction === 'across' ? 'A' : 'D';
            numberEl.textContent = `${clueNumber}${dirLabel}`;
            textEl.textContent = clue.clue;
        }
    }

    handleKeydown(e) {
        const { row, col } = this.selectedCell;
        const { layout } = this.puzzle.grid;

        // Letter input
        if (/^[a-zA-Z]$/.test(e.key)) {
            e.preventDefault();
            this.setCell(row, col, e.key.toUpperCase());
            this.moveToNextCell();
            return;
        }

        switch (e.key) {
            case 'ArrowUp':
                e.preventDefault();
                this.moveCell(-1, 0);
                break;
            case 'ArrowDown':
                e.preventDefault();
                this.moveCell(1, 0);
                break;
            case 'ArrowLeft':
                e.preventDefault();
                this.moveCell(0, -1);
                break;
            case 'ArrowRight':
                e.preventDefault();
                this.moveCell(0, 1);
                break;
            case 'Backspace':
                e.preventDefault();
                if (this.userGrid[row][col]) {
                    // Clear current cell
                    this.setCell(row, col, '');
                } else {
                    // Move back and clear
                    this.moveToPrevCell();
                    if (this.selectedCell) {
                        this.setCell(this.selectedCell.row, this.selectedCell.col, '');
                    }
                }
                break;
            case 'Delete':
                e.preventDefault();
                this.setCell(row, col, '');
                break;
            case ' ':
                e.preventDefault();
                this.toggleDirection();
                break;
            case 'Tab':
                e.preventDefault();
                if (e.shiftKey) {
                    this.moveToPrevClue();
                } else {
                    this.moveToNextClue();
                }
                break;
        }
    }

    setCell(row, col, letter) {
        this.userGrid[row][col] = letter;

        const cellEl = document.querySelector(
            `.cell[data-row="${row}"][data-col="${col}"] .cell-letter`
        );
        if (cellEl) {
            cellEl.textContent = letter;
        }

        // Clear any validation styling
        const cell = document.querySelector(
            `.cell[data-row="${row}"][data-col="${col}"]`
        );
        if (cell) {
            cell.classList.remove('incorrect', 'correct');
        }
    }

    moveCell(dRow, dCol) {
        const { layout } = this.puzzle.grid;
        let { row, col } = this.selectedCell;

        row += dRow;
        col += dCol;

        // Bounds check
        if (row < 0 || row >= layout.length) return;
        if (col < 0 || col >= layout[0].length) return;

        // Skip black cells
        if (layout[row][col] === '#') return;

        this.selectedCell = { row, col };

        // Update direction based on movement
        if (dRow !== 0) this.direction = 'down';
        if (dCol !== 0) this.direction = 'across';

        this.updateHighlights();
        this.updateCurrentClue();
    }

    moveToNextCell() {
        const { layout } = this.puzzle.grid;
        let { row, col } = this.selectedCell;

        if (this.direction === 'across') {
            col++;
            if (col >= layout[0].length || layout[row][col] === '#') {
                return; // End of word
            }
        } else {
            row++;
            if (row >= layout.length || layout[row][col] === '#') {
                return; // End of word
            }
        }

        this.selectedCell = { row, col };
        this.updateHighlights();
    }

    moveToPrevCell() {
        const { layout } = this.puzzle.grid;
        let { row, col } = this.selectedCell;

        if (this.direction === 'across') {
            col--;
            if (col < 0 || layout[row][col] === '#') {
                return;
            }
        } else {
            row--;
            if (row < 0 || layout[row][col] === '#') {
                return;
            }
        }

        this.selectedCell = { row, col };
        this.updateHighlights();
    }

    moveToNextClue() {
        const currentNum = this.getCurrentClueNumber();
        const numbering = this.puzzle.numbering[this.direction];
        const clues = this.puzzle.clues[this.direction];

        // Find current index
        let idx = clues.findIndex(c => c.number === currentNum);
        idx = (idx + 1) % clues.length;

        this.selectClue(this.direction, clues[idx].number);
    }

    moveToPrevClue() {
        const currentNum = this.getCurrentClueNumber();
        const clues = this.puzzle.clues[this.direction];

        let idx = clues.findIndex(c => c.number === currentNum);
        idx = (idx - 1 + clues.length) % clues.length;

        this.selectClue(this.direction, clues[idx].number);
    }

    async checkAnswers() {
        const { solution } = this.puzzle.grid;

        let errors = 0;
        let filled = 0;
        let total = 0;

        for (let r = 0; r < this.userGrid.length; r++) {
            for (let c = 0; c < this.userGrid[r].length; c++) {
                if (this.userGrid[r][c] === '#') continue;

                total++;
                const cellEl = document.querySelector(
                    `.cell[data-row="${r}"][data-col="${c}"]`
                );

                if (this.userGrid[r][c]) {
                    filled++;
                    if (this.userGrid[r][c] !== solution[r][c]) {
                        errors++;
                        cellEl?.classList.add('incorrect');
                        cellEl?.classList.remove('correct');
                    } else {
                        cellEl?.classList.add('correct');
                        cellEl?.classList.remove('incorrect');
                    }
                } else {
                    cellEl?.classList.remove('incorrect', 'correct');
                }
            }
        }

        const resultEl = document.getElementById('validation-result');
        if (errors === 0 && filled === total) {
            resultEl.textContent = 'Congratulations! Puzzle complete!';
            resultEl.className = 'validation-result success';
        } else if (errors === 0) {
            resultEl.textContent = `Looking good so far! ${total - filled} cells remaining.`;
            resultEl.className = 'validation-result success';
        } else {
            resultEl.textContent = `${errors} incorrect cell${errors > 1 ? 's' : ''} found.`;
            resultEl.className = 'validation-result error';
        }
    }

    clearValidation() {
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('incorrect', 'correct');
        });
        document.getElementById('validation-result').textContent = '';
        document.getElementById('validation-result').className = 'validation-result';
    }

    clearGrid() {
        const { layout } = this.puzzle.grid;

        for (let r = 0; r < this.userGrid.length; r++) {
            for (let c = 0; c < this.userGrid[r].length; c++) {
                if (layout[r][c] !== '#') {
                    this.setCell(r, c, '');
                }
            }
        }

        this.clearValidation();
    }

    revealAll() {
        const { solution } = this.puzzle.grid;

        for (let r = 0; r < solution.length; r++) {
            for (let c = 0; c < solution[r].length; c++) {
                if (solution[r][c] !== '#') {
                    this.setCell(r, c, solution[r][c]);
                }
            }
        }

        this.clearValidation();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.crossword = new CrosswordPuzzle();
});
