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

**Assembly transform prompts — deliver the aha moment:**
Every transform prompt in the assembly step must teach a cryptic convention, not just label an operation. The student should understand *why* this word points to those letters. Mechanical prompts like "Find a 2-letter synonym for 'in'" or "'IT' is used as-is — type it in (2 letters)" tell the student what to do but not what to learn. Instead, each clue's transform `hint` and the per-clue `prompt` override (in `clues_db.json`) should connect the clue word to the convention being used:
- **synonym**: guide the student to the specific crossword convention (e.g. "In cryptics, 'work' almost always means OP — it's one of the most common abbreviations")
- **abbreviation**: explain the shorthand (e.g. "'number' in cryptics usually points to NO — a standard abbreviation")
- **literal**: explain why this word is taken at face value, not as a clue to something else
- **letter_selection**: teach the pattern (e.g. "'head of office' = take the first letter — 'head of' always means first letter in cryptics")
- **reversal/deletion/anagram**: connect the indicator word to the operation it signals

The generic `transformPrompts` in `render_templates.json` (under the `assembly` template) provide a baseline, but the real teaching happens through per-clue `prompt` overrides and `hint` text in `clues_db.json`. When writing clue metadata, always ask: "will the student understand the cryptic trick after reading this?"

### Template Rules — MANDATORY

When writing or modifying step metadata for clues:

1. **Check existing templates first.** Read `render_templates.json` — can an existing template handle this step? If so, use it. If it needs a small extension, extend it. Don't invent new templates without explicit approval.
2. **If using an existing template, follow its patterns exactly.** Templates define `completedTitle`, `onCorrect`, `menuTitle`, etc. with specific variable substitution patterns. Match them. For example, the `indicator` template uses `{indicatorType}` in menuTitle/completedTitle and dict-keyed lookup for prompt/intro — indicator steps just need the `indicator_type` field in their metadata.
3. **If a new template is genuinely needed, model it on the closest existing one.** Copy the structure (inputMode, prompt, menuTitle, completedTitle, onCorrect, expected_source) and adapt the content.
4. **Every step must deliver a teaching moment, not a robotic instruction.** We are building a teaching app. Each step should help the student understand a cryptic crossword convention — why something works, not just what to type. Prompts like "Enter the 3-letter result" are mechanical. Prompts like "What does 'work' mean in cryptic crosswords?" teach.

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

### Step 2 Rule: Indicators vs No-Indicators

After the student finds the definition, step 2 depends on whether the clue type uses indicator words:

- **Clue types WITH indicators** (anagram, container, hidden, deletion, reversal): Show word chips (`tap_words`) so the student can find and tap the indicator word(s). The indicator step comes next.
- **Clue types WITHOUT indicators** (charade, double definition): Show multiple choice options (`multiple_choice`) so the student can select the clue type. There are no indicator words to find, so word chips are not shown — the student just picks from a list.

This is why 5D (deletion — has indicator "A lot of") shows word chips at step 2, while 2D (anagram — has indicator "Crooked") also shows word chips. A charade clue would show multiple choice instead because charades typically have no indicator words.

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

### 2a. Test-First Bug Fixes — MANDATORY
**When fixing a bug, always follow this process:**
1. **Write a test case** that detects the bug (add to `test_regression.py`)
2. **Run tests → confirm FAIL** — the new test must fail, proving it catches the bug
3. **Fix the code** — make the minimal change to fix the bug
4. **Run tests → confirm PASS** — all tests pass, including the new one

Never fix code before proving the test catches the bug. If the test passes before the fix, the test is wrong.

### 3. Key Constraints

**STATELESS CLIENT ARCHITECTURE** (See SPEC.md Section 4.4)
The trainer UI (`trainer.js`) has ZERO state. ALL state lives on the server. If you're tempted to add `this.foo = ...` in trainer.js, STOP — it belongs on the server.

**Exception: Silent server sync for typing**
Answer/step input boxes sync to server on each keystroke BUT don't trigger re-render (to preserve focus). Only re-render when server sets `answerLocked=true`.

