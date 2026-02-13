/**
 * TemplateTrainer - Stateless training UI
 *
 * Renders server state. No client-side state beyond what the server sends.
 * Server drives all transitions via the render object.
 *
 * Design: Inspired by Duolingo/Brilliant — focus on ONE interaction at a time.
 * Completed steps collapse to a single line. Active step gets full attention.
 */
class TemplateTrainer {
    constructor(container, options) {
        this.container = container;
        this.clueId = options.clueId;
        this.crossLetters = options.crossLetters || [];
        this.onComplete = options.onComplete;

        this.render = null;
        this.loading = true;
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

            if (data.render) {
                this.render = data.render;
            }
            this.renderUI();
            this.showToast(data.correct ? 'success' : 'error', data.message);
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
            // Silent sync for typing — don't re-render (preserves focus/cursor)
            // Only re-render if server locked the answer
            if (action === 'type_answer' && !result.answerLocked) return;
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

            if (data.render) {
                this.render = data.render;
            }
            this.renderUI();
            this.showToast(data.correct ? 'success' : 'error', data.message);
        } catch (err) {
            console.error('checkAnswer error:', err);
        }
    }

    // =========================================================================
    // TOAST FEEDBACK (overlay, no layout shift)
    // =========================================================================

    showToast(type, message) {
        // Remove any existing toast
        const old = this.container.querySelector('.trainer-toast');
        if (old) old.remove();

        const toast = document.createElement('div');
        toast.className = 'trainer-toast';
        const isSuccess = type === 'success';
        toast.textContent = message;
        Object.assign(toast.style, {
            position: 'absolute',
            top: '0.5rem',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '0.3rem 1rem',
            borderRadius: '1rem',
            fontSize: '0.8rem',
            fontWeight: '600',
            color: isSuccess ? '#16a34a' : '#dc2626',
            background: isSuccess ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${isSuccess ? '#bbf7d0' : '#fecaca'}`,
            opacity: '0',
            transition: 'opacity 0.2s ease',
            zIndex: '10',
            pointerEvents: 'none'
        });

        // Container needs relative positioning for the overlay
        this.container.style.position = 'relative';
        this.container.appendChild(toast);

        // Fade in
        requestAnimationFrame(() => { toast.style.opacity = '1'; });

        // Fade out and remove
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 200);
        }, 1300);
    }

    // =========================================================================
    // MAIN RENDER
    // =========================================================================

    renderUI() {
        if (this.loading || !this.render) {
            this.container.innerHTML = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">Loading...</div>';
            return;
        }

        const r = this.render;

        this.renderTraining(r);
        this.attachEventListeners();
    }

    // =========================================================================
    // TRAINING VIEW
    // =========================================================================

    renderTraining(r) {
        let html = '';

        // Progress bar
        html += this.renderProgressBar(r);

        // Answer boxes + buttons
        html += this.renderAnswerSection(r);

        // Step list
        html += this.renderStepList(r);

        // Update Grid button when all done
        if (r.complete) {
            html += `<div style="padding: 0.75rem 1.25rem 1.25rem; text-align: center;">`;
            html += `<button class="complete-btn" style="padding: 0.6rem 2rem; background: #16a34a; color: white; border: none; border-radius: 2rem; cursor: pointer; font-size: 0.9rem; font-weight: 600;">Update Grid</button>`;
            html += `</div>`;
        }

        this.container.innerHTML = html;
    }

    // =========================================================================
    // PROGRESS BAR
    // =========================================================================

    renderProgressBar(r) {
        const steps = r.steps || [];
        const completed = steps.filter(s => s.status === 'completed').length;
        const pct = steps.length > 0 ? (completed / steps.length) * 100 : 0;

        return `<div style="height: 4px; background: #e2e8f0;"><div style="height: 100%; width: ${pct}%; background: #22c55e; transition: width 0.4s ease;"></div></div>`;
    }

    // =========================================================================
    // ANSWER SECTION
    // =========================================================================

    renderAnswerSection(r) {
        // Server computes answer box groups — client just renders
        const parts = r.answerGroups || [];
        const userAnswer = r.userAnswer || [];
        const locked = r.answerLocked;

        let html = '<div style="padding: 1rem 1.25rem 0.75rem;">';

        // Letter boxes — centered
        html += '<div style="display: flex; justify-content: center; gap: 4px; flex-wrap: wrap;">';
        let letterIdx = 0;
        for (let p = 0; p < parts.length; p++) {
            if (p > 0) html += '<div style="width: 10px;"></div>';
            for (let c = 0; c < parts[p]; c++) {
                const letter = userAnswer[letterIdx] || '';
                const crossLetter = this.getCrossLetter(letterIdx);
                const displayLetter = letter || crossLetter || '';
                const borderColor = locked ? '#16a34a' : displayLetter ? '#475569' : '#cbd5e1';
                const bg = locked ? '#f0fdf4' : 'white';
                const textColor = locked ? '#16a34a' : '#1e293b';

                html += `<input type="text" class="answer-box" data-letter-index="${letterIdx}" `
                    + `value="${displayLetter}" maxlength="1" ${locked ? 'disabled' : ''} `
                    + `style="width: 2.4rem; height: 2.6rem; text-align: center; border: none; border-bottom: 3px solid ${borderColor}; border-radius: 0; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; background: ${bg}; color: ${textColor}; outline: none;" />`;
                letterIdx++;
            }
        }
        html += '</div>';

        // Buttons row — below boxes
        if (!locked) {
            html += '<div style="display: flex; justify-content: center; gap: 0.75rem; margin-top: 0.75rem;">';
            html += `<button class="check-answer-btn" style="padding: 0.35rem 1.25rem; background: #3b82f6; color: white; border: none; border-radius: 1rem; cursor: pointer; font-size: 0.8rem; font-weight: 500;">Check</button>`;
            html += `<button class="reveal-btn" style="padding: 0.35rem 1.25rem; background: none; color: #94a3b8; border: 1px solid #cbd5e1; border-radius: 1rem; cursor: pointer; font-size: 0.8rem; font-weight: 500;">Reveal</button>`;
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    // =========================================================================
    // STEP LIST
    // =========================================================================

    renderStepList(r) {
        const steps = r.steps || [];
        const currentStep = r.currentStep;

        let html = '<div style="padding: 0.25rem 1.25rem 1rem;">';

        for (const step of steps) {
            const isActive = currentStep && step.index === currentStep.index;
            const isCompleted = step.status === 'completed';
            const isExpanded = isActive && r.stepExpanded;

            html += this.renderStepRow(step, isActive, isCompleted, isExpanded);

            // Expanded content
            if (isExpanded && currentStep) {
                html += this.renderActiveStep(r, currentStep);
            }
        }

        html += '</div>';
        return html;
    }

    renderStepRow(step, isActive, isCompleted, isExpanded) {
        // Completed: small muted checkmark + title, single line
        if (isCompleted) {
            const titleHtml = step.title.replace(/\n/g, '<br>');
            return `<div style="display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.4rem 0;">
                <svg style="flex-shrink: 0; margin-top: 2px;" width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#22c55e" stroke-width="1.5" fill="#f0fdf4"/><path d="M5 8l2 2 4-4" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                <span style="font-size: 0.85rem; color: #475569;">${titleHtml}</span>
            </div>`;
        }

        // Active: bold, clickable
        if (isActive) {
            const chevron = isExpanded
                ? '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 5l3 3 3-3" stroke="#94a3b8" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
                : '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M5 3l3 3-3 3" stroke="#94a3b8" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>';

            return `<div class="step-header-active" data-step-index="${step.index}" style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; cursor: pointer;">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" fill="#3b82f6"/><circle cx="8" cy="8" r="3" fill="white"/></svg>
                <span style="font-size: 0.9rem; color: #1e293b; font-weight: 600; flex: 1;">${step.title}</span>
                ${chevron}
            </div>`;
        }

        // Pending: muted
        return `<div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0; opacity: 0.35;">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="#94a3b8" stroke-width="1.5"/></svg>
            <span style="font-size: 0.8rem; color: #94a3b8;">${step.title}</span>
        </div>`;
    }

    // =========================================================================
    // ACTIVE STEP CONTENT
    // =========================================================================

    renderActiveStep(r, step) {
        if (step.inputMode === 'assembly') {
            return this.renderAssemblyContent(r, step);
        }

        let html = '<div style="padding: 0.5rem 0 0.75rem 1.75rem;">';

        // Word chips
        if (step.inputMode === 'tap_words') {
            html += '<div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.75rem;">';
            for (let i = 0; i < r.words.length; i++) {
                const word = r.words[i];
                const highlight = this.getWordHighlight(r, i);
                const isSelected = (r.selectedIndices || []).includes(i);

                let bg, color, border;
                if (highlight) {
                    bg = highlight === 'GREEN' ? '#dcfce7' : highlight === 'ORANGE' ? '#fef3c7' : highlight === 'BLUE' ? '#dbeafe' : '#f1f5f9';
                    color = highlight === 'GREEN' ? '#15803d' : '#44403c';
                    border = 'none';
                } else if (isSelected) {
                    bg = '#dbeafe';
                    color = '#1e40af';
                    border = 'none';
                } else {
                    bg = '#f1f5f9';
                    color = '#334155';
                    border = 'none';
                }

                html += `<span class="word-chip" data-word-index="${i}" style="padding: 0.4rem 0.75rem; border-radius: 2rem; background: ${bg}; color: ${color}; border: ${border}; cursor: pointer; font-size: 0.9rem; user-select: none; transition: background 0.15s; ${isSelected ? 'box-shadow: 0 0 0 2px #3b82f6;' : ''}">${word}</span>`;
            }
            html += '</div>';
        }

        // Multiple choice options
        if (step.inputMode === 'multiple_choice' && step.options) {
            html += '<div style="display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 0.75rem;">';
            for (const option of step.options) {
                html += `<button class="mc-option" data-value="${option}" style="padding: 0.5rem 1rem; background: #f1f5f9; color: #334155; border: 1px solid #e2e8f0; border-radius: 0.5rem; cursor: pointer; font-size: 0.85rem; text-align: left; transition: background 0.15s;">${option}</button>`;
            }
            html += '</div>';
        }

        // Prompt + hint
        html += `<div style="display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.25rem;">`;
        html += `<span style="font-size: 0.8rem; color: #64748b; flex: 1; line-height: 1.5;">${step.prompt}</span>`;
        if (step.hint) {
            html += `<span class="hint-toggle" style="cursor: pointer; width: 20px; height: 20px; border-radius: 50%; background: ${step.hintVisible ? '#3b82f6' : '#e2e8f0'}; color: ${step.hintVisible ? 'white' : '#94a3b8'}; font-size: 0.7rem; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;" title="Hint">?</span>`;
        }
        if (step.lookup) {
            html += `<a href="${step.lookup.url}" target="_blank" rel="noopener" style="width: 20px; height: 20px; border-radius: 50%; background: #e2e8f0; color: #64748b; font-size: 0.7rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0; text-decoration: none;" title="Look up '${step.lookup.word}' in Merriam-Webster">📖</a>`;
        }
        html += `</div>`;

        // Intro (when hint not shown)
        if (step.intro && !step.hintVisible) {
            html += `<div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.5; margin-top: 0.25rem;">${step.intro}</div>`;
        }

        // Hint revealed
        if (step.hintVisible && step.hint) {
            html += `<div style="font-size: 0.8rem; color: #1e40af; margin-top: 0.5rem; padding-left: 0.75rem; border-left: 2px solid #93c5fd; line-height: 1.5;">${step.hint}</div>`;
        }

        // Submit button
        if (step.inputMode === 'tap_words' && (r.selectedIndices || []).length > 0) {
            html += `<div style="margin-top: 0.75rem;">`;
            html += `<button class="submit-btn" style="padding: 0.4rem 1.5rem; background: #3b82f6; color: white; border: none; border-radius: 1rem; cursor: pointer; font-size: 0.8rem; font-weight: 500;">Check</button>`;
            html += `</div>`;
        }

        html += '</div>';
        return html;
    }

    // =========================================================================
    // ASSEMBLY STEP
    // =========================================================================

    renderAssemblyContent(r, step) {
        const data = step.assemblyData;
        if (!data) {
            return '<div style="padding: 0.75rem; color: #dc2626;">Step data missing — please reload.</div>';
        }

        let html = '<div style="padding: 0.5rem 0 0.75rem 1.75rem;">';

        // Coaching context — server provides ready-to-render strings
        if (data.definitionLine) {
            html += `<div style="font-size: 0.85rem; font-weight: 600; color: #1e293b; margin-bottom: 0.5rem; line-height: 1.5;">${data.definitionLine}</div>`;
        }
        if (data.indicatorLine) {
            html += `<div style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.5rem; line-height: 1.5;">${data.indicatorLine}</div>`;
        }

        // Fail message — why the raw words don't work
        html += `<div style="font-size: 0.8rem; color: #b45309; margin-bottom: 1rem; font-style: italic; line-height: 1.5;">${data.failMessage}</div>`;

        // Transforms — all visible at once (active, completed, or locked)
        for (let i = 0; i < data.transforms.length; i++) {
            html += this.renderTransformInput(data.transforms[i], i);
        }

        // Combined result display — shows answer forming below transforms
        html += this.renderCombinedResult(data);

        // Assembly check (only when all transforms done but auto-skip didn't fire)
        if (data.phase === 'check') {
            html += this.renderAssemblyCheck(data);
        }

        html += '</div>';
        return html;
    }

    renderTransformInput(transform, index) {
        let html = '';
        const tIdx = transform.index !== undefined ? transform.index : index;

        if (transform.status === 'completed') {
            // Completed — compact single line with server-provided text
            html += `<div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; margin-bottom: 0.25rem;">`;
            html += `<svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#22c55e" stroke-width="1.5" fill="#f0fdf4"/><path d="M5 8l2 2 4-4" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            html += `<span style="font-size: 0.85rem; color: #1e293b; font-family: monospace; letter-spacing: 0.03em;">${transform.completedText || transform.result}</span>`;
            html += `</div>`;

        } else if (transform.status === 'active') {
            // Active — prompt and hint only (letter entry is in combined display below)
            html += `<div style="padding: 0.25rem 0; margin-bottom: 0.15rem;">`;

            // Prompt with hint
            html += `<div style="display: flex; align-items: flex-start; gap: 0.5rem;">`;
            html += `<span style="font-size: 0.8rem; font-weight: 600; color: #334155; flex: 1; line-height: 1.5;">${transform.prompt}</span>`;
            if (transform.hint) {
                html += `<span class="assembly-hint-toggle" data-transform-index="${tIdx}" style="cursor: pointer; width: 20px; height: 20px; border-radius: 50%; background: ${transform.hintVisible ? '#3b82f6' : '#e2e8f0'}; color: ${transform.hintVisible ? 'white' : '#94a3b8'}; font-size: 0.7rem; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;" title="Hint">?</span>`;
            }
            if (transform.lookup) {
                html += `<a href="${transform.lookup.url}" target="_blank" rel="noopener" style="width: 20px; height: 20px; border-radius: 50%; background: #e2e8f0; color: #64748b; font-size: 0.7rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0; text-decoration: none;" title="Look up '${transform.lookup.word}' in Merriam-Webster">📖</a>`;
            }
            html += `</div>`;

            // Hint
            if (transform.hintVisible && transform.hint) {
                html += `<div style="font-size: 0.8rem; color: #1e40af; margin-top: 0.25rem; padding-left: 0.75rem; border-left: 2px solid #93c5fd; line-height: 1.5;">${transform.hint}</div>`;
            }

            html += `</div>`;

        }

        return html;
    }

    renderCombinedResult(data) {
        const letters = data.completedLetters;
        if (!letters || !data.resultParts) return '';

        let html = '<div style="margin: 0.75rem 0; padding: 0.6rem 0; border-top: 1px solid #e2e8f0;">';

        // Build groups from positionMap: find contiguous runs belonging to each transform
        const posMap = data.positionMap || {};
        const groups = this.buildPositionGroups(letters, posMap);

        // Build reverse map: position → transform index (for editable inputs)
        const posToTransform = {};
        for (const [tIdx, positions] of Object.entries(posMap)) {
            for (const pos of positions) {
                posToTransform[pos] = parseInt(tIdx);
            }
        }

        // Find which transforms are completed vs active
        const completedTransforms = new Set();
        for (const t of data.transforms) {
            if (t.status === 'completed') completedTransforms.add(t.index);
        }

        html += '<div style="display: flex; gap: 3px; flex-wrap: wrap; align-items: center;">';
        for (let g = 0; g < groups.length; g++) {
            if (g > 0) html += '<div style="font-size: 1rem; font-weight: 700; color: #94a3b8; padding: 0 0.2rem;">+</div>';
            for (const pos of groups[g]) {
                const letter = letters[pos];
                const crossLetter = this.getCrossLetter(pos);
                const tIdx = posToTransform[pos];
                const isCompleted = completedTransforms.has(tIdx);
                const filled = letter !== null;
                const hasCross = !filled && crossLetter;
                const displayLetter = letter || crossLetter || '';

                if (filled || isCompleted) {
                    // Completed — green static display
                    html += `<div style="width: 2.2rem; height: 2.4rem; display: flex; align-items: center; justify-content: center; border-bottom: 3px solid #22c55e; background: #f0fdf4; font-size: 1.1rem; font-weight: 700; font-family: monospace; color: #15803d; letter-spacing: 0.05em;">${displayLetter}</div>`;
                } else {
                    // Active — editable input (cross letters shown as placeholder, overwritable)
                    html += `<input type="text" class="assembly-combined-letter" data-transform-index="${tIdx}" data-pos="${pos}" `
                        + `value="" placeholder="${crossLetter || ''}" maxlength="1" `
                        + `style="width: 2.2rem; height: 2.4rem; text-align: center; border: none; border-bottom: 3px solid #93c5fd; border-radius: 0; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; background: white; color: #1e293b; outline: none; font-family: monospace;" />`;
                }
            }
        }
        html += '</div>';

        // Check button
        html += '<div style="margin-top: 0.5rem;">';
        html += '<button class="assembly-combined-check" style="padding: 0.35rem 1.25rem; background: #3b82f6; color: white; border: none; border-radius: 1rem; cursor: pointer; font-size: 0.8rem; font-weight: 500;">Check</button>';
        html += '</div>';

        html += '</div>';
        return html;
    }

    buildPositionGroups(letters, posMap) {
        // Build a map: position → transform index
        const posToTransform = {};
        for (const [tIdx, positions] of Object.entries(posMap)) {
            for (const pos of positions) {
                posToTransform[pos] = parseInt(tIdx);
            }
        }

        // Walk positions in order, grouping contiguous runs with the same transform
        const groups = [];
        let currentGroup = [];
        let currentTransform = null;

        for (let pos = 0; pos < letters.length; pos++) {
            const t = posToTransform[pos];
            if (t !== currentTransform && currentGroup.length > 0) {
                groups.push(currentGroup);
                currentGroup = [];
            }
            currentGroup.push(pos);
            currentTransform = t;
        }
        if (currentGroup.length > 0) groups.push(currentGroup);

        return groups;
    }

    renderAssemblyCheck(data) {
        let html = '';

        html += `<div style="padding: 0.75rem 0;">`;
        html += `<div style="font-size: 0.8rem; color: #334155; margin-bottom: 0.5rem;">${data.checkPhasePrompt}</div>`;

        // Letter tiles
        html += `<div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">`;
        let letterIdx = 0;
        for (let p = 0; p < data.resultParts.length; p++) {
            if (p > 0) html += '<div style="width: 10px;"></div>';
            for (let c = 0; c < data.resultParts[p]; c++) {
                html += `<input type="text" class="assembly-result-letter" data-letter-pos="${letterIdx}" `
                    + `maxlength="1" `
                    + `style="width: 2.2rem; height: 2.4rem; text-align: center; border: none; border-bottom: 3px solid #c4b5fd; border-radius: 0; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; background: white; outline: none;" />`;
                letterIdx++;
            }
        }
        html += `<button class="assembly-check-btn" style="margin-left: 0.5rem; padding: 0.35rem 1rem; background: #8b5cf6; color: white; border: none; border-radius: 1rem; cursor: pointer; font-size: 0.8rem; font-weight: 500;">Check</button>`;
        html += `</div>`;

        html += `</div>`;
        return html;
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
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this.updateUIState('toggle_hint');
            });
        });

        // Assembly combined letter inputs (in the grouped result display)
        this.container.querySelectorAll('.assembly-combined-letter').forEach(el => {
            el.addEventListener('input', (e) => {
                const letter = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
                e.target.value = letter;

                if (letter) {
                    // Auto-advance to next input (skip + separators and non-inputs)
                    let next = el.nextElementSibling;
                    while (next && !next.classList?.contains('assembly-combined-letter')) {
                        next = next.nextElementSibling;
                    }
                    if (next) {
                        next.focus();
                    }
                }
            });

            el.addEventListener('keydown', (e) => {
                e.stopPropagation();
                if (e.key === 'Backspace' && !el.value) {
                    let prev = el.previousElementSibling;
                    while (prev && !prev.classList?.contains('assembly-combined-letter')) {
                        prev = prev.previousElementSibling;
                    }
                    if (prev) {
                        prev.focus();
                        prev.select();
                    }
                }
            });

            // Focus: select text and highlight
            el.addEventListener('focus', () => {
                el.select();
                el.style.borderBottomColor = '#3b82f6';
            });
            el.addEventListener('blur', () => {
                el.style.borderBottomColor = '#93c5fd';
            });
        });

        // Assembly combined check button — send all inputs to server in one request
        this.container.querySelectorAll('.assembly-combined-check').forEach(el => {
            el.addEventListener('click', async () => {
                const allInputs = this.container.querySelectorAll('.assembly-combined-letter');
                const byTransform = {};
                allInputs.forEach(box => {
                    const tIdx = box.dataset.transformIndex;
                    if (!byTransform[tIdx]) byTransform[tIdx] = [];
                    byTransform[tIdx].push(box.value || box.placeholder || '');
                });
                try {
                    const resp = await fetch('/trainer/input', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ clue_id: this.clueId, transform_inputs: byTransform })
                    });
                    const data = await resp.json();
                    if (data.render) this.render = data.render;
                    this.renderUI();
                    this.showToast(data.correct ? 'success' : 'error', data.message);
                } catch (err) {
                    console.error('Assembly combined check error:', err);
                }
            });
        });

        // Assembly hint toggle — per-transform hint visibility
        this.container.querySelectorAll('.assembly-hint-toggle').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const transformIdx = parseInt(el.dataset.transformIndex, 10);
                this.updateUIState('toggle_assembly_hint', { transform_index: transformIdx });
            });
        });

        // Assembly result letter inputs
        this.container.querySelectorAll('.assembly-result-letter').forEach(el => {
            el.addEventListener('input', (e) => {
                const letter = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
                e.target.value = letter;

                if (letter) {
                    let next = el.nextElementSibling;
                    while (next && !next.classList?.contains('assembly-result-letter')) {
                        next = next.nextElementSibling;
                    }
                    if (next?.classList?.contains('assembly-result-letter')) {
                        next.focus();
                    }
                }
            });

            el.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !el.value) {
                    let prev = el.previousElementSibling;
                    while (prev && !prev.classList?.contains('assembly-result-letter')) {
                        prev = prev.previousElementSibling;
                    }
                    if (prev?.classList?.contains('assembly-result-letter')) {
                        prev.focus();
                        prev.select();
                    }
                }
            });
        });

        // Assembly check button
        this.container.querySelectorAll('.assembly-check-btn').forEach(el => {
            el.addEventListener('click', () => {
                const letters = [];
                this.container.querySelectorAll('.assembly-result-letter').forEach(box => {
                    letters.push(box.value || '');
                });
                this.submitInput(letters.join(''));
            });
        });

        // Multiple choice options
        this.container.querySelectorAll('.mc-option').forEach(el => {
            el.addEventListener('click', () => {
                this.submitInput(el.dataset.value);
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
                const letter = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
                e.target.value = letter;

                const letters = [];
                this.container.querySelectorAll('.answer-box').forEach(box => {
                    letters.push(box.value || '');
                });
                this.updateUIState('type_answer', { letters });

                // Auto-advance — skip word gaps
                if (letter) {
                    let next = el.nextElementSibling;
                    while (next && !next.classList?.contains('answer-box')) {
                        next = next.nextElementSibling;
                    }
                    if (next?.classList?.contains('answer-box')) {
                        next.focus();
                    }
                }
            });

            el.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !el.value) {
                    let prev = el.previousElementSibling;
                    while (prev && !prev.classList?.contains('answer-box')) {
                        prev = prev.previousElementSibling;
                    }
                    if (prev?.classList?.contains('answer-box')) {
                        prev.focus();
                        prev.select();
                    }
                }
            });

            // Focus style + select existing letter so next keystroke replaces it
            el.addEventListener('focus', () => {
                if (!el.disabled) {
                    el.style.borderBottomColor = '#3b82f6';
                    el.select();
                }
            });
            el.addEventListener('blur', () => {
                if (!el.disabled) el.style.borderBottomColor = el.value ? '#475569' : '#cbd5e1';
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
