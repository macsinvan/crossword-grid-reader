# Grid Reader - Claude Context

## Domain Expertise
You are an expert in cryptic crosswords and the techniques used to solve them. You have researched this topic thoroughly. We are developing a trainer to teach students how to approach solving cryptic clues in a holistic and natural way, only using the information they have available at each step.

### Coaching Tone — MANDATORY
All user-facing text in templates MUST read like a skilled teacher guiding a student, NOT like a technical system describing its own internals. This applies to:
- Menu item titles (before and after completion)
- Assembly labels, instructions, and failure messages
- Hints, prompts, and action text
- Any string the student sees

**Core coaching principle:**
In charades and container insertions, the clue words are rarely used directly. Each word is typically a clue *to* another word — a synonym, abbreviation, or cryptic association. The assembly step exists to teach this: "these raw words don't work as-is, so what is each one really pointing to?" All template text must reflect this teaching principle.

**Rules:**
- No jargon: never use "transform", "raw insertion", "assembly", "outer/inner transform", "fodder" or similar programmer/solver terminology that students wouldn't know
- No ALL-CAPS labels: "CONTAINER INDICATOR:" reads like a database field, not a teacher
- Short and sharp: screen space is limited, every word must earn its place
- Guide understanding: tell the student *why*, not just *what* (e.g. "'lengthened' tells us one word goes inside another" not "CONTAINER INDICATOR: lengthened")
- Use the student's language: "What does 'architect' mean?" not "Outer transform for 'architect':"
- Completed steps should summarise the insight, not label the category
- Before writing ANY user-facing text, think as a cryptic crossword teacher — research the domain if needed, don't hypothesise from code structure

### Coaching Guidance Per Template Type

Every template's user-facing text must connect to these high-level coaching insights. Step instructions should flow naturally from this guidance.

**standard_definition** — Every cryptic clue contains a straight definition, always at the very start or very end, never in the middle. Finding it first narrows your search. Completed: confirm what the definition means and where it sits.

**container (insertion)** — An indicator word (e.g. "holding", "within", "nurses", "lengthened") tells you one word goes inside another. You need to identify: which word signals the insertion, which is the outer word, and which goes inside. The clue words themselves rarely *are* the answer letters — each is pointing to another word (synonym, abbreviation, etc.). The assembly step shows this: the raw words don't fit, so what does each one really mean?

**charade** — The wordplay breaks into parts that join end-to-end. Often there are no indicator words at all — that's the giveaway it's a charade. Each part is a clue to a shorter word. Again, the raw words rarely work directly; each is pointing to something else. The assembly step demonstrates this by showing the raw words don't produce the right number of letters.

**anagram** — An indicator word (e.g. "mixed", "confused", "struggling") signals that letters need rearranging. First collect the letters (sometimes from multiple words), then rearrange them into the answer.

**hidden** — The answer is literally hiding in plain sight, spelled out across consecutive letters spanning word boundaries. An indicator like "in", "from", or "some" points to this. Sometimes the hidden word is reversed.

**double_definition** — The clue is simply two definitions side by side, both pointing to the same answer. No wordplay trickery — just spot that both halves define the same word.

**transformation_chain** — Multiple operations applied in sequence: start with a word, then apply each transformation (synonym, deletion, reversal, etc.) one after another. Each step builds on the previous result.

**synonym / abbreviation / literal / reversal / deletion / letter_selection** — These are the building blocks that appear within charades, containers, and chains. Each teaches one specific trick: a word means something else (synonym), a standard short form (abbreviation, e.g. "five" = V), a word used as-is (literal), reading backwards (reversal), removing letters (deletion), or picking specific letters like first/last/middle (letter_selection).

**connector** — Some words in the clue are just glue — "and", "with", "for" — that don't contribute any letters. Recognising them helps the student focus on the words that matter.

## Communication Rules

**When I ask a direct question, answer it directly. Never take my question as a request to take action.**

## IMPORTANT: Implementation Rules

### 0. NO CODING WITHOUT A DESIGN SPEC
**If a feature is not documented in the design spec, DO NOT implement it.** Ask for the specification first.

### 1. Design Documentation Required
**DO NOT IMPLEMENT WITHOUT CONSULTING:**
1. `SPEC.md` - **Technical Specification** (canonical source for all technical detail)

### 2. Verification Required
**EVERY PLAN MUST:**
1. **Start with verification strategy** - Define how you will test the feature works
2. **End with verification completed** - Actually test in browser, not just API calls

**Verification Checklist:**
- [ ] Server starts without errors
- [ ] UI loads at http://127.0.0.1:8080/
- [ ] Feature works end-to-end in browser (click through the UI)
- [ ] No JavaScript console errors
- [ ] No Python server errors

