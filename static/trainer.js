/**
 * TemplateTrainer - Port of React TemplateTrainer.tsx to vanilla JavaScript
 *
 * This is an exact port of the cryptic-trainer React component.
 * Layout:
 * - Section 1: Clue words (tappable when inputMode === 'tap_words')
 * - Section 2: Answer Entry - crossword boxes
 * - Section 3: Action Required + Button
 * - Section 4: Details (multiple choice, intro, teaching panel, learnings)
 */

class TemplateTrainer {
    constructor(container, options) {
        this.container = container;
        this.clueId = options.clueId;
        this.clueText = options.clueText;
        this.enumeration = options.enumeration;
        this.answer = options.answer;
        this.crossLetters = options.crossLetters || [];
        this.onComplete = options.onComplete;
        this.onBack = options.onBack;

        // Server state (source of truth)
        this.render = null;
        this.loading = true;
        this.error = null;

        // Ephemeral UI state for step interactions
        this.selectedIndices = [];
        this.textInput = '';
        this.feedback = null;
        this.userAnswer = [];  // Track letters typed in answer boxes
        this.answerLocked = false;  // Lock boxes after correct answer typed
        this.stepTextInput = [];  // Track letters typed in step text input boxes
        this.hintVisible = false;  // Toggle hint visibility

        // Parse enumeration to get letter count
        this.letterCount = this.enumeration.split(/[^0-9]+/).filter(Boolean)
            .reduce((sum, n) => sum + parseInt(n, 10), 0) || this.answer.length || 10;

        // Split clue into words (matching React line 89)
        this.words = this.clueText.replace(/[,;:]/g, ' ').split(/\s+/).filter(Boolean);

        // Note: Don't auto-init here - crossword.js sets render and calls renderUI() directly
    }

    // =========================================================================
    // API CALLS
    // =========================================================================

