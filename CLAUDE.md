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
Every transform prompt in the assembly step must teach a cryptic convention, not just label an operation. The student should understand *why* this word points to those letters. Mechanical prompts like "Find a 2-letter synonym for 'in'" or "'IT' is used as-is — type it in (2 letters)" tell the student what to do but not what to learn. The `transformPrompts` in `render_templates.json` and per-transform `hint` text in `clues_db.json` should connect the clue word to the convention being used:
- **synonym**: guide the student to the specific crossword convention (e.g. "In cryptics, 'work' almost always means OP — it's one of the most common abbreviations")
- **abbreviation**: explain the shorthand (e.g. "'number' in cryptics usually points to NO — a standard abbreviation")
- **literal**: explain why this word is taken at face value, not as a clue to something else
- **letter_selection**: teach the pattern (e.g. "'head of office' = take the first letter — 'head of' always means first letter in cryptics")
- **reversal/deletion/anagram/container**: connect the indicator word to the operation it signals

**NO per-clue prompt overrides.** All prompts come from the generic `transformPrompts` templates in `render_templates.json`. If a template doesn't cover a case, extend the template — never add a `prompt` field to an individual transform in `clues_db.json`. The `hint` field is for clue-specific teaching (convention explanations, dictionary links); the `prompt` is always template-driven.

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

After the student finds the definition, step 2 depends on whether the clue has indicator words:

- **Clues WITH indicators** (anagram, container, hidden, deletion, reversal — and charades that contain these): Show word chips (`tap_words`) so the student can find and tap the indicator word(s). A clue can have multiple indicator steps (e.g. 26A has both a reversal and a container indicator). Every dependent transform (reversal, deletion, anagram) in the assembly MUST have a corresponding indicator step — the `test_indicator_coverage` test enforces this.
- **Clues WITHOUT indicators** (pure charades, double definition): Show multiple choice options (`multiple_choice`) so the student can select the clue type. There are no indicator words to find, so word chips are not shown — the student just picks from a list.

Examples: 5D (deletion — indicator "A lot of") and 2D (anagram — indicator "Crooked") show word chips at step 2. 26A (charade with reversal+container) has two indicator steps for "back" and "in". Pure charades like 4A and 25A show multiple choice instead.

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

**NO AI/LLM in this app.** Teaching mode uses pre-annotated step data from the Supabase database (or JSON files in development), NOT dynamically generated explanations.

**Training data source (`TRAINING_SOURCE` env var)**
- `supabase` (default): Loads training metadata from the `training_metadata` JSONB column on the `clues` table. Requires `upload_training_metadata.py` to have been run first. No auto-reload — server restart picks up database changes.
- `file`: Loads from `clues_db.json` file (development/testing only). Auto-reloads on file change (mtime check on each `/trainer/start` request).
- No silent fallback between sources. If the configured source fails, the server errors out with a clear message.

**Auto-reload and auto-restart**
- **`render_templates.json`**: Server checks file mtime on each `/trainer/start` request, reloads automatically — no server restart needed.
- **`clues_db.json`** (when `TRAINING_SOURCE=file`): Same mtime-based auto-reload as render templates.
- **Supabase training data** (when `TRAINING_SOURCE=supabase`): No auto-reload. Restart the server to pick up database changes.
- **Python code**: The server runs with `debug=True` (Werkzeug reloader). Any `.py` file change triggers an automatic server restart. `render_templates.json` is also in `extra_files` as a safety net.

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
| `puzzle_store_supabase.py` | Supabase database storage (required) — puzzles, clues, training metadata |
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
| `clues_db.json` | Pre-annotated clue database (56 clues: 30 from puzzle 29453 + 26 from puzzle 29147) — development source, also used by upload script |
| `static/trainer.js` | Stateless trainer UI (renders server state) |
| `validate_training.py` | Training metadata validator — structural, semantic, convention, and publication checks |
| `test_regression.py` | Regression test suite: 330 tests (30 clues × 11 tests), stdlib only |

### Database & Migrations
| File | Purpose |
|------|---------|
| `migrations/001_initial_schema.sql` | Initial DB schema (publications, puzzles, clues, user_progress) |
| `migrations/002_add_training_metadata.sql` | Adds `training_metadata` JSONB column to clues table |
| `migrations/004_add_training_locked.sql` | Adds `training_locked` column to puzzles table |
| `upload_training_metadata.py` | Uploads training metadata from `clues_db.json` to Supabase (requires `--puzzle` or `--clue` filter) |
| `lock_puzzle.py` | Lock/unlock puzzle training data (auto-backs up before locking) |
| `backup_puzzle.py` | Backup puzzle training data from Supabase to `backups/{puzzle}.json` |
| `restore_puzzle.py` | Restore puzzle training data from backup file to Supabase |

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
     │        │        ├── Supabase clues.training_metadata (default, TRAINING_SOURCE=supabase)
     │        │        ├── clues_db.json (dev fallback, TRAINING_SOURCE=file)
     │        │        └── render_templates.json (presentation templates, always file-based)
     │        │
     │        └── puzzle_store_supabase.py → Supabase PostgreSQL
