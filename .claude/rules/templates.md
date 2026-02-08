---
paths:
  - "render_templates.json"
  - "clues_db.json"
  - "training_handler.py"
---

# Template System Rules

## render_templates.json
- Contains ALL user-facing text as template strings with {variable} placeholders
- To add new display text: add a new field here, not in Python code
- Variables: {words}, {enumeration}, {hint}, {position}, {result}, {expected}, {definitionWords}, {indicatorHint}

## clues_db.json
- Contains clue-specific data: indices, hints, expected answers, transforms
- Per-clue overrides (menuTitle, completedTitle, prompt, intro) must follow the template's structural pattern
- words array must exactly match the clue text

## training_handler.py
- Sequencer only: reads steps, resolves template variables, validates input, advances
- _resolve_variables() is the ONLY place variable substitution happens
- Never construct display strings with f-strings or string concatenation
- To add a new variable: add it to _resolve_variables() and reference it in render_templates.json

## Step 2 Rule
- Clue types WITH indicators (anagram, container, hidden, deletion, reversal): step 2 is indicator (tap_words)
- Clue types WITHOUT indicators (charade, double definition): step 2 is wordplay_type (multiple_choice)