    // Start session - React lines 94-112
    // Note: In this port, the session is already started by crossword.js openTrainer()
    // which calls /trainer/start. This method is called but the initial render state
    // is already set by crossword.js, so we just render the UI.
    async startSession() {
        // Reset user answer for new session
        this.userAnswer = [];

        // The session was already started by openTrainer() in crossword.js
        // which sets this.render before creating the TemplateTrainer instance
        // If render is already set, just render the UI
        if (this.render) {
            this.loading = false;
            this.renderUI();
            return;
        }

        // Fallback: start a new session if render wasn't provided
        this.loading = true;
        this.error = null;
        this.renderLoading();

        try {
            const response = await fetch('/trainer/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId })
            });

            const data = await response.json();

            if (data.success === false || data.error) {
                this.error = data.error || 'Failed to start training';
                this.renderError();
                return;
            }

            this.render = data.render;
            this.clueId = data.clue_id || this.clueId;
            this.loading = false;
            this.renderUI();

        } catch (e) {
            this.error = String(e);
            this.renderError();
        }
    }

    async submitInput(value) {
        if (!this.render) return;

        this.feedback = null;

        try {
            const response = await fetch('/trainer/input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId, value: value })
            });

            const data = await response.json();

            if (data.success !== false) {
                if (data.correct) {
                    // Correct - update render state and clear selections (React lines 296-302)
                    // Note: Server returns render data flat, not under data.render
                    this.render = data.render || data;
                    this.selectedIndices = [];
                    this.textInput = '';
                    this.stepTextInput = [];
                    this.hintVisible = false;
                    this.feedback = null;
                    this.renderUI();
                } else {
                    // Wrong - show feedback (React lines 305-310)
                    this.feedback = {
                        correct: false,
                        message: data.message || 'Try again'
                    };
                    this.renderUI();
                }
            } else {
                this.error = data.error || 'Server error';
                this.renderError();
            }
        } catch (e) {
            this.error = String(e);
            this.renderError();
        }
    }

    async submitContinue() {
        try {
            const response = await fetch('/trainer/continue', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId })
            });

            const data = await response.json();

            if (data.success !== false) {
                // Note: Server returns render data flat, not under data.render
                this.render = data.render || data;
                this.selectedIndices = [];
                this.textInput = '';
                this.stepTextInput = [];
                this.hintVisible = false;
                this.feedback = null;
                this.renderUI();
            } else {
                this.error = data.error || 'Server error';
                this.renderError();
            }
        } catch (e) {
            this.error = String(e);
            this.renderError();
        }
    }

    async handleSolveStep() {
        // Call server to reveal answer for current step
        try {
            const response = await fetch('/trainer/solve-step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId })
            });

            const data = await response.json();

            if (data.success) {
                // Show the revealed answer briefly, then update UI
                this.feedback = {
                    correct: true,
                    message: data.message || `Answer revealed: ${data.revealed}`
                };
                this.render = data.render || this.render;
                this.selectedIndices = [];
                this.textInput = '';
                this.stepTextInput = [];
                this.hintVisible = false;
                this.renderUI();
            } else {
                this.error = data.error || 'Could not reveal step';
                this.renderError();
            }
        } catch (e) {
            this.error = String(e);
            this.renderError();
        }
    }

    async handleSolve() {
        // Give up - reveal full answer and show summary with learnings
        try {
            const response = await fetch('/trainer/reveal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId })
            });

            const data = await response.json();

            if (data.success) {
                // Show summary with learnings, "Done" button will complete
                this.render = data;
                this.answerLocked = true;  // Lock answer boxes to show the answer
                this.renderUI();
            } else {
                this.error = data.error || 'Could not reveal answer';
                this.renderError();
            }
        } catch (e) {
            this.error = String(e);
            this.renderError();
        }
    }

    // =========================================================================
    // EVENT HANDLERS (matching React handlers)
    // =========================================================================

    // handleWordTap - React lines 239-269
    handleWordTap(index) {
        if (this.render?.inputMode !== 'tap_words') return;

        this.feedback = null;

        // If autoCheck is true, submit immediately (React lines 244-260)
        if (this.render?.autoCheck) {
            this.submitInput([index]);
            return;
        }

        // Otherwise toggle selection (React lines 262-268)
        const currentIndex = this.selectedIndices.indexOf(index);
        if (currentIndex !== -1) {
            this.selectedIndices.splice(currentIndex, 1);
        } else {
            this.selectedIndices.push(index);
        }

        this.renderUI();
    }

    // handleSubmit - React lines 274-318
    handleSubmit(optionIndex) {
        if (!this.render) return;

        this.feedback = null;

        // Determine value based on input mode (React lines 279-290)
        let value;
        if (this.render.inputMode === 'tap_words') {
            value = this.selectedIndices;
        } else if (this.render.inputMode === 'multiple_choice') {
            value = optionIndex !== undefined ? optionIndex : 0;
        } else {
            value = this.textInput;
        }

        this.submitInput(value);
    }

    // =========================================================================
    // RENDERING HELPERS
    // =========================================================================

    // getWordColor - React lines 401-419
    getWordColor(index) {
        // Check confirmed highlights from server
        const highlight = this.render?.highlights?.find(h => h.indices.includes(index));
        if (highlight) {
            switch (highlight.color) {
                case 'GREEN': return '#22c55e';
                case 'ORANGE': return '#f97316';
                case 'BLUE': return '#3b82f6';
                case 'PURPLE': return '#a855f7';
            }
        }

        // Check ephemeral selection
        if (this.selectedIndices.includes(index)) {
            return '#94a3b8'; // gray for selection
        }

        return null;
    }

    // canSubmit - React lines 452-458
    canSubmit() {
        if (this.render?.inputMode === 'tap_words') {
            return this.selectedIndices.length > 0;
        } else if (this.render?.inputMode === 'multiple_choice') {
            return false; // Multiple choice submits immediately on click
        } else if (this.render?.inputMode === 'text') {
            return this.textInput.trim().length > 0;
        }
        return false;
    }

    // =========================================================================
    // RENDER METHODS
    // =========================================================================

    renderLoading() {
        this.container.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; padding: 2rem;">
                <div style="width: 2rem; height: 2rem; border: 4px solid #3b82f6; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            </div>
            <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
        `;
    }

    renderError() {
        this.container.innerHTML = `
            <div style="padding: 1rem; color: #dc2626; background: #fef2f2; border-radius: 0.5rem;">
                <p style="font-weight: 500;">Error</p>
                <p style="font-size: 0.875rem;">${this.error}</p>
                <button onclick="this.closest('.trainer-content').trainer.onBack?.()"
                    style="margin-top: 1rem; padding: 0.5rem 1rem; background: #e5e7eb; border-radius: 0.375rem; border: none; cursor: pointer;">
                    Go Back
                </button>
            </div>
        `;
    }

    renderUI() {
        if (!this.render) return;

        const isComplete = this.render.complete;
        const isTeaching = this.render.phaseId === 'teaching';

        // If complete, auto-apply answer and close (no button required)
        if (isComplete) {
            if (this.onComplete) {
                this.onComplete();
            }
            return;
        }

        // If answer was revealed (Solve button), show the complete/summary view
        // This lets user see the learnings before applying to grid
        if (this.render.revealed) {
            this.renderComplete();
            return;
        }

        // Build main UI (React lines 577-782)
        const html = `
            <!-- SECTION 1: CLUE WORDS (React lines 579-601) -->
            <div style="background: white; border-radius: 0.75rem 0.75rem 0 0; border: 1px solid #e5e7eb; border-bottom: none; padding: 1rem; min-height: 100px;">
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 1.25rem; font-family: serif; line-height: 1.625;">
                    ${this.words.map((word, index) => {
                        const bgColor = this.getWordColor(index);
                        const isTapMode = this.render.inputMode === 'tap_words';
                        return `<span
                            data-word-index="${index}"
                            style="padding: 0.125rem 0.375rem; border-radius: 0.25rem; transition: all 0.2s; cursor: ${isTapMode ? 'pointer' : 'default'}; ${bgColor ? `background-color: ${bgColor}; color: white;` : ''}"
                            ${isTapMode ? '' : ''}
                        >${word}</span>`;
                    }).join('')}
                    <span style="color: #9ca3af;">(${this.enumeration})</span>
                </div>
            </div>

            <!-- SECTION 2: INPUT AREA (React lines 603-635) -->
            <div style="background: #f8fafc; border: 1px solid #e5e7eb; border-bottom: none; padding: 1rem; min-height: 80px; display: flex; flex-direction: column; justify-content: center;">
                ${this.renderInputArea()}
            </div>

            <!-- SECTION 3: ACTION + BUTTON (React lines 637-675) -->
            <div style="border: 1px solid #e5e7eb; border-radius: 0 0 0.75rem 0.75rem; padding: 1rem; min-height: 70px; background: white;">
                ${this.render.stepProgress ? `
                    <div style="margin-bottom: 0.75rem; display: inline-block; padding: 0.25rem 0.75rem; background: #fef3c7; color: #92400e; font-size: 0.875rem; font-weight: 500; border-radius: 0.5rem;">
                        ${this.render.stepProgress.label}
                    </div>
                ` : ''}
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
                    <p style="flex: 1; font-weight: 500; color: #374151;">
                        ${isTeaching ? this.render.actionPrompt : (this.render.panel?.instruction || this.render.actionPrompt || '')}
                    </p>
                    <div style="display: flex; align-items: center; gap: 0.25rem;">
                        ${this.renderHintButton()}
                        ${this.renderSolveStepButton()}
                    </div>
                    ${this.renderActionButton()}
                </div>
                ${this.renderHintContent()}
            </div>

            <!-- SECTION 4: DETAILS (React lines 677-780) -->
            <div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 1rem;">
                ${this.renderFeedback()}
                ${this.renderMultipleChoice()}
                ${this.renderIntro()}
                ${this.renderTeachingPanel()}
                ${this.renderLearnings()}
            </div>

        `;

        this.container.innerHTML = html;
        this.attachEventListeners();
    }

    // Input area - React lines 603-635
    // Shows either: text input (for intermediate steps) OR answer entry boxes
    renderInputArea() {
        const isTeaching = this.render?.phaseId === 'teaching';
        const stepType = this.render?.stepType;
        const isFinalAnswerStep = stepType === 'anagram_solve' || stepType === 'double_definition';

        // Text input for intermediate steps - crossword-style boxes
        if (this.render?.inputMode === 'text' && !isTeaching && !isFinalAnswerStep) {
            const expectedLength = typeof this.render?.expected === 'string' ? this.render.expected.length : 5;
            return `
                <div style="display: flex; gap: 4px; justify-content: center; flex-wrap: wrap;">
                    ${this.renderTextInputBoxes(expectedLength)}
                </div>
            `;
        }

        // Default: Answer entry boxes with Solve button
        return `
            <div style="display: flex; gap: 8px; align-items: center; justify-content: center; flex-wrap: wrap;">
                <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                    ${this.renderAnswerBoxes()}
                </div>
                ${this.renderSolveButton()}
            </div>
        `;
    }

    renderAnswerBoxes() {
        const rawAnswer = this.render?.answer || this.answer || '';
        // Filter out spaces - answer boxes only show letters
        const answer = rawAnswer.replace(/\s/g, '');
        const isComplete = this.render?.complete;
        const isAnswerKnown = this.render?.answerKnown || false;
        // Only lock boxes if user typed correct answer in THIS session (tracked locally)
        const isAnswerLocked = this.answerLocked || false;

        return answer.split('').map((letter, i) => {
            // Check if this position has a cross letter from the grid
            const crossLetter = this.crossLetters?.find(cl => cl.position === i);
            const isCrossLetter = !isComplete && !isAnswerLocked && crossLetter?.letter;

            // Determine what to display
            let displayLetter = '';
            if (isComplete || isAnswerLocked) {
                displayLetter = letter;
            } else if (isCrossLetter) {
                displayLetter = crossLetter.letter;
            } else {
                displayLetter = this.userAnswer[i] || '';
            }

            // Cross letters and completed answers are read-only
            if (isCrossLetter || isComplete || isAnswerLocked) {
                return `<div class="answer-box ${isCrossLetter ? 'cross-letter' : ''}"
                            data-position="${i}"
                            style="width: 32px; height: 40px; border: 2px solid ${isCrossLetter ? '#3b82f6' : '#d1d5db'};
                                   border-radius: 4px; display: flex; align-items: center; justify-content: center;
                                   font-weight: bold; font-size: 1.25rem;
                                   background: ${isCrossLetter ? '#eff6ff' : (isAnswerKnown ? '#f0fdf4' : 'white')};">
                    ${displayLetter}
                </div>`;
            } else {
                // Editable input for user entry
                return `<input type="text"
                               class="answer-box-input"
                               data-position="${i}"
                               maxlength="1"
                               value="${displayLetter}"
                               autocomplete="off"
                               autocapitalize="characters"
                               spellcheck="false"
                               style="width: 32px; height: 40px; border: 2px solid #d1d5db;
                                      border-radius: 4px; text-align: center;
                                      font-weight: bold; font-size: 1.25rem;
                                      color: #111827; background: white; outline: none;
                                      text-transform: uppercase; caret-color: #2563eb;"
                        />`;
            }
        }).join('');
    }

    renderTextInputBoxes(expectedLength) {
        return Array(expectedLength).fill('').map((_, i) => {
            const displayLetter = this.stepTextInput[i] || '';
            return `<input type="text"
                           class="step-text-input"
                           data-position="${i}"
                           maxlength="1"
                           value="${displayLetter}"
                           autocomplete="off"
                           autocapitalize="characters"
                           spellcheck="false"
                           style="width: 32px; height: 40px; border: 2px solid #d1d5db;
                                  border-radius: 4px; text-align: center;
                                  font-weight: bold; font-size: 1.25rem;
                                  color: #111827; background: white; outline: none;
                                  text-transform: uppercase; caret-color: #2563eb;"
                    />`;
        }).join('');
    }

    renderActionButton() {
        // Continue button (React lines 653-659)
        if (this.render.button) {
            return `<button data-action="continue" style="padding: 0.5rem 1.25rem; background: #2563eb; color: white; font-weight: 500; border-radius: 0.5rem; border: none; cursor: pointer; white-space: nowrap;">
                ${this.render.button.label}
            </button>`;
        }

        // Check button for tap_words and text modes (React lines 660-673)
        if (this.render.inputMode !== 'none' && this.render.inputMode !== 'multiple_choice') {
            const canSubmit = this.canSubmit();
            return `<button data-action="submit" ${canSubmit ? '' : 'disabled'} style="padding: 0.5rem 1.25rem; background: ${canSubmit ? '#2563eb' : '#e5e7eb'}; color: ${canSubmit ? 'white' : '#9ca3af'}; font-weight: 500; border-radius: 0.5rem; border: none; cursor: ${canSubmit ? 'pointer' : 'not-allowed'}; white-space: nowrap;">
                Check
            </button>`;
        }

        return '';
    }

    // Feedback message - React lines 680-687
    renderFeedback() {
        if (!this.feedback) return '';
        const bgColor = this.feedback.correct ? '#dcfce7' : '#fee2e2';
        const textColor = this.feedback.correct ? '#166534' : '#991b1b';
        return `<div style="padding: 0.75rem; border-radius: 0.5rem; background: ${bgColor}; color: ${textColor};">
            ${this.feedback.message || this.feedback}
        </div>`;
    }

    // Multiple choice options - React lines 715-741
    renderMultipleChoice() {
        if (this.render.inputMode !== 'multiple_choice' || !this.render.options) return '';

        return `<div style="display: flex; flex-direction: column; gap: 0.5rem;">
            ${this.render.options.map((option, index) => `
                <button data-option-index="${index}" style="width: 100%; padding: 0.75rem 1rem; text-align: left; border-radius: 0.5rem; border: 2px solid #e5e7eb; background: white; cursor: pointer; display: flex; align-items: center; gap: 0.75rem; transition: all 0.2s;">
                    <span style="width: 1.25rem; height: 1.25rem; border-radius: 50%; border: 2px solid #d1d5db; display: flex; align-items: center; justify-content: center; flex-shrink: 0;"></span>
                    <span style="font-weight: 500;">${option.label}</span>
                </button>
            `).join('')}
        </div>`;
    }

    // Intro card - React lines 744-753
    renderIntro() {
        if (!this.render.intro || this.render.phaseId === 'teaching') return '';

        return `<div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 1rem; border-radius: 0 0.5rem 0.5rem 0;">
            <h3 style="font-weight: bold; color: #1e40af;">${this.render.intro.title}</h3>
            <p style="color: #1d4ed8; margin-top: 0.25rem; white-space: pre-line;">${this.render.intro.text}</p>
            ${this.render.intro.example ? `<p style="color: #2563eb; font-size: 0.875rem; margin-top: 0.5rem; font-style: italic; white-space: pre-line;">${this.render.intro.example}</p>` : ''}
        </div>`;
    }

    // Teaching panel - React lines 755-766
    renderTeachingPanel() {
        if (this.render.phaseId !== 'teaching' || !this.render.panel) return '';

        return `<div style="background: #fefce8; border: 2px solid #fbbf24; border-radius: 0.75rem; padding: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.25rem;">🎓</span>
                <h3 style="font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.875rem; color: #a16207;">
                    ${this.render.panel.title}
                </h3>
            </div>
            <p style="color: #854d0e; white-space: pre-line;">${this.render.panel.instruction}</p>
        </div>`;
    }

    // Hint button - lightbulb icon to reveal hints
    renderHintButton() {
        if (!this.render?.hint) return '';

        const opacity = this.hintVisible ? '1' : '0.5';

        return `<button class="hint-button"
                        style="background: none; border: none; font-size: 1.5rem;
                               cursor: pointer; padding: 0.25rem; opacity: ${opacity};
                               transition: opacity 0.2s;"
                        title="${this.hintVisible ? 'Hide hint' : 'Show hint'}">
            💡
        </button>`;
    }

    // Solve step button - reveals answer for current step
    renderSolveStepButton() {
        // Only show for interactive phases (not teaching/none)
        const inputMode = this.render?.inputMode;
        if (!inputMode || inputMode === 'none') return '';

        return `<button class="solve-step-button"
                        style="background: none; border: none; font-size: 1.25rem;
                               cursor: pointer; padding: 0.25rem; opacity: 0.5;
                               transition: opacity 0.2s;"
                        title="Reveal answer for this step">
            🔓
        </button>`;
    }

    // Solve button - reveals full answer and completes training
    renderSolveButton() {
        return `<button class="solve-button"
                        style="padding: 0.25rem 0.5rem; background: none; color: #9ca3af;
                               font-weight: 400; border-radius: 0.25rem; border: 1px solid #e5e7eb;
                               cursor: pointer; font-size: 0.75rem; opacity: 0.7;
                               transition: opacity 0.2s, color 0.2s;"
                        title="Give up and reveal the answer"
                        onmouseover="this.style.opacity='1'; this.style.color='#6b7280';"
                        onmouseout="this.style.opacity='0.7'; this.style.color='#9ca3af';">
            Solve
        </button>`;
    }

    // Hint content - shown when lightbulb clicked
    renderHintContent() {
        if (!this.hintVisible || !this.render?.hint) return '';

        return `<div class="hint-content"
                     style="background: #fef3c7; border: 1px solid #fbbf24;
                            border-radius: 0.5rem; padding: 0.75rem; margin-top: 0.5rem;
                            color: #92400e; font-size: 0.9rem;">
            💡 ${this.render.hint}
        </div>`;
    }

    // Previous learnings - React lines 768-779
    renderLearnings() {
        if (!this.render.learnings || this.render.learnings.length === 0) return '';

        return `<div style="display: flex; flex-direction: column; gap: 0.5rem;">
            ${this.render.learnings.map(learning => `
                <div style="background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 0.5rem 0.75rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="color: #f59e0b; font-size: 0.875rem;">🎓</span>
                        <span style="font-weight: bold; color: #475569; font-size: 0.875rem;">${learning.title}</span>
                    </div>
                </div>
            `).join('')}
        </div>`;
    }

    // Solved view - React lines 461-574
    renderComplete() {
        const html = `
            <!-- SOLVED HEADER -->
            <div style="background: #16a34a; border-radius: 0.75rem 0.75rem 0 0; padding: 1.5rem; text-align: center;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🎉</div>
                <h2 style="font-size: 1.5rem; font-weight: bold; color: white;">Solved!</h2>
                <p style="color: #bbf7d0; margin-top: 0.25rem; font-size: 1.125rem; font-family: serif;">${this.answer}</p>
            </div>

            <!-- CLUE WITH HIGHLIGHTS -->
            <div style="background: white; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb; padding: 1rem;">
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 1.125rem; font-family: serif; line-height: 1.625;">
                    ${this.words.map((word, index) => {
                        const bgColor = this.getWordColor(index);
                        return `<span style="padding: 0.125rem 0.375rem; border-radius: 0.25rem; ${bgColor ? `background-color: ${bgColor}; color: white;` : ''}">${word}</span>`;
                    }).join('')}
                    <span style="color: #9ca3af;">(${this.enumeration})</span>
                </div>
            </div>

            <!-- LEARNINGS SECTION -->
            <div style="background: #f8fafc; border-left: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb; border-top: 1px solid #e5e7eb; padding: 1rem;">
                <h3 style="font-size: 0.875rem; font-weight: bold; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">What You Learned</h3>
                <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    ${this.render.learnings && this.render.learnings.length > 0 ?
                        this.render.learnings.map(learning => `
                            <div style="background: white; border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 0.75rem;">
                                <div style="display: flex; align-items: flex-start; gap: 0.5rem;">
                                    <span style="color: #f59e0b;">🎓</span>
                                    <div>
                                        <h4 style="font-weight: bold; color: #334155; font-size: 0.875rem;">${learning.title}</h4>
                                        <p style="color: #475569; font-size: 0.875rem; margin-top: 0.25rem;">${learning.text}</p>
                                    </div>
                                </div>
                            </div>
                        `).join('') :
                        '<p style="color: #64748b; font-size: 0.875rem; font-style: italic;">Great work completing this clue!</p>'
                    }
                </div>
            </div>

            <!-- NEXT BUTTON -->
            <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 0 0 0.75rem 0.75rem; padding: 1rem; display: flex; align-items: center; justify-content: space-between;">
                <p style="color: #15803d; font-weight: 500;">Ready for the next clue?</p>
                <button data-action="complete" style="padding: 0.5rem 1.5rem; background: #16a34a; color: white; font-weight: bold; border-radius: 0.5rem; border: none; cursor: pointer;">
                    Apply to Grid
                </button>
            </div>
        `;

        this.container.innerHTML = html;
        this.attachEventListeners();
    }

    attachEventListeners() {
        // Hint button listener
        const hintBtn = this.container.querySelector('.hint-button');
        if (hintBtn) {
            hintBtn.addEventListener('click', () => {
                this.hintVisible = !this.hintVisible;
                this.renderUI();
            });
        }

        // Solve step button listener
        const solveStepBtn = this.container.querySelector('.solve-step-button');
        if (solveStepBtn) {
            solveStepBtn.addEventListener('click', () => {
                this.handleSolveStep();
            });
        }

        // Solve button (give up and reveal full answer)
        const solveBtn = this.container.querySelector('.solve-button');
        if (solveBtn) {
            solveBtn.addEventListener('click', () => {
                this.handleSolve();
            });
        }

        // Word tap listeners
        this.container.querySelectorAll('[data-word-index]').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.dataset.wordIndex, 10);
                this.handleWordTap(index);
            });
        });

        // Multiple choice option listeners
        this.container.querySelectorAll('[data-option-index]').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.dataset.optionIndex, 10);
                this.handleSubmit(index);
            });
        });

        // Action button listeners
        this.container.querySelectorAll('[data-action]').forEach(el => {
            el.addEventListener('click', () => {
                const action = el.dataset.action;
                if (action === 'submit') {
                    this.handleSubmit();
                } else if (action === 'continue') {
                    this.submitContinue();
                } else if (action === 'complete') {
                    this.onComplete?.();
                }
            });
        });

        // Text input listener (if present)
        const textInput = this.container.querySelector('#trainer-text-input');
        if (textInput) {
            // Set focus on the input
            textInput.focus();

            textInput.addEventListener('input', (e) => {
                this.textInput = e.target.value.toUpperCase();
                // Update the Check button state without full re-render
                const checkBtn = this.container.querySelector('[data-action="submit"]');
                if (checkBtn) {
                    const canSubmit = this.canSubmit();
                    checkBtn.disabled = !canSubmit;
                    checkBtn.style.background = canSubmit ? '#2563eb' : '#e5e7eb';
                    checkBtn.style.color = canSubmit ? 'white' : '#9ca3af';
                    checkBtn.style.cursor = canSubmit ? 'pointer' : 'not-allowed';
                }
            });

            textInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && this.canSubmit()) {
                    e.preventDefault();
                    this.handleSubmit();
                }
            });
        }

        // Answer box input listeners (for interactive answer entry)
        const answerInputs = this.container.querySelectorAll('.answer-box-input');
        console.log('[Trainer] Found answer inputs:', answerInputs.length);

        answerInputs.forEach(input => {
            // Handle input (letter typed)
            input.addEventListener('input', (e) => {
                const pos = parseInt(e.target.dataset.position, 10);
                const letter = e.target.value.toUpperCase().slice(-1); // Take last char if multiple
                console.log('[Trainer] Input at pos', pos, ':', letter, 'raw value:', e.target.value);
                e.target.value = letter;
                this.userAnswer[pos] = letter;

                // Auto-advance to next empty box
                if (letter) {
                    this.focusNextEmptyBox(pos);
                }

                // Check if answer is complete and correct
                this.checkAnswerComplete();
            });

            // Handle keyboard navigation
            input.addEventListener('keydown', (e) => {
                const pos = parseInt(e.target.dataset.position, 10);

                if (e.key === 'Backspace' && !e.target.value) {
                    // Move to previous editable box on backspace when empty
                    e.preventDefault();
                    this.focusPreviousEditableBox(pos);
                } else if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    this.focusPreviousEditableBox(pos);
                } else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    this.focusNextEditableBox(pos);
                } else if (e.key === 'Tab' && !e.shiftKey) {
                    e.preventDefault();
                    this.focusNextEditableBox(pos);
                }
            });

            // Visual feedback on focus
            input.addEventListener('focus', () => {
                input.style.borderColor = '#2563eb';
                input.style.boxShadow = '0 0 0 2px rgba(37, 99, 235, 0.2)';
            });

            input.addEventListener('blur', () => {
                input.style.borderColor = '#d1d5db';
                input.style.boxShadow = 'none';
            });
        });

        // Auto-focus first empty answer box
        const firstEmptyBox = this.container.querySelector('.answer-box-input:not([value])') ||
                              this.container.querySelector('.answer-box-input');
        if (firstEmptyBox) {
            firstEmptyBox.focus();
        }

        // Step text input listeners (crossword-style boxes for text mode)
        const stepTextInputs = this.container.querySelectorAll('.step-text-input');
        if (stepTextInputs.length > 0) {
            stepTextInputs.forEach(input => {
                // Handle input (letter typed)
                input.addEventListener('input', (e) => {
                    const pos = parseInt(e.target.dataset.position, 10);
                    const letter = e.target.value.toUpperCase().slice(-1);
                    e.target.value = letter;
                    this.stepTextInput[pos] = letter;

                    // Update textInput as combined string for submission
                    this.textInput = this.stepTextInput.join('');

                    // Auto-advance to next box
                    if (letter) {
                        this.focusNextStepTextBox(pos);
                    }

                    // Update Check button state
                    this.updateCheckButtonState();
                });

                // Handle keyboard navigation
                input.addEventListener('keydown', (e) => {
                    const pos = parseInt(e.target.dataset.position, 10);

                    if (e.key === 'Backspace' && !e.target.value) {
                        e.preventDefault();
                        this.focusPreviousStepTextBox(pos);
                    } else if (e.key === 'ArrowLeft') {
                        e.preventDefault();
                        this.focusPreviousStepTextBox(pos);
                    } else if (e.key === 'ArrowRight') {
                        e.preventDefault();
                        this.focusNextStepTextBox(pos);
                    } else if (e.key === 'Tab' && !e.shiftKey) {
                        e.preventDefault();
                        this.focusNextStepTextBox(pos);
                    } else if (e.key === 'Enter' && this.canSubmit()) {
                        e.preventDefault();
                        this.handleSubmit();
                    }
                });

                // Visual feedback on focus
                input.addEventListener('focus', () => {
                    input.style.borderColor = '#2563eb';
                    input.style.boxShadow = '0 0 0 2px rgba(37, 99, 235, 0.2)';
                });

                input.addEventListener('blur', () => {
                    input.style.borderColor = '#d1d5db';
                    input.style.boxShadow = 'none';
                });
            });

            // Auto-focus first step text input
            const firstStepInput = this.container.querySelector('.step-text-input');
            if (firstStepInput) {
                firstStepInput.focus();
            }
        }
    }

    // Navigation helpers for step text input boxes
    focusNextStepTextBox(currentPos) {
        const nextInput = this.container.querySelector(`.step-text-input[data-position="${currentPos + 1}"]`);
        if (nextInput) {
            nextInput.focus();
        }
    }

    focusPreviousStepTextBox(currentPos) {
        if (currentPos > 0) {
            const prevInput = this.container.querySelector(`.step-text-input[data-position="${currentPos - 1}"]`);
            if (prevInput) {
                prevInput.focus();
                prevInput.select();
            }
        }
    }

    updateCheckButtonState() {
        const checkBtn = this.container.querySelector('[data-action="submit"]');
        if (checkBtn) {
            const canSubmit = this.canSubmit();
            checkBtn.disabled = !canSubmit;
            checkBtn.style.background = canSubmit ? '#2563eb' : '#e5e7eb';
            checkBtn.style.color = canSubmit ? 'white' : '#9ca3af';
            checkBtn.style.cursor = canSubmit ? 'pointer' : 'not-allowed';
        }
    }

    // Navigation helpers for answer boxes
    focusNextEmptyBox(currentPos) {
        const answer = this.render?.answer || this.answer || '';
        const answerLength = answer.length;
        for (let i = currentPos + 1; i < answerLength; i++) {
            const crossLetter = this.crossLetters?.find(cl => cl.position === i);
            if (!crossLetter?.letter && !this.userAnswer[i]) {
                const nextInput = this.container.querySelector(`.answer-box-input[data-position="${i}"]`);
                if (nextInput) {
                    nextInput.focus();
                    return;
                }
            }
        }
        // No empty box found, focus next editable
        this.focusNextEditableBox(currentPos);
    }

    focusNextEditableBox(currentPos) {
        const answer = this.render?.answer || this.answer || '';
        const answerLength = answer.length;
        for (let i = currentPos + 1; i < answerLength; i++) {
            const crossLetter = this.crossLetters?.find(cl => cl.position === i);
            if (!crossLetter?.letter) {
                const nextInput = this.container.querySelector(`.answer-box-input[data-position="${i}"]`);
                if (nextInput) {
                    nextInput.focus();
                    nextInput.select();
                    return;
                }
            }
        }
    }

    focusPreviousEditableBox(currentPos) {
        for (let i = currentPos - 1; i >= 0; i--) {
            const crossLetter = this.crossLetters?.find(cl => cl.position === i);
            if (!crossLetter?.letter) {
                const prevInput = this.container.querySelector(`.answer-box-input[data-position="${i}"]`);
                if (prevInput) {
                    prevInput.focus();
                    prevInput.select();
                    return;
                }
            }
        }
    }

    // Answer validation
    checkAnswerComplete() {
        const rawAnswer = (this.render?.answer || this.answer || '').toUpperCase();
        // Strip spaces from answer - boxes don't include spaces
        const answer = rawAnswer.replace(/\s/g, '');
        const answerLength = answer.length;

        // Build the complete user answer including cross letters
        let userFullAnswer = '';
        for (let i = 0; i < answerLength; i++) {
            const crossLetter = this.crossLetters?.find(cl => cl.position === i);
            if (crossLetter?.letter) {
                userFullAnswer += crossLetter.letter.toUpperCase();
            } else {
                userFullAnswer += (this.userAnswer[i] || '').toUpperCase();
            }
        }

        // Check if all boxes are filled (no empty strings)
        if (userFullAnswer.length !== answerLength) {
            return; // Not complete yet
        }

        // Check for any unfilled positions
        for (let i = 0; i < answerLength; i++) {
            if (!userFullAnswer[i] || userFullAnswer[i] === ' ') {
                return; // Still has empty boxes
            }
        }

        // Check if correct
        if (userFullAnswer === answer) {
            this.onAnswerCorrect();
        } else {
            this.onAnswerIncorrect(userFullAnswer);
        }
    }

    onAnswerCorrect() {
        // Lock the answer boxes (they'll be re-rendered as divs)
        this.answerLocked = true;

        // Visual feedback - green borders on existing inputs before re-render
        this.container.querySelectorAll('.answer-box-input').forEach(input => {
            input.style.borderColor = '#22c55e';
            input.style.background = '#f0fdf4';
            input.disabled = true;
        });

        // Notify server that answer is known (forms hypothesis)
        this.submitAnswerHypothesis();
    }

    onAnswerIncorrect(userAnswer) {
        // Brief red flash feedback, then reset
        this.container.querySelectorAll('.answer-box-input').forEach(input => {
            input.style.borderColor = '#ef4444';
            input.style.background = '#fef2f2';
        });

        // Reset after brief delay
        setTimeout(() => {
            this.container.querySelectorAll('.answer-box-input').forEach(input => {
                input.style.borderColor = '#d1d5db';
                input.style.background = 'white';
            });
        }, 500);
    }

    async submitAnswerHypothesis() {
        try {
            const response = await fetch('/trainer/hypothesis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clue_id: this.clueId,
                    answer: this.render?.answer || this.answer
                })
            });

            const data = await response.json();

            if (data.success) {
                // Server acknowledged hypothesis - update render state
                this.render = data.render || data;
                this.render.answerKnown = true;

                // Show feedback message
                this.feedback = {
                    correct: true,
                    message: "Correct! Now let's verify with the wordplay..."
                };

                // Re-render to show verification steps
                this.renderUI();
            }
        } catch (e) {
            console.error('Failed to submit hypothesis:', e);
        }
    }
}

// Export for use
window.TemplateTrainer = TemplateTrainer;