```

Supabase is required. `SUPABASE_URL` and `SUPABASE_ANON_KEY` must be set in `.env`. The server will not start without a valid connection.

For full architecture diagrams, data models, template system details, API endpoints, and UI specs, see `SPEC.md`.

## Teaching Mode — Key Concepts

**Simple Sequencer Engine:**
The trainer engine (`training_handler.py`, ~1120 lines) owns ALL trainer business logic: clue database loading/lookup (from Supabase or file), session management, the sequencer engine, and template variable resolution. It reads flat steps from clue metadata, looks up a render template by step type, presents each step, validates input, and advances. No nesting, no phases within steps (except `assembly` which has sub-phases for transforms). The routes layer (`trainer_routes.py`, ~150 lines) is a thin HTTP wrapper that only extracts request parameters and delegates to `training_handler`.

**Two-Layer Template System:**
- Layer 1: Clue step metadata — clue-specific data (which words, indices, expected answers, hints). Stored in Supabase `clues.training_metadata` (production) or `clues_db.json` (development).
- Layer 2: Render templates in `render_templates.json` — generic presentation logic (inputMode, prompt, intro, hint, onCorrect). Always file-based.
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
TRAINING_SOURCE=supabase    # 'supabase' (default) or 'file' (uses clues_db.json)
```

## Common Commands
```bash
python3 crossword_server.py                                          # Start server (uses TRAINING_SOURCE=supabase by default)
TRAINING_SOURCE=file python3 crossword_server.py                     # Start server with file-based training data
python3 test_regression.py                                           # Run 330 regression tests (server must be running)
python3 upload_training_metadata.py --puzzle 29147                   # Upload one puzzle's training data to Supabase
python3 upload_training_metadata.py --clue times-29147-1d            # Upload one clue's training data
python3 upload_training_metadata.py --puzzle 29147 --dry-run         # Preview upload without writing
python3 lock_puzzle.py --lock 29453                                  # Lock a puzzle (auto-backs up first)
python3 lock_puzzle.py --unlock 29453                                # Unlock a puzzle
python3 lock_puzzle.py --status 29453                                # Check lock status
python3 lock_puzzle.py --list                                        # List all locked puzzles
python3 backup_puzzle.py --puzzle 29453                              # Backup puzzle training data from Supabase to backups/29453.json
python3 restore_puzzle.py --puzzle 29453                             # Restore puzzle training data from backup (must unlock first)
python3 restore_puzzle.py --puzzle 29453 --dry-run                   # Preview restore without writing
python3 validate_training.py                                         # Validate all training items (structural + semantic + convention + publication)
python3 -c "import json; json.load(open('clues_db.json')); print('Valid')"  # Validate clues_db JSON syntax
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=21"></script>
```

## Mobile Design
Grid uses CSS Grid with `1fr` units, NOT fixed pixel sizes. See `SPEC.md` Section 11 for full details.

## Parsing Clues — Systematic Approach

When creating training metadata for a new clue, use a two-phase approach: **solve first, then encode.**

### Phase 1: Solve the clue

You have the clue text, the definition, and the answer. As an expert in Times cryptic crosswords, **solve the wordplay cold** — work out the full parse before touching the metadata format.

1. **Start from the answer letters** — the answer is the Rosetta Stone. Write them out (e.g. H-E-L-E-N-O-F-T-R-O-Y).
2. **Scan for known patterns** — abbreviations (E=English, F=female, CIA=agents), common short words, letter groups that map to clue words.
3. **Identify the wordplay type** — anagram? container? charade? The indicator words and letter mechanics will tell you.
4. **Work out the complete parse** — which words contribute which letters, via what mechanism (synonym, abbreviation, literal, anagram, reversal, container, etc.).
5. **Verify mechanically** — do the letters actually work? Check anagram sorts, reversal directions, container structures letter-by-letter. Don't trust your first guess.

If stuck, research: check the Times for the Times blog, crossword solver sites, or thesaurus lookups. Never guess.

### Phase 2: Encode as training metadata

