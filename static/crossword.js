/**
 * Crossword Puzzle Interactive Grid
 *
 * Handles all interactive functionality for the crossword puzzle:
 * - Puzzle list and storage
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
        this.direction = 'across';
        this.currentClueNumber = null;
        this.currentPuzzleInfo = null;

        this.initEventListeners();
        this.loadPuzzleList();
    }

    initEventListeners() {
        // Navigation tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Series filter
        document.getElementById('series-filter').addEventListener('change', (e) => {
            this.loadPuzzleList(e.target.value);
        });

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

        // Back button
        document.getElementById('back-btn').addEventListener('click', () => {
            this.showPuzzleList();
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

        // Modal controls
        document.getElementById('modal-cancel').addEventListener('click', () => {
            this.hideModal();
        });

        document.getElementById('add-answers-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitAnswersFile();
        });

        // Keyboard input
        document.addEventListener('keydown', (e) => {
            if (this.puzzle && this.selectedCell) {
                this.handleKeydown(e);
            }
        });
    }

    switchTab(tab) {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        if (tab === 'puzzles') {
            document.getElementById('puzzles-section').classList.remove('hidden');
            document.getElementById('upload-section').classList.add('hidden');
        } else {
            document.getElementById('puzzles-section').classList.add('hidden');
            document.getElementById('upload-section').classList.remove('hidden');
        }
    }

    async loadPuzzleList(seriesFilter = '') {
        try {
            const url = seriesFilter ? `/puzzles?series=${encodeURIComponent(seriesFilter)}` : '/puzzles';
            const response = await fetch(url);
            const data = await response.json();

            this.renderPuzzleList(data.puzzles);
            this.updateSeriesFilter(data.series);
        } catch (error) {
            console.error('Failed to load puzzles:', error);
        }
    }

    updateSeriesFilter(seriesList) {
        const select = document.getElementById('series-filter');
        const currentValue = select.value;

        select.innerHTML = '<option value="">All Series</option>';

        for (const series of seriesList) {
            const option = document.createElement('option');
            option.value = series;
            option.textContent = series;
            select.appendChild(option);
        }

        select.value = currentValue;
    }

    renderPuzzleList(puzzles) {
        const container = document.getElementById('puzzle-list');

        if (puzzles.length === 0) {
            container.innerHTML = '<p class="empty-message">No puzzles imported yet. Use the Import tab to add puzzles.</p>';
            return;
        }

        container.innerHTML = '';

        for (const puzzle of puzzles) {
            const item = document.createElement('div');
            item.className = 'puzzle-item';
            item.innerHTML = `
                <div class="puzzle-item-info">
                    <span class="puzzle-series">${puzzle.series}</span>
                    <span class="puzzle-number">#${puzzle.number}</span>
                    ${puzzle.has_answers ? '<span class="has-answers">✓ Answers</span>' : ''}
                </div>
                <div class="puzzle-item-actions">
                    ${!puzzle.has_answers ? `<button class="btn btn-small btn-secondary add-answers-btn" data-series="${puzzle.series}" data-number="${puzzle.number}">Add Answers</button>` : ''}
                    <button class="btn btn-small btn-primary play-btn" data-series="${puzzle.series}" data-number="${puzzle.number}">Play</button>
                </div>
            `;
            container.appendChild(item);
        }

        container.querySelectorAll('.play-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.loadPuzzle(btn.dataset.series, btn.dataset.number);
            });
        });

        container.querySelectorAll('.add-answers-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.showAddAnswersModal(btn.dataset.series, btn.dataset.number);
            });
        });
    }

    async loadPuzzle(series, puzzleNumber) {
        try {
            const response = await fetch(`/puzzles/${encodeURIComponent(series)}/${puzzleNumber}`);
            const data = await response.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            this.puzzle = data.puzzle;
            this.currentPuzzleInfo = { series, number: puzzleNumber };
            this.initUserGrid();
            this.renderPuzzle();

            document.getElementById('puzzle-title').textContent =
                `${this.puzzle.series || this.puzzle.publication} #${this.puzzle.number}`;

            document.getElementById('puzzles-section').classList.add('hidden');
            document.getElementById('upload-section').classList.add('hidden');
            document.getElementById('puzzle-section').classList.remove('hidden');
            document.querySelector('.nav-tabs').classList.add('hidden');

        } catch (error) {
            alert('Failed to load puzzle: ' + error.message);
        }
    }

    showPuzzleList() {
        document.getElementById('puzzle-section').classList.add('hidden');
        document.getElementById('puzzles-section').classList.remove('hidden');
        document.querySelector('.nav-tabs').classList.remove('hidden');
        this.loadPuzzleList();
    }

    showAddAnswersModal(series, puzzleNumber) {
        document.getElementById('modal-series').value = series;
        document.getElementById('modal-puzzle-number').value = puzzleNumber;
        document.getElementById('answers-modal').classList.remove('hidden');
    }

    hideModal() {
        document.getElementById('answers-modal').classList.add('hidden');
        document.getElementById('add-answers-form').reset();
    }

    async submitAnswersFile() {
        const series = document.getElementById('modal-series').value;
        const puzzleNumber = document.getElementById('modal-puzzle-number').value;
        const answersFile = document.getElementById('modal-answers-file').files[0];

        if (!answersFile) {
            alert('Please select an answers file');
            return;
        }

        const formData = new FormData();
        formData.append('answers_file', answersFile);

        try {
            const response = await fetch(`/puzzles/${encodeURIComponent(series)}/${puzzleNumber}/answers`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.hideModal();
                this.loadPuzzleList();
            } else {
                alert(data.error || 'Failed to add answers');
            }
        } catch (error) {
            alert('Failed to add answers: ' + error.message);
        }
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
            this.currentPuzzleInfo = data.storage;
            this.initUserGrid();
            this.renderPuzzle();

            if (data.warnings && data.warnings.length > 0) {
                this.showWarnings(data.warnings);
            }

            document.getElementById('puzzle-title').textContent =
                `${this.puzzle.series || this.puzzle.publication} #${this.puzzle.number}`;

            document.getElementById('puzzles-section').classList.add('hidden');
            document.getElementById('upload-section').classList.add('hidden');
            document.getElementById('puzzle-section').classList.remove('hidden');
            document.querySelector('.nav-tabs').classList.add('hidden');

            document.getElementById('pdf-upload-form').reset();
            document.getElementById('pdf-file-name').textContent = 'No file selected';
            document.getElementById('answers-file-name').textContent = 'No file selected';

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
            const container = document.getElementById('puzzle-section');
            const div = document.createElement('div');
            div.id = 'validation-warnings';
            div.className = 'validation-warnings';
            container.insertBefore(div, container.querySelector('.puzzle-layout'));
        }
        const el = document.getElementById('validation-warnings');
        el.innerHTML = `<strong>Warnings (${warnings.length}):</strong><ul>${warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
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
        const info = document.getElementById('puzzle-info');
        const parts = [];

        if (this.puzzle.publication) parts.push(this.puzzle.publication);
        if (this.puzzle.series) parts.push(this.puzzle.series);
        if (this.puzzle.number) parts.push(`#${this.puzzle.number}`);

        info.textContent = parts.join(' - ');
    }

    renderGrid() {
        const gridEl = document.getElementById('crossword-grid');
        gridEl.innerHTML = '';

        const { rows, cols, layout, cellNumbers } = this.puzzle.grid;

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
                    const key = `${r + 1},${c + 1}`;
                    if (cellNumbers && cellNumbers[key]) {
                        const numSpan = document.createElement('span');
                        numSpan.className = 'cell-number';
                        numSpan.textContent = cellNumbers[key];
                        cell.appendChild(numSpan);
                    }

                    const letterSpan = document.createElement('span');
                    letterSpan.className = 'cell-letter';
                    cell.appendChild(letterSpan);

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
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('selected', 'highlighted');
        });

        document.querySelectorAll('.clue-list li').forEach(li => {
            li.classList.remove('active');
        });

        if (!this.selectedCell) return;

        const { row, col } = this.selectedCell;

        const selectedEl = document.querySelector(
            `.cell[data-row="${row}"][data-col="${col}"]`
        );
        if (selectedEl) {
            selectedEl.classList.add('selected');
        }

        const wordCells = this.getWordCells(row, col);
        for (const { r, c } of wordCells) {
            const cellEl = document.querySelector(
                `.cell[data-row="${r}"][data-col="${c}"]`
            );
            if (cellEl) {
                cellEl.classList.add('highlighted');
            }
        }

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
        const cells = [];
        const { layout } = this.puzzle.grid;

        if (this.direction === 'across') {
            let c = col;
            while (c > 0 && layout[row][c - 1] !== '#') c--;

            while (c < layout[0].length && layout[row][c] !== '#') {
                cells.push({ r: row, c });
                c++;
            }
        } else {
            let r = row;
            while (r > 0 && layout[r - 1][col] !== '#') r--;

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
        const numbering = this.puzzle.numbering[this.direction];

        for (const n of numbering) {
            const startRow = n.row - 1;
            const startCol = n.col - 1;

            if (this.direction === 'across') {
                if (row === startRow && col >= startCol && col < startCol + n.length) {
                    return n.number;
                }
            } else {
                if (col === startCol && row >= startRow && row < startRow + n.length) {
                    return n.number;
                }
            }
        }

        return null;
    }

    updateCurrentClue() {
        const numEl = document.getElementById('current-clue-number');
        const textEl = document.getElementById('current-clue-text');

        const number = this.getCurrentClueNumber();
        if (!number) {
            numEl.textContent = '';
            textEl.textContent = '';
            return;
        }

        const dirLabel = this.direction === 'across' ? 'A' : 'D';
        numEl.textContent = `${number}${dirLabel}`;

        const clue = this.puzzle.clues[this.direction].find(c => c.number === number);
        textEl.textContent = clue ? clue.clue : '';
    }

    handleKeydown(e) {
        const { row, col } = this.selectedCell;
        const { layout } = this.puzzle.grid;

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
                    this.setCell(row, col, '');
                } else {
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

    setCell(row, col, value) {
        this.userGrid[row][col] = value;

        const cellEl = document.querySelector(
            `.cell[data-row="${row}"][data-col="${col}"] .cell-letter`
        );
        if (cellEl) {
            cellEl.textContent = value;
        }
    }

    moveCell(dRow, dCol) {
        const { layout } = this.puzzle.grid;
        let { row, col } = this.selectedCell;

        row += dRow;
        col += dCol;

        if (row < 0 || row >= layout.length ||
            col < 0 || col >= layout[0].length ||
            layout[row][col] === '#') {
            return;
        }

        if (dRow !== 0) this.direction = 'down';
        if (dCol !== 0) this.direction = 'across';

        this.selectedCell = { row, col };
        this.updateHighlights();
        this.updateCurrentClue();
    }

    moveToNextCell() {
        const { layout } = this.puzzle.grid;
        let { row, col } = this.selectedCell;

        if (this.direction === 'across') {
            col++;
            if (col >= layout[0].length || layout[row][col] === '#') {
                return;
            }
        } else {
            row++;
            if (row >= layout.length || layout[row][col] === '#') {
                return;
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
        const clues = this.puzzle.clues[this.direction];

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
                    if (solution[r][c] !== '-' && this.userGrid[r][c] !== solution[r][c]) {
                        cellEl.classList.add('incorrect');
                        errors++;
                    } else if (solution[r][c] !== '-') {
                        cellEl.classList.add('correct');
                    }
                }
            }
        }

        const resultEl = document.getElementById('validation-result');
        if (errors === 0 && filled === total) {
            resultEl.textContent = 'Congratulations! Puzzle complete!';
            resultEl.className = 'validation-result success';
        } else if (errors === 0) {
            resultEl.textContent = `${filled}/${total} cells filled. Keep going!`;
            resultEl.className = 'validation-result success';
        } else {
            resultEl.textContent = `${errors} incorrect cell${errors > 1 ? 's' : ''} found.`;
            resultEl.className = 'validation-result error';
        }
    }

    clearValidation() {
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('correct', 'incorrect');
        });
        document.getElementById('validation-result').textContent = '';
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
        const { solution, layout } = this.puzzle.grid;

        for (let r = 0; r < solution.length; r++) {
            for (let c = 0; c < solution[r].length; c++) {
                if (layout[r][c] !== '#' && solution[r][c] !== '-') {
                    this.setCell(r, c, solution[r][c]);
                }
            }
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new CrosswordPuzzle();
});
