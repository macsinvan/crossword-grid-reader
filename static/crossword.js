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

        // Trainer state
        this.templateTrainer = null;
        this.trainerWordData = null;

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
            // Don't intercept keyboard when typing in the trainer input
            if (e.target.id === 'trainer-text-input') {
                return;
            }
            if (this.puzzle && this.selectedCell) {
                this.handleKeydown(e);
            }
        });

        // Trainer controls
        document.getElementById('solve-btn').addEventListener('click', () => {
            this.openTrainer();
        });

        document.getElementById('trainer-close').addEventListener('click', () => {
            this.closeTrainer();
        });
    }

    // =========================================================================
    // TRAINER FUNCTIONALITY
    // =========================================================================

    async openTrainer() {
        if (!this.selectedCell || !this.puzzle) return;

        const wordData = this.getWordDataForTrainer();
        if (!wordData) return;

        // Store current word data for later
        this.trainerWordData = wordData;

        // Show the modal
        document.getElementById('trainer-modal').classList.remove('hidden');
        document.getElementById('trainer-clue-number').textContent = `${wordData.clueNumber}${wordData.direction === 'across' ? 'A' : 'D'}`;
        document.getElementById('trainer-clue-text').textContent = wordData.clueText;

        // Get puzzle number for clue lookup
        const puzzleNumber = this.currentPuzzleInfo?.number || this.puzzle?.number;

        // First, start the session via API to get the clue_id
        try {
            const response = await fetch('/trainer/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clue_text: wordData.clueText,
                    enumeration: wordData.enumeration,
                    cross_letters: wordData.crossLetters,
                    puzzle_number: puzzleNumber,
                    clue_number: wordData.clueNumber,
                    direction: wordData.direction
                })
            });

            const data = await response.json();

            if (data.error) {
                document.getElementById('trainer-container').innerHTML = `
                    <div style="padding: 2rem; text-align: center; color: #666;">
                        <p>${data.error}</p>
                        <p style="font-style: italic; margin-top: 0.5rem;">This clue has not been annotated for training yet.</p>
                    </div>
                `;
                return;
            }

            // Create TemplateTrainer instance with the clue_id from server
            const container = document.getElementById('trainer-container');
            this.templateTrainer = new TemplateTrainer(container, {
                clueId: data.clue_id,
                clueText: wordData.clueText,
                enumeration: wordData.enumeration,
                answer: data.render?.answer || '',
                onComplete: () => {
                    this.applyTrainerAnswer();
                    this.closeTrainer();
                },
                onBack: () => this.closeTrainer()
            });

            // Store the initial render state
            this.templateTrainer.render = data.render;
            this.templateTrainer.loading = false;
            this.templateTrainer.renderUI();

        } catch (error) {
            console.error('Trainer API error:', error);
            document.getElementById('trainer-container').innerHTML = `
                <div style="padding: 2rem; text-align: center; color: #dc2626;">
                    <p>Could not connect to trainer service</p>
                </div>
            `;
        }
    }

    closeTrainer() {
        document.getElementById('trainer-modal').classList.add('hidden');
        this.templateTrainer = null;
        this.trainerWordData = null;
    }

    applyTrainerAnswer() {
        if (!this.templateTrainer?.render?.answer || !this.trainerWordData) {
            this.closeTrainer();
            return;
        }

        const letters = this.templateTrainer.render.answer.toUpperCase().split('');
        const cells = this.trainerWordData.cells;

        cells.forEach(({ r, c }, i) => {
            if (letters[i]) {
                this.setCell(r, c, letters[i]);
            }
        });

        this.closeTrainer();
        this.updateHighlights();
    }

    getWordDataForTrainer() {
        if (!this.selectedCell) return null;

        const { row, col } = this.selectedCell;
        const number = this.getCurrentClueNumber();
        if (!number) return null;

        const clue = this.puzzle.clues[this.direction].find(c => c.number === number);
        if (!clue) return null;

        const wordCells = this.getWordCells(row, col);
        const numbering = this.puzzle.numbering[this.direction].find(n => n.number === number);

        // Extract cross letters (letters already filled in)
        const crossLetters = wordCells.map(({ r, c }, index) => ({
            position: index,
            letter: this.userGrid[r][c] || null
        })).filter(cl => cl.letter);

        // Extract enumeration from clue text (e.g., "(5)" or "(3-4)")
        const enumMatch = clue.clue.match(/\([\d,\-\s]+\)\s*$/);
        const enumeration = enumMatch ? enumMatch[0].replace(/[()]/g, '').trim() : String(numbering?.length || wordCells.length);

        return {
            clueNumber: number,
            direction: this.direction,
            clueText: clue.clue,
            length: numbering?.length || wordCells.length,
            enumeration: enumeration,
            crossLetters: crossLetters,
            cells: wordCells
        };
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
                    <div class="puzzle-item-title">${puzzle.series} #${puzzle.number}</div>
                    <div class="puzzle-item-meta">
                        ${puzzle.date ? `<span class="puzzle-date">${puzzle.date}</span>` : ''}
                        ${puzzle.has_answers ? '<span class="has-answers">✓ Answers</span>' : '<span class="no-answers">No answers</span>'}
                    </div>
                </div>
                <div class="puzzle-item-actions">
                    ${!puzzle.has_answers ? `<button class="btn btn-small btn-secondary add-answers-btn" data-series="${puzzle.series}" data-number="${puzzle.number}">Add Answers</button>` : ''}
                    <button class="btn btn-small btn-primary play-btn" data-series="${puzzle.series}" data-number="${puzzle.number}">Play</button>
                    <button class="btn btn-small btn-danger delete-btn" data-series="${puzzle.series}" data-number="${puzzle.number}" title="Delete puzzle">✕</button>
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

        container.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.deletePuzzle(btn.dataset.series, btn.dataset.number);
            });
        });
    }

    async deletePuzzle(series, puzzleNumber) {
        if (!confirm(`Delete ${series} #${puzzleNumber}? This cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/puzzles/${encodeURIComponent(series)}/${puzzleNumber}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Delete failed');
            }

            // Refresh the puzzle list
            this.loadPuzzleList(document.getElementById('series-filter').value);
        } catch (error) {
            alert('Failed to delete puzzle: ' + error.message);
        }
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

            // Try to restore saved progress
            if (this.loadProgress()) {
                console.log('Restored saved progress');
            }

            const titleParts = [`${this.puzzle.series || this.puzzle.publication} #${this.puzzle.number}`];
            if (this.puzzle.date) {
                titleParts.push(`— ${this.puzzle.date}`);
            }
            document.getElementById('puzzle-title').textContent = titleParts.join(' ');

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

            const titleParts = [`${this.puzzle.series || this.puzzle.publication} #${this.puzzle.number}`];
            if (this.puzzle.date) {
                titleParts.push(`— ${this.puzzle.date}`);
            }
            document.getElementById('puzzle-title').textContent = titleParts.join(' ');

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
        // If clicking the same cell, toggle direction
        if (this.selectedCell &&
            this.selectedCell.row === row &&
            this.selectedCell.col === col) {
            this.toggleDirection();
            return;
        }

        this.selectedCell = { row, col };

        // Determine best direction for this cell
        const canGoAcross = this.isPartOfAcross(row, col);
        const canGoDown = this.isPartOfDown(row, col);

        if (canGoAcross && !canGoDown) {
            // Cell is only part of an across word
            this.direction = 'across';
        } else if (canGoDown && !canGoAcross) {
            // Cell is only part of a down word
            this.direction = 'down';
        }
        // If both directions valid, keep current direction preference

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
            document.getElementById('solve-btn').disabled = true;
            return;
        }

        const dirLabel = this.direction === 'across' ? 'A' : 'D';
        numEl.textContent = `${number}${dirLabel}`;

        const clue = this.puzzle.clues[this.direction].find(c => c.number === number);
        textEl.textContent = clue ? clue.clue : '';

        // Enable solve button when a clue is selected
        document.getElementById('solve-btn').disabled = false;
    }

    handleKeydown(e) {
        // Allow browser shortcuts (Cmd+R, Ctrl+R, etc.) to work normally
        if (e.metaKey || e.ctrlKey) return;

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

        // Auto-save progress
        this.saveProgress();
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
        this.clearProgress();
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
        // Clear saved progress when solution is revealed
        this.clearProgress();
    }

    // =========================================================================
    // PROGRESS PERSISTENCE (localStorage)
    // =========================================================================

    getStorageKey() {
        if (!this.currentPuzzleInfo) return null;
        return `puzzle-progress-${this.currentPuzzleInfo.series}-${this.currentPuzzleInfo.number}`;
    }

    saveProgress() {
        const key = this.getStorageKey();
        if (!key || !this.userGrid) return;

        try {
            const progress = {
                userGrid: this.userGrid,
                selectedCell: this.selectedCell,
                direction: this.direction,
                timestamp: Date.now()
            };
            localStorage.setItem(key, JSON.stringify(progress));
        } catch (e) {
            console.warn('Failed to save progress:', e);
        }
    }

    loadProgress() {
        const key = this.getStorageKey();
        if (!key) return false;

        try {
            const saved = localStorage.getItem(key);
            if (!saved) return false;

            const progress = JSON.parse(saved);

            // Verify grid dimensions match
            if (!progress.userGrid ||
                progress.userGrid.length !== this.userGrid.length ||
                progress.userGrid[0]?.length !== this.userGrid[0]?.length) {
                console.warn('Saved progress grid dimensions mismatch, starting fresh');
                this.clearProgress();
                return false;
            }

            // Restore state
            this.userGrid = progress.userGrid;
            this.selectedCell = progress.selectedCell;
            this.direction = progress.direction || 'across';

            // Update DOM with restored letters
            for (let r = 0; r < this.userGrid.length; r++) {
                for (let c = 0; c < this.userGrid[r].length; c++) {
                    const letter = this.userGrid[r][c];
                    if (letter && letter !== '#') {
                        const cellEl = document.querySelector(
                            `.cell[data-row="${r}"][data-col="${c}"] .cell-letter`
                        );
                        if (cellEl) {
                            cellEl.textContent = letter;
                        }
                    }
                }
            }

            return true;
        } catch (e) {
            console.warn('Failed to load progress:', e);
            return false;
        }
    }

    clearProgress() {
        const key = this.getStorageKey();
        if (key) {
            try {
                localStorage.removeItem(key);
            } catch (e) {
                console.warn('Failed to clear progress:', e);
            }
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new CrosswordPuzzle();
});
