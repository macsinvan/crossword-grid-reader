#!/bin/bash
# SessionStart hook: re-inject critical rules after context compaction
cat << 'EOF'
CRITICAL RULES (preserved after compaction):

1. STATELESS CLIENT: trainer.js has ZERO state. All state on server. No logic in JS.
2. TEMPLATE-DRIVEN: All user-facing text in render_templates.json with {variable} placeholders. Never construct strings in Python or JS.
3. TWO-LAYER SYSTEM: clues_db.json (data) + render_templates.json (presentation). Sequencer resolves variables.
4. NO CODING WITHOUT GO: Read CLAUDE.md and SPEC.md first. Wait for explicit approval.
5. VERIFY BEFORE COMMIT: Test end-to-end. Server starts, UI loads, feature works.
6. NO GUESSING: Read code before stating anything. If unsure, say "I don't know."
7. ERROR OUT: No silent fallbacks. Crash with clear messages on errors.
8. ANSWER DIRECTLY: When asked a question, answer it. Don't take action.
EOF
exit 0
