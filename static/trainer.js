/**
 * TemplateTrainer - Stateless training UI
 *
 * Renders server state. No client-side state beyond what the server sends.
 * Server drives all transitions via the render object.
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

        this.render = null;
        this.loading = true;
        this.feedback = null; // {type: 'success'|'error', message}
    }

    // =========================================================================
    // API CALLS
    // =========================================================================

    async submitInput(value) {
        try {
            const resp = await fetch('/trainer/input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId, value })
            });
            const data = await resp.json();

            if (data.correct) {
                this.feedback = { type: 'success', message: 'Correct!' };
            } else {
                this.feedback = { type: 'error', message: 'Not quite — try again.' };
            }

            if (data.render) {
                this.render = data.render;
            }
            this.renderUI();

            // Clear feedback after delay
            setTimeout(() => { this.feedback = null; this.renderUI(); }, 1500);
        } catch (err) {
            console.error('submitInput error:', err);
        }
    }

    async updateUIState(action, data = {}) {
        try {
            const resp = await fetch('/trainer/ui-state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId, action, ...data })
            });
            const result = await resp.json();
            this.render = result;
            this.renderUI();
        } catch (err) {
            console.error('updateUIState error:', err);
        }
    }

    async revealAnswer() {
        try {
            const resp = await fetch('/trainer/reveal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId })
            });
            const data = await resp.json();
            this.render = data;
            this.renderUI();
        } catch (err) {
            console.error('revealAnswer error:', err);
        }
    }

    async checkAnswer(answer) {
        try {
            const resp = await fetch('/trainer/check-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clue_id: this.clueId, answer })
            });
            const data = await resp.json();

            if (data.correct) {
                this.feedback = { type: 'success', message: 'Correct!' };
            } else {
                this.feedback = { type: 'error', message: 'Not the right answer.' };
            }

            if (data.render) {
                this.render = data.render;
            }
            this.renderUI();
            setTimeout(() => { this.feedback = null; this.renderUI(); }, 1500);
        } catch (err) {
            console.error('checkAnswer error:', err);
        }
    }

    // =========================================================================
    // MAIN RENDER
    // =========================================================================

    renderUI() {
        if (this.loading || !this.render) {
            this.container.innerHTML = '<div style="padding: 2rem; text-align: center; color: #666;">Loading...</div>';
            return;
        }

        const r = this.render;

        if (r.complete) {
            this.renderComplete(r);
        } else {
            this.renderTraining(r);
        }

        this.attachEventListeners();
    }

    // =========================================================================
    // TRAINING VIEW
    // =========================================================================

    renderTraining(r) {
        const step = r.currentStep;

        let html = '';

        // Answer boxes
        html += this.renderAnswerBoxes(r);

        // Feedback banner
        if (this.feedback) {
            const bgColor = this.feedback.type === 'success' ? '#16a34a' : '#dc2626';
            html += `<div style="padding: 0.5rem 1rem; background: ${bgColor}; color: white; text-align: center; border-radius: 0.375rem; margin: 0.5rem 1rem; font-weight: 500;">${this.feedback.message}</div>`;
        }

        // Step menu
        html += this.renderStepMenu(r);

        this.container.innerHTML = html;
    }

    // =========================================================================
    // STEP MENU
    // =========================================================================

    renderStepMenu(r) {
        const steps = r.steps || [];
        const currentStep = r.currentStep;

        let html = '<div style="padding: 0.5rem 1rem;">';
        html += '<div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.5rem;">Steps to solve:</div>';

        for (const step of steps) {
            const isActive = currentStep && step.index === currentStep.index;
            const isCompleted = step.status === 'completed';

            // Step header
            const icon = isCompleted ? '<span style="color: #16a34a;">&#10003;</span>'
                       : isActive ? '<span style="color: #3b82f6;">&#9679;</span>'
                       : '<span style="color: #94a3b8;">&#9675;</span>';

            const titleColor = isCompleted ? '#16a34a' : isActive ? '#1e293b' : '#64748b';
            const isExpanded = isActive && r.stepExpanded;
            const cursor = isActive ? 'pointer' : isCompleted ? 'default' : 'default';
            const chevron = isActive ? (isExpanded ? '&#9660;' : '&#9654;') : '';

            html += `<div style="margin-bottom: 0.25rem;">`;
            html += `<div class="${isActive ? 'step-header-active' : 'step-header'}" data-step-index="${step.index}" style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; cursor: ${cursor}; border-radius: 0.375rem; ${isActive ? 'background: #f0f9ff;' : ''}">`;
            html += `${icon} <span style="font-size: 0.9rem; color: ${titleColor}; font-weight: ${isActive ? '600' : '400'};">${step.index + 1}. ${step.title}</span>`;
            if (chevron) html += `<span style="font-size: 0.6rem; color: #94a3b8; margin-left: auto;">${chevron}</span>`;
            html += `</div>`;

            // Expanded content for active step (only when expanded)
            if (isExpanded && currentStep) {
                html += this.renderActiveStep(r, currentStep);
            }

            // Completion text for completed steps
            if (isCompleted && step.completionText) {
                html += `<div style="margin-left: 1.75rem; padding: 0.75rem; background: #f0fdf4; border-radius: 0.375rem; border-left: 3px solid #16a34a; margin-bottom: 0.5rem;">`;
                html += `<div style="font-size: 0.85rem; color: #166534;">${step.completionText}</div>`;
                html += `</div>`;
            }

            html += `</div>`;
        }

        html += '</div>';
        return html;
    }

    // =========================================================================
    // ACTIVE STEP
    // =========================================================================

    renderActiveStep(r, step) {
        let html = '<div style="margin-left: 1.75rem; padding: 0.75rem; background: #f8fafc; border-radius: 0.375rem; border: 1px solid #e2e8f0; margin-bottom: 0.5rem;">';

        // Word chips for tap_words
        if (step.inputMode === 'tap_words') {
            html += '<div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">';
            for (let i = 0; i < r.words.length; i++) {
                const word = r.words[i];
                const highlight = this.getWordHighlight(r, i);
                const isSelected = (r.selectedIndices || []).includes(i);

                let bg = '#e2e8f0';
                let color = '#1e293b';
                let border = '2px solid transparent';

                if (highlight) {
                    bg = highlight === 'GREEN' ? '#bbf7d0' : highlight === 'ORANGE' ? '#fed7aa' : highlight === 'BLUE' ? '#bfdbfe' : '#e2e8f0';
                    color = highlight === 'GREEN' ? '#166534' : '#1e293b';
                } else if (isSelected) {
                    bg = '#bfdbfe';
                    border = '2px solid #3b82f6';
                }

                html += `<span class="word-chip" data-word-index="${i}" style="padding: 0.375rem 0.75rem; border-radius: 0.375rem; background: ${bg}; color: ${color}; border: ${border}; cursor: pointer; font-size: 1rem; user-select: none; transition: background 0.15s;">${word}</span>`;
            }
            html += '</div>';
        }

        // Prompt
        html += `<div style="font-size: 0.85rem; color: #475569; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">`;
        html += `<span>${step.prompt}</span>`;
        // Hint lightbulb
        if (step.hint) {
            html += `<span class="hint-toggle" style="cursor: pointer; font-size: 1.25rem; opacity: ${step.hintVisible ? '1' : '0.5'};" title="Show hint">&#128161;</span>`;
        }
        html += `</div>`;

        // Intro text
        if (step.intro && !step.hintVisible) {
            html += `<div style="font-size: 0.8rem; color: #64748b; line-height: 1.5; white-space: pre-line;">${step.intro}</div>`;
        }

        // Hint text (revealed)
        if (step.hintVisible && step.hint) {
            html += `<div style="font-size: 0.85rem; color: #1e40af; background: #eff6ff; padding: 0.5rem 0.75rem; border-radius: 0.375rem; margin-top: 0.25rem;">`;
            html += `&#128161; ${step.hint}`;
            html += `</div>`;
        }

        // Submit button for tap_words when words are selected
        if (step.inputMode === 'tap_words' && (r.selectedIndices || []).length > 0) {
            html += `<div style="margin-top: 0.75rem;">`;
            html += `<button class="submit-btn" style="padding: 0.5rem 1.5rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer; font-size: 0.9rem;">Check</button>`;
            html += `</div>`;
        }

        html += '</div>';
        return html;
    }

    // =========================================================================
    // ANSWER BOXES
    // =========================================================================

    renderAnswerBoxes(r) {
        const enumeration = r.enumeration || this.enumeration || '';
        const parts = enumeration.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
        const userAnswer = r.userAnswer || [];
        const locked = r.answerLocked;

        let html = '<div style="padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0;">';
        html += '<div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">';

        let letterIdx = 0;
        for (let p = 0; p < parts.length; p++) {
            if (p > 0) {
                // Word gap
                html += '<div style="width: 0.5rem;"></div>';
            }
            for (let c = 0; c < parts[p]; c++) {
                const letter = userAnswer[letterIdx] || '';
                const crossLetter = this.getCrossLetter(letterIdx);
                const displayLetter = letter || crossLetter || '';

                html += `<input type="text" class="answer-box" data-letter-index="${letterIdx}" `
                    + `value="${displayLetter}" `
                    + `maxlength="1" `
                    + `${locked ? 'disabled' : ''} `
                    + `style="width: 2rem; height: 2rem; text-align: center; border: 1px solid ${locked ? '#16a34a' : '#cbd5e1'}; border-radius: 0.25rem; font-size: 1rem; font-weight: 600; text-transform: uppercase; ${locked ? 'background: #f0fdf4; color: #16a34a;' : ''}" />`;
                letterIdx++;
            }
        }

        // Check / Reveal buttons
        if (!locked) {
            html += `<button class="check-answer-btn" style="margin-left: 0.5rem; padding: 0.25rem 0.75rem; background: #3b82f6; color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-size: 0.8rem;">Check</button>`;
            html += `<button class="reveal-btn" style="padding: 0.25rem 0.75rem; background: #ef4444; color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-size: 0.8rem;">Reveal</button>`;
        }

        html += '</div>';
        html += '</div>';
        return html;
    }

    // =========================================================================
    // COMPLETION VIEW
    // =========================================================================

    renderComplete(r) {
        let html = '';

        // Green header with answer
        html += `<div style="background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); padding: 1.5rem; text-align: center; color: white;">`;
        html += `<div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.25rem;">Answer</div>`;
        html += `<div style="font-size: 1.75rem; font-weight: 700; font-family: monospace; letter-spacing: 0.15em;">${r.answer}</div>`;
        html += `</div>`;

        // Steps summary
        html += '<div style="padding: 1rem;">';
        for (const step of (r.steps || [])) {
            if (step.completionText) {
                html += `<div style="padding: 0.5rem 0.75rem; background: #f0fdf4; border-radius: 0.375rem; border-left: 3px solid #16a34a; margin-bottom: 0.5rem;">`;
                html += `<div style="font-size: 0.85rem; color: #166534;"><strong>${step.title}:</strong> ${step.completionText}</div>`;
                html += `</div>`;
            }
        }
        html += '</div>';

        // Update Grid button
        html += `<div style="padding: 1rem; text-align: center;">`;
        html += `<button class="complete-btn" style="padding: 0.75rem 2rem; background: #16a34a; color: white; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 1rem; font-weight: 600;">Update Grid</button>`;
        html += `</div>`;

        this.container.innerHTML = html;
        this.attachEventListeners();
    }

    // =========================================================================
    // EVENT LISTENERS
    // =========================================================================

    attachEventListeners() {
        // Active step header click (expand/collapse)
        this.container.querySelectorAll('.step-header-active').forEach(el => {
            el.addEventListener('click', () => {
                this.updateUIState('expand_step');
            });
        });

        // Word chip clicks
        this.container.querySelectorAll('.word-chip').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.dataset.wordIndex, 10);
                this.updateUIState('select_word', { index });
            });
        });

        // Hint toggle
        this.container.querySelectorAll('.hint-toggle').forEach(el => {
            el.addEventListener('click', () => {
                this.updateUIState('toggle_hint');
            });
        });

        // Submit button (for tap_words)
        this.container.querySelectorAll('.submit-btn').forEach(el => {
            el.addEventListener('click', () => {
                const selected = this.render?.selectedIndices || [];
                if (selected.length > 0) {
                    this.submitInput(selected);
                }
            });
        });

        // Answer box typing
        this.container.querySelectorAll('.answer-box').forEach(el => {
            el.addEventListener('input', (e) => {
                const idx = parseInt(el.dataset.letterIndex, 10);
                const letter = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
                e.target.value = letter;

                // Update server silently
                const letters = [];
                this.container.querySelectorAll('.answer-box').forEach(box => {
                    letters.push(box.value || '');
                });
                this.updateUIState('type_answer', { letters });

                // Auto-advance to next box
                if (letter && el.nextElementSibling?.classList?.contains('answer-box')) {
                    el.nextElementSibling.focus();
                }
            });

            el.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !el.value) {
                    // Move to previous box on backspace when empty
                    const prev = el.previousElementSibling;
                    if (prev?.classList?.contains('answer-box')) {
                        prev.focus();
                        prev.select();
                    }
                }
            });
        });

        // Check answer button
        this.container.querySelectorAll('.check-answer-btn').forEach(el => {
            el.addEventListener('click', () => {
                const letters = [];
                this.container.querySelectorAll('.answer-box').forEach(box => {
                    letters.push(box.value || '');
                });
                this.checkAnswer(letters.join(''));
            });
        });

        // Reveal button
        this.container.querySelectorAll('.reveal-btn').forEach(el => {
            el.addEventListener('click', () => {
                this.revealAnswer();
            });
        });

        // Complete button
        this.container.querySelectorAll('.complete-btn').forEach(el => {
            el.addEventListener('click', () => {
                if (this.onComplete) this.onComplete();
            });
        });
    }

    // =========================================================================
    // HELPERS
    // =========================================================================

    getWordHighlight(r, wordIndex) {
        const highlights = r.highlights || [];
        for (const h of highlights) {
            if (h.indices && h.indices.includes(wordIndex)) {
                return h.color;
            }
        }
        return null;
    }

    getCrossLetter(letterIndex) {
        if (!this.crossLetters) return '';
        const entry = this.crossLetters.find(cl => cl.position === letterIndex);
        return entry ? entry.letter : '';
    }
}