Once you have the full parse verified, walk through it with the user **one step at a time** (like the trainer), showing:
1. **Word table** — all words with their indices
2. **Remaining words** — which words haven't been assigned a role yet
3. **The answer** — always visible, always in uppercase with letter count

Present each step for confirmation: definition → indicators → fodder/outer/inner → assembly transforms. Then write the metadata to `clues_db.json` and validate.

### Common pitfalls
- **Don't fumble through indicators before solving** — solve the wordplay first, then you know what the indicators are.
- **Verify letter-by-letter** — 1D taught us that "revolution" reverses the WHOLE container result (CIMEANA→ANAEMIC), not just one part. Always check.
- **Research before guessing** — if unsure about an abbreviation or synonym, look it up. Never hypothesise.
- **Watch for multi-word definitions** — the definition can be more than one word (e.g. "Classic beauty"), always at the start or end.
- **Connectors carry no letters** — words like "for", "and", "with", "in" (when not an indicator) are just grammatical glue.
- **Abbreviations hide in anagram fodder** — E=English, F=female, N=north etc. can supply single letters to an anagram alongside literal words.

## Clue Metadata Reference

All 56 clues in `clues_db.json` are in the flat format. When editing or adding clues, follow these patterns.

### Reference clues — study these BEFORE editing any clue:
- **5D** — deletion + reversal chain (indicator steps, tap_words flow)
- **1A** — container (definition → indicator → outer_word → inner_word → assembly)
- **17D** — container (same pattern as 1A)
- **4A** — pure charade (no indicators, multiple_choice wordplay_type step)
- **25A** — pure charade (same pattern as 4A)
- **6D** — charade with ordering indicator ("after")
- **22A** — charade with anagram indicator ("taking")
- **26A** — charade with reversal + container indicators ("back", "in")
- **28A** — charade with reversal chain (CA + RASE→reversed→ESAR)
- **18D** — charade with reversal of compound (FLEE + G+NIT→reversed→TING)
- **12A** — anagram with fodder pieces (literal parts + final anagram)
- **23D** — hidden reversed word with dictionary lookup on transform

### Flat Format — top-level fields:
```
clue (string), number, enumeration, answer, words (array matching clue text exactly),
clue_type, difficulty ({definition, wordplay, overall}), steps (array)
```

### Step types and flows:
- Step 1 always: `definition` (tap_words) — indices, position, hint
- Step 2 depends on clue (Step 2 Rule above):
  - WITH indicators → `indicator` (tap_words) — can have multiple indicator steps per clue
  - WITHOUT indicators → `wordplay_type` (multiple_choice) with expected, options, hint
- Then type-specific steps: `fodder`, `outer_word`, `inner_word` (all tap_words)
- Final step: `assembly` with intro, failMessage, transforms array, result
- Each transform: `{role, indices, type, result, hint}` — type is synonym/abbreviation/literal/reversal/deletion/anagram/container/letter_selection
- Transforms can optionally have `lookup: {word, url}` for dictionary links
- **Never add a `prompt` field to individual transforms** — all prompts come from `transformPrompts` templates. Use `hint` for clue-specific teaching.

### Key rules:
- Follow the Step 2 Rule (see above)
- Every dependent transform (reversal/deletion/anagram/container) in the assembly MUST have a matching indicator step — `test_indicator_coverage` enforces this
- Indicator steps must have `indicator_type` field (container, anagram, deletion, reversal, ordering, letter_selection, hidden_word) — the template uses this for type-specific text
- Indicator type equivalences: `hidden_word` covers `reversal`
- Container insertions use transform type `container` (not `anagram`) — the template explains the insertion operation
- Indicator indices must be ONLY the indicator word itself, not connectors like "by", "with", "in"
- Hints must teach cryptic conventions (e.g. "'work' nearly always means OP"), not just define words
- **Indicator hints must NOT repeat the indicator type label** — the `completedTitle` template already prefixes with `{indicatorType} indicator:`, so the hint text must not say "anagram indicator", "deletion indicator", etc. The `test_template_text` guard test enforces this.
- Transform `type` must be accurate: use "abbreviation" not "synonym" for standard cryptic mappings
- `words` array must exactly match the clue text (case, spelling, punctuation including —)
- Assembly intro should teach through consequence: show what happens with raw words first, then ask why it doesn't work
- Only change the clue you are asked to change
- When a compound transform is needed, break it into a chain of simple transforms (see 18D, 28A)
- Transform `role` fields are formatted for display automatically (`part2a` → `Part 2a`, `outer` → `Outer`)

## Training Metadata Validation

