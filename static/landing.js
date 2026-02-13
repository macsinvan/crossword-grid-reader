/**
 * Landing Page — Cryptic Trainer
 *
 * Handles the interactive demo (embedded TemplateTrainer),
 * smooth scrolling, and mobile nav toggle.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDemo();
    initSmoothScroll();
});

// =========================================================================
// Interactive Demo
// =========================================================================

async function initDemo() {
    // Showcase clue: 12A from puzzle 29463 (SEMINAR — hidden word)
    // Simple, satisfying, ideal for a first-time solver
    const SHOWCASE = {
        puzzle_number: '29463',
        clue_number: 12,
        direction: 'across'
    };

    const container = document.getElementById('demo-trainer-container');
    const clueTextEl = document.querySelector('.demo-clue-text');

    try {
        const resp = await fetch('/trainer/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(SHOWCASE)
        });

        if (!resp.ok) {
            const err = await resp.json();
            container.innerHTML = '<div class="demo-error"><p>' +
                escapeHTML(err.message || 'Could not load demo clue') + '</p></div>';
            return;
        }

        const data = await resp.json();

        // Show clue text from words array
        if (data.words) {
            clueTextEl.textContent = data.words.join(' ') +
                (data.enumeration ? ' (' + data.enumeration + ')' : '');
        }

        // Instantiate the trainer in the demo container
        const trainer = new TemplateTrainer(container, {
            clueId: data.clue_id,
            crossLetters: [],
            onComplete: () => {
                const completeEl = document.getElementById('demo-complete');
                if (completeEl) completeEl.classList.remove('hidden');
            }
        });

        trainer._updateSession(data);
        trainer.render = data;
        trainer.loading = false;
        trainer.renderUI();

    } catch (err) {
        console.error('Demo init failed:', err);
        container.innerHTML = '<div class="demo-error"><p>Could not connect to trainer</p></div>';
    }
}

// =========================================================================
// Smooth Scrolling
// =========================================================================

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function(a) {
        a.addEventListener('click', function(e) {
            var target = document.querySelector(a.getAttribute('href'));
            if (target) {
                e.preventDefault();
                // Close mobile nav if open
                var navLinks = document.querySelector('.nav-links');
                if (navLinks) navLinks.classList.remove('open');
                // Scroll with offset for sticky nav
                var offset = 70;
                var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({ top: top, behavior: 'smooth' });
            }
        });
    });
}

// =========================================================================
// Utilities
// =========================================================================

function escapeHTML(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
