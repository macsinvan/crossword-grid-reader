# Architecture Rules (MANDATORY — applies to all files)

## Stateless Client
trainer.js has ZERO state. ALL state lives on the server in training_handler.py.
- Never add `this.foo = ...` in trainer.js
- Never put decision logic in trainer.js (if/else based on data analysis)
- Client renders what server sends — nothing more

## Template-Driven Rendering
All user-facing text comes from render_templates.json with {variable} substitution.
- Never construct display strings in Python code (no f-strings for UI text)
- Never construct display strings in JavaScript
- Add new template fields to render_templates.json, add new variables to _resolve_variables
- Sequencer resolves variables — that's all it does

## Two-Layer Template System
- Layer 1: clues_db.json — clue-specific data (indices, hints, expected answers)
- Layer 2: render_templates.json — generic presentation ({variable} placeholders)
- **NO per-clue prompt overrides.** Never add `prompt` fields to individual steps or transforms in clues_db.json. All prompts come from render_templates.json. If a template doesn't cover a case, extend the template. Use `hint` for clue-specific teaching.

## Error Out, Don't Fallback
No silent fallbacks. If data is missing, crash with a clear error message.
Never substitute defaults for missing data without explicit approval.

## No Guessing
Never state something without reading the code first.
If you don't know, say "I don't know — let me check."