`validate_training.py` runs four layers of checks on every training item before it reaches the server. Errors block upload/load; warnings are logged but don't block.

**Integration points:**
- `upload_training_metadata.py` — validates before uploading (errors skip item)
- `training_handler.py` `load_clues_db()` — validates on load (errors raise ValueError, crash loud)
- Standalone: `python3 validate_training.py` — validates all items in `clues_db.json`

### Layer 1: Structural checks
- Required top-level fields exist (clue, number, enumeration, answer, words, clue_type, difficulty, steps)
- `words` array matches clue text (punctuation-tolerant comparison)
- Steps is non-empty, each has valid `type` (must be a key in `render_templates.json`)
- Indices in bounds for steps and transforms
- Step-specific required fields (e.g. `indicator` needs `indices`, `hint`, `indicator_type`)
- Valid `indicator_type` values

### Layer 2: Semantic checks
- Assembly `result` == `answer`
- Terminal transform letters match assembly result (chain-aware: dependent transforms consume predecessors)
- Total letter count matches enumeration
- Each transform has required fields (`role`, `indices`, `type`, `result`, `hint`)
- Valid transform `type` (synonym/abbreviation/literal/reversal/deletion/anagram/container/letter_selection)
- No `prompt` field on individual transforms (architecture rule)
- Indicator coverage: every dependent transform (reversal/deletion/anagram/container) has a matching indicator step

### Layer 3: Convention checks (per-transform)
Deterministic checks — **hard errors**:
- **literal**: result == uppercase of clue word(s)
- **reversal**: result == reverse of consumed predecessor(s)
- **deletion**: result is predecessor with letter(s) removed (subsequence check)
- **anagram**: sorted letters of input == sorted letters of result
- **container**: result is one piece inserted inside another
- **letter_selection**: result extractable by first/last/alternating/hidden letters

Lookup-based — **warnings**:
- **abbreviation**: checked against `CRYPTIC_ABBREVIATIONS` (~200 entries) + publication-specific dictionary
- **synonym**: no check yet (no external API)

### Layer 4: Publication-specific checks
Publication is extracted from item ID (e.g. `times-29453-11a` → `times`). All publication checks produce **warnings**, not errors.

**Times (`times`) conventions:**
- **British spelling** — answers checked against ~35 American spelling patterns (COLOR→COLOUR, CENTER→CENTRE, GRAY→GREY, etc.). Ambiguous words with valid shared meanings (tire, curb, draft) are excluded.
- **Times abbreviation dictionary** (`TIMES_ABBREVIATIONS`, ~70 entries) — extends the general dictionary with UK-specific mappings:
  - British institutions: RA (Royal Academy), NT (National Trust), BBC, NHS, BM, VA
  - UK politics: CON, LAB, LIB, MP, PM, TORY
  - British royalty/honours: ER, HM, OBE, MBE, CBE, MC, DSO, VC
  - British military: RA (gunners), RE (sappers), RM (marines), RN (fleet/navy), TA (reserves), OR (ranks)
  - UK education: ETON, SCH, UNI
  - UK rivers: CAM, DEE, DON, EXE, TAY, URE, USK, WYE, AVON, etc. (including cryptic misdirections: "flower"/"banker"/"runner" = river)
  - Cricket: duck=O, maiden=M, eleven=XI
  - Old British currency: bob=S, quid=L, guinea=G/GN, copper=D
  - British slang: chap=MAN, pub=INN/PH, loo=WC/LAV

**Adding a new publication:** Add a new entry to `PUBLICATION_CONVENTIONS` dict in `validate_training.py` with `spelling_checks` and `extra_abbreviations` keys.

## Current Work — Puzzle 29147 Training Metadata

**Status:** 26 of 32 clues completed and validated. 6 remaining (see below).