**Step state resets on advance**
When `step_index` increments, engine clears: `hint_visible`, `selected_indices`, `step_expanded`, `assembly_transforms_done`, `assembly_hint_index`. Answer boxes persist across steps.

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
| `trainer_routes.py` | Flask Blueprint — thin HTTP layer, all `/trainer/*` routes |
| `training_handler.py` | All trainer business logic: sequencer engine, clue DB, lookup, sessions |
| `render_templates.json` | **EXTERNAL TO CODE** - Render templates (HOW to present steps) |
| `clues_db.json` | Pre-annotated clue database (30 clues with flat step metadata) |
| `static/trainer.js` | Stateless trainer UI (renders server state) |
| `test_regression.py` | Regression test suite: 210 tests (30 clues × 7 tests), stdlib only |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (stateless teaching UI)
     │
     ├── crossword_server.py (Flask app + infrastructure routes)
     │        │
     │        ├── trainer_routes.py (Blueprint: thin HTTP layer, /trainer/* routes)
     │        │        └── delegates to training_handler.py
     │        │
     │        ├── training_handler.py (ALL trainer logic)
     │        │        ├── clues_db.json (30 annotated clues)
     │        │        └── render_templates.json (presentation templates)
     │        │
     │        └── puzzle_store_supabase.py → Supabase PostgreSQL
```

Supabase is required. `SUPABASE_URL` and `SUPABASE_ANON_KEY` must be set in `.env`. The server will not start without a valid connection.

For full architecture diagrams, data models, template system details, API endpoints, and UI specs, see `SPEC.md`.

## Teaching Mode — Key Concepts

**Simple Sequencer Engine:**
The trainer engine (`training_handler.py`, ~950 lines) owns ALL trainer business logic: clue database loading/lookup, session management, the sequencer engine, and template variable resolution. It reads flat steps from clue metadata, looks up a render template by step type, presents each step, validates input, and advances. No nesting, no phases within steps (except `assembly` which has sub-phases for transforms). The routes layer (`trainer_routes.py`, ~150 lines) is a thin HTTP wrapper that only extracts request parameters and delegates to `training_handler`.

**Two-Layer Template System:**
- Layer 1: Clue step metadata in `clues_db.json` — clue-specific data (which words, indices, expected answers, hints)
- Layer 2: Render templates in `render_templates.json` — generic presentation logic (inputMode, prompt, intro, hint, onCorrect)
- Each step `type` maps 1:1 to a render template
- For indicator steps: `indicator_type` field drives type-specific text via dict-keyed lookup and `{indicatorType}` variable
- Assembly steps can override `failMessage`

**Current render templates (7):**
| Template | inputMode | Purpose |
|----------|-----------|---------|
| `definition` | `tap_words` | Find the definition at start/end of clue |
| `wordplay_type` | `multiple_choice` | Identify the type of wordplay (Charade, Container, etc.) |
| `indicator` | `tap_words` | Find indicator word — `indicator_type` drives type-specific text |
| `outer_word` | `tap_words` | Identify which word wraps around |
| `inner_word` | `tap_words` | Identify which word goes inside |
| `fodder` | `tap_words` | Identify the word being operated on by an indicator |
| `assembly` | `assembly` | Coaching context, parallel transforms, combined letter entry |

**Step Menu with Inline Expansion:**
Steps are listed as a roadmap. The active step is collapsed by default (click chevron to expand). Completed steps show green ✓ and completion text. The `stepExpanded` flag in session state controls visibility.

**Assembly Steps (assembly):**
Assembly is a multi-phase step with its own sub-state (`assembly_phase`, `assembly_transforms_done`). The layout shows:
1. **Definition line** — reminds the student what they're looking for (e.g. "You're looking for a 6-letter word meaning 'Cover up in shower'")
2. **Indicator line** — for containers, shows piece layout with roles (e.g. "'nurses' tells us 'turn round' (inner) goes inside 'Not after' (outer)")
3. **Fail message** — shows raw words don't work, prompting transformation
4. **Transform prompts** — role-labelled coaching prompts (e.g. "outer, 'Not after', has a 2-letter synonym"), each with its own hint lightbulb. All transforms are always active — no locking. The student sees the full plan and works through them in any order.
5. **Combined result display** — editable letter inputs grouped by transform with `+` separators, showing cross letters as overwritable placeholders. Check button submits all filled groups.

Transform prompts are template-driven from `transformPrompts` in `render_templates.json`. Definition/indicator lines use `{variable}` substitution via `_resolve_variables()`. When the last transform result equals the final answer, the check phase is auto-skipped.

**Flat Clue Metadata Format (17D example):**
Steps are a flat array — no nesting. Each step has `type`, `indices` (word positions), and `hint`. Indicator steps also have `indicator_type` (container, anagram, deletion, reversal, ordering, letter_selection, hidden_word) which drives type-specific template text. The `assembly` step additionally has `transforms` (array of `{role, indices, type, result, hint}`) and `result`. Steps like `wordplay_type` have `expected` and `options`.

## Environment Variables
Create `.env` file (see `.env.example`):
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

## Common Commands
```bash
python3 crossword_server.py                                          # Start server
python3 test_regression.py                                           # Run 72 regression tests (server must be running)
python3 -c "import json; json.load(open('clues_db.json')); print('Valid')"  # Validate clues_db
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=21"></script>
```

## Mobile Design
Grid uses CSS Grid with `1fr` units, NOT fixed pixel sizes. See `SPEC.md` Section 11 for full details.

## Pickup Instructions — Clue Conversion

Convert all 30 clues in `clues_db.json` from the old format to the new flat format with teaching steps. Verify each converted clue works end-to-end (API test or browser).

### Progress

**Converted and verified (30 clues — all complete):**
1A, 1D, 2D, 3D, 4A, 5D, 6D, 7D, 8D, 9D, 10A, 11A, 12A, 13A, 14D, 15A, 16D, 17D, 18D, 19A, 20D, 21D, 22A, 23D, 24A, 25A, 26A, 26D, 27A, 28A

### Conversion Method

1. Read the old format entry for the clue
2. Analyze the cryptic wordplay — verify the breakdown is correct
3. Map to step flow: definition → indicator/wordplay_type → type-specific → assembly
4. Choose indicator words carefully — only the actual indicator, not connectors ("divided" not "divided by")
5. Break compound transforms into chains where possible (see 18D, 28A for examples)
6. Write teaching hints that explain cryptic conventions, not just state facts
7. Convert the JSON entry in clues_db.json
8. Validate JSON
9. Test all steps via API (start session → input each step → verify correct + complete)

### Reference clues — study these BEFORE converting any new clue:
- **5D** — deletion + reversal chain (indicator clues, tap_words flow)
- **1A** — container (definition → indicator → outer_word → inner_word → assembly)
- **17D** — container (same pattern as 1A)
- **4A** — charade (no indicators, multiple_choice wordplay_type step)
- **25A** — charade (same pattern as 4A)
- **6D** — charade with ordering indicator ("after")
- **28A** — charade with reversal chain (CA + RASE→reversed→ESAR)
- **18D** — charade with reversal of compound (FLEE + G+NIT→reversed→TING)
- **12A** — anagram with fodder pieces (literal parts + final anagram)

### Format Reference

**Old format** has nested `clue` object with `text`/`enumeration`/`answer`/`definition`, separate `metadata`, `publicationId`, `difficulty` with nested ratings, `verified` flag, and steps using `standard_definition`/`anagram`/etc types with `indicator`/`pieces`/`fodder` sub-objects.

**New flat format** — top-level fields:
```
clue (string), number, enumeration, answer, words (array matching clue text exactly),
clue_type, difficulty ({definition, wordplay, overall}), steps (array)
```

**Step types and flows:**
- Step 1 always: `definition` (tap_words) — indices, position, hint
- Step 2 depends on clue type (Step 2 Rule above):
  - WITH indicators → `indicator` (tap_words) with menuTitle, completedTitle, prompt, intro, hint
  - WITHOUT indicators → `wordplay_type` (multiple_choice) with expected, options, hint
- Then type-specific steps: `fodder`, `outer_word`, `inner_word` (all tap_words)
- Final step: `assembly` with intro, failMessage, transforms array, result
- Each transform: `{role, indices, type, result, hint}` — type is synonym/abbreviation/literal/reversal/deletion/anagram/letter_selection

**Key rules:**
- Follow the Step 2 Rule (see above)
- Indicator steps must have `indicator_type` field (container, anagram, deletion, reversal, ordering, letter_selection, hidden_word) — the template uses this for type-specific text
- Indicator indices must be ONLY the indicator word itself, not connectors like "by", "with", "in"
- Hints must teach cryptic conventions (e.g. "'work' nearly always means OP"), not just define words
- Transform `type` must be accurate: use "abbreviation" not "synonym" for standard cryptic mappings
- `words` array must exactly match the clue text (case, spelling, punctuation including —)
- Assembly intro should teach through consequence: show what happens with raw words first, then ask why it doesn't work
- Only change the clue you are asked to change
- When a compound transform is needed, break it into a chain of simple transforms (see 18D, 28A)

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch

To switch work between branches, cd to the appropriate directory.