### 3. Key Constraints

**STATELESS CLIENT ARCHITECTURE** (See SPEC.md Section 4.4)
The trainer UI (`trainer.js`) has ZERO state. ALL state lives on the server. If you're tempted to add `this.foo = ...` in trainer.js, STOP — it belongs on the server.

**Exception: Silent server sync for typing**
Answer/step input boxes sync to server on each keystroke BUT don't trigger re-render (to preserve focus). Only re-render when server sets `answerLocked=true`.

**Step state resets on advance**
When `step_index` increments, `reset_step_ui_state()` clears: `hint_visible`, `selected_indices`, `step_text_input`. Answer boxes persist across steps.

**NO AI/LLM in this app.** Teaching mode uses pre-annotated step data from imported JSON files, NOT dynamically generated explanations.

**Auto-reload clues_db.json**
The server checks file modification time on each `/trainer/start` request. If `clues_db.json` has changed, it reloads automatically - no server restart needed.

**Error out, don't fallback — MANDATORY**
Do NOT add fallbacks in the code without explicit approval from the user. Never silently swallow errors, substitute defaults for missing data, or degrade functionality without raising an error. If something is wrong, crash with a clear message. Silent fallbacks hide bugs and cause confusion.

## What This Is
Web-based Times Cryptic crossword solver. Import PDFs, solve interactively, get step-by-step teaching via template-based step display system.

## Quick Start
```bash
# Ensure .env file exists with Supabase credentials (see .env.example)
python3 crossword_server.py  # port 8080
```
Open http://localhost:8080

## Key Files

### Infrastructure (crossword_server.py)
| File | Purpose |
|------|---------|
| `crossword_server.py` | Flask server (port 8080) — infrastructure routes only |
| `puzzle_store_supabase.py` | Supabase database storage (required) |
| `pdf_processor.py` | PDF parsing, grid/clue extraction |
| `crossword_processor.py` | Grid structure detection |
| `templates/index.html` | Web UI (bump `?v=N` for cache busting) |
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence |

### Trainer (trainer_routes.py)
| File | Purpose |
|------|---------|
| `trainer_routes.py` | Flask Blueprint — all `/trainer/*` routes, clues DB loading |
| `training_handler.py` | Teaching mode logic: loads templates, get_render(), handle_input() |
| `clue_step_templates.json` | **EXTERNAL TO CODE** - Clue step template schemas (WHAT data from clue) |
| `render_templates.json` | **EXTERNAL TO CODE** - Render templates (HOW to present steps) |
| `clues_db.json` | Pre-annotated clue database (30 clues with template metadata) |
| `static/trainer.js` | Stateless trainer UI (renders server state) |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (stateless teaching UI)
     │
     ├── crossword_server.py (Flask app + infrastructure routes)
     │        │
     │        ├── trainer_routes.py (Blueprint: all /trainer/* routes)
     │        │        ├── training_handler.py (teaching logic)
     │        │        └── clues_db.json (30 annotated clues)
     │        │
     │        └── puzzle_store_supabase.py → Supabase PostgreSQL
```

Supabase is required. `SUPABASE_URL` and `SUPABASE_ANON_KEY` must be set in `.env`. The server will not start without a valid connection.

For full architecture diagrams, data models, template system details, API endpoints, and UI specs, see `SPEC.md`.

## Teaching Mode — Key Concepts

**Two-Layer Template System** (See SPEC.md Section 4.2.2):
- Layer 1: Clue step metadata in `clues_db.json` — clue-specific data (which words, expected answers)
- Layer 2: Render templates in `render_templates.json` — generic presentation logic (phases, input modes)
- Each step `type` maps 1:1 to a render template. 19 templates total.

**Step Menu Overview:**
When clicking "Solve", users see a step menu with inline expansion. Steps expand/collapse in place. See SPEC.md Section 6.1 for full UI spec.

**Template Expansion:**
Templates with multiple atomic steps expand automatically:
- `insertion_with_two_synonyms` → 4 steps (indicator, outer literal, inner synonym, assembly)
- `charade_with_parts` → Steps for each part + assembly
- `anagram_with_fodder_pieces` → Fodder identification + anagram
- `transformation_chain` → Step for each transformation

## Environment Variables
Create `.env` file (see `.env.example`):
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

## Common Commands
```bash
python3 crossword_server.py                                          # Start server
python3 -c "import json; json.load(open('clues_db.json')); print('Valid')"  # Validate clues_db
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=21"></script>
```

## Mobile Design
Grid uses CSS Grid with `1fr` units, NOT fixed pixel sizes. See `SPEC.md` Section 11 for full details.

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch

To switch work between branches, cd to the appropriate directory.