**Completed clues (26):**
- **1A** — ASHAMED: charade (AS + HAM + ED)
- **1D** — ANAEMIC: container + reversal (CIA contains MEAN → reversed)
- **2D** — HELEN OF TROY: anagram (TO + E + F + ONLY + HER → anagram)
- **3D** — MY WORD: double definition (exclamation + promise)
- **4D** — DARTH VADER: charade + container (DART + HER containing V + AD)
- **5A** — REMAINS: charade (RE + MAINS)
- **5D** — ROSE: triple definition (grew/flower/spray attachment)
- **6D** — MINISTRY: charade with ordering (MINIS + TRY, "priority" = ordering indicator)
- **7D** — IDA: hidden word in holIDAys
- **8D** — SALFORD: container (SAD containing L + FOR)
- **9A** — AIL: letter selection (alternate letters from bAcIlLi)
- **11A** — MONARCHY: charade + letter selection (MON + ARCH + Y)
- **14D** — STRATEGIST: charade (ST + RATE + GIST)
- **15A** — CUFF: charade (CU + FF)
- **16A** — MASTERMIND: container + charade (MATER containing S = MASTER + MIND)
- **17D** — SPOTLESS: charade (SPOT + LESS)
- **18A** — PERIPHERAL: anagram (HELP + REPAIR)
- **18D** — PICKLED: charade (PICK + LED)
- **19A** — LIMB: deletion (LIMBO - O)
- **20D** — BUGBEAR: charade (BUG + BEAR)
- **22A** — COYOTE: charade (COY + OTE)
- **23A** — DEPUTING: anagram (EG + PUNDIT)
- **24D** — ZANY: charade (Z + ANY)
- **26D** — ALB: hidden reversed word in shruBLAnd
- **28A** — DEBUSSY: charade + letter selection (DEBUS + SY)
- **29A** — TO ORDER: reversal (RED + ROOT → reversed)

**Remaining clues (6):** Each needs the wordplay fully solved before encoding. Blog parses are from Times for the Times.

- **10A** — "Frank has cut short walk clutching right shoe" (5,3,3) = WARTS AND ALL
  - Blog parse: WALk (cut short) containing RT (right) + SANDAL (shoe)
  - Problem: couldn't verify letter-by-letter how WAL+RT+SANDAL → WARTSANDALL (11 letters). Parse needs more analysis.
- **12A** — "Pretended to beg money from speaker" (6) = PSEUDO
  - Blog parse: homophone of SUE (beg) + DOUGH (money) → sounds like PSEUDO
  - Blocker: **no homophone template exists yet** — needs new template in `render_templates.json`
- **13D** — "Lay egg, fine on reflection, as one must eat" (11) = UNINITIATED
  - Blog parse: UNITED (as one) contains NIT (egg) + IA (A1/fine reversed)
  - Parse verified: UNI + NIT + IA + TED = UNINITIATED ✅
  - Blocker: **validator `_check_container` fails** — the reversal (AI→IA) creates a 4th predecessor that confuses the container check. Need to teach the validator that reversed predecessors replace (not add to) their input.
- **21D** — "Extremely enthusiastic piece first to highlight boring essay" (4,2) = GUNG HO
  - Blog parse: GUN (piece) + G (first of highlight) + HO (boring essay — H in GO?)
  - Problem: HO parse unclear. Possibly H (boring = drill bit?) inside GO (essay/attempt), but G is already used. Needs research.
- **25A** — "Making disclosure about an old soldier's farewell" (5-6) = LEAVE-TAKING
  - Blog parse: LEAKING (disclosure) containing VET (old soldier)
  - Problem: LEAKING (7) + VET (3) = 10, but LEAVE-TAKING has 11 letters. Parse doesn't add up. Possibly "an old soldier" = A + VET (4 letters) but still unclear where insertion happens.
- **27A** — "Husband turning to one during the match" (3) = TIE
  - Blog parse: H (husband) replaced by I (one) in THE → TIE
  - Blocker: **no letter substitution template exists yet** — needs new template in `render_templates.json`

**Known issue (puzzle 29453 — DO NOT MODIFY 29453 DATA):**
- **9D** — has wrong apostrophe and wrong transform type. Not yet fixed.

**Validator changes made during 29147 work:**
- `_check_container`: now handles 3+ predecessors (multiple inner pieces concatenated via permutations)
- `_check_reversal`: now strips non-alpha characters (handles multi-word answers like TO ORDER)
- Added to CRYPTIC_ABBREVIATIONS: agents→CIA, spies→CIA, female→F, male→M, commercial→AD, light source→LED, touching→RE, regarding→RE, concerning→RE, pounds→L, unknown quantity→X/Y/Z, very loud→FF, goodbye from texter→CU, earnings for salesperson→OTE, light→L, advertisement→AD

**Process:** Two-phase approach: (1) Solve as AI expert with clue+definition+answer, (2) Encode as training metadata. Hints teach Times conventions (the macro-level checks become the hints).

**IMPORTANT: Puzzle 29453 is the verified reference. It is locked in Supabase (`training_locked = TRUE`) and 100% read-only. Never modify any `times-29453-*` entries in `clues_db.json`. The upload script and all store write methods refuse to modify locked puzzles. Use `python3 lock_puzzle.py --unlock 29453` only if you genuinely need to fix data.**

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch

To switch work between branches, cd to the appropriate directory.
