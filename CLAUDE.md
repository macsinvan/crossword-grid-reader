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
Every transform prompt in the assembly step must teach a cryptic convention, not just label an operation. The student should understand *why* this word points to those letters. Mechanical prompts like "Find a 2-letter synonym for 'in'" or "'IT' is used as-is — type it in (2 letters)" tell the student what to do but not what to learn. The `transformPrompts` in `render_templates.json` and per-transform `hint` text in training metadata should connect the clue word to the convention being used:
- **synonym**: guide the student to the specific crossword convention (e.g. "In cryptics, 'work' almost always means OP — it's one of the most common abbreviations")
- **abbreviation**: explain the shorthand (e.g. "'number' in cryptics usually points to NO — a standard abbreviation")
- **literal**: explain why this word is taken at face value, not as a clue to something else
- **letter_selection**: teach the pattern (e.g. "'head of office' = take the first letter — 'head of' always means first letter in cryptics")
- **reversal/deletion/anagram/container**: connect the indicator word to the operation it signals

**NO per-clue prompt overrides.** All prompts come from the generic `transformPrompts` templates in `render_templates.json`. If a template doesn't cover a case, extend the template — never add a `prompt` field to an individual transform in training metadata. The `hint` field is for clue-specific teaching (convention explanations, dictionary links); the `prompt` is always template-driven.

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

### 2b. Fully Dynamic Test Suite — MANDATORY
**The test runner has ZERO hardcoded clue data.** It dynamically fetches all clues with training data from Supabase via `/trainer/clue-ids?full=1`, builds test data from live metadata, and runs all tests against every clue. No hardcoded lists, no generated test files, no manual maintenance.

- Adding training data for a new clue automatically includes it in the next test run — no regeneration step needed.
- Every clue in Supabase is tested. No silent omissions are possible.
- If a clue's training data is broken, the test fails loudly with a clear error.

### 3. Key Constraints

**STATELESS CLIENT ARCHITECTURE** (See SPEC.md Section 4.4)
The trainer UI (`trainer.js`) has ZERO state. ALL state lives on the server. If you're tempted to add `this.foo = ...` in trainer.js, STOP — it belongs on the server.

**Exception: Silent server sync for typing**
Answer/step input boxes sync to server on each keystroke BUT don't trigger re-render (to preserve focus). Only re-render when server sets `answerLocked=true`.

**Non-linear step completion**
All pre-assembly steps are available simultaneously — the student can tackle them in any order. Assembly is gated: it becomes active only when all prior steps are completed. `step_index` is the expanded-step pointer (which step the user is currently looking at), not a gatekeeper. Switching steps (via `select_step` action or auto-advance after correct answer) resets per-step UI state: `hint_visible`, `selected_indices`, `step_expanded`, `assembly_transforms_done`, `assembly_hint_index`. Answer boxes persist across steps.

**NO AI/LLM in this app.** Teaching mode uses pre-annotated step data from the Supabase database, NOT dynamically generated explanations.

**Training data source — lazy-loaded from Supabase**
Training metadata is fetched on demand from the `training_metadata` JSONB column on the `clues` table in Supabase. Each `/trainer/start` request queries Supabase for the specific clue by key (puzzle_number, clue_number, direction), validates it, and stores it in the session. No bulk loading at startup, no restart needed for DB changes — data is always fresh.

**Scale design:** This architecture supports 100s of puzzles, 1000s of clues, and 100s of simultaneous users. No clue data is held in memory beyond active sessions.

**Auto-reload and auto-restart**
- **`render_templates.json`**: Server checks file mtime on each `/trainer/start` request, reloads automatically — no server restart needed.
- **Supabase training data**: Lazy-loaded per request — always fresh, no restart needed.
- **Python code**: The server runs with `debug=True` (Werkzeug reloader). Any `.py` file change triggers an automatic server restart. `render_templates.json` is also in `extra_files` as a safety net.

**Error out, don't fallback — MANDATORY (code AND tests)**
Do NOT add fallbacks in the code without explicit approval from the user. Never silently swallow errors, substitute defaults for missing data, or degrade functionality without raising an error. If something is wrong, crash with a clear message. Silent fallbacks hide bugs and cause confusion.

This applies equally to tests. A test must never compensate for a failing code path by falling back to an alternative route that happens to succeed. If a test submits all assembly transforms and auto-skip should fire, the test must assert auto-skip fired — not silently fall through to the check phase and submit the answer there. A test that always passes is worse than no test at all.

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
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence, auth headers on admin APIs |
| `auth.py` | JWT verification (`get_current_user()`), `@require_admin` decorator |
| `static/auth.js` | Frontend auth module (Supabase Google OAuth, role-based UI) |
| `migrations/006_auth_profiles.sql` | Auth profiles table + auto-insert trigger |

### Trainer (trainer_routes.py)
| File | Purpose |
|------|---------|
| `trainer_routes.py` | Flask Blueprint — thin HTTP layer, all `/trainer/*` routes |
| `training_handler.py` | All trainer business logic: sequencer engine, lazy clue lookup, sessions |
| `render_templates.json` | **EXTERNAL TO CODE** - Render templates (HOW to present steps) |
| `static/trainer.js` | Stateless trainer UI (renders server state) |
| `validate_training.py` | Training metadata validator — structural, semantic, convention, and publication checks |
| `test_regression.py` | Fully dynamic regression tests — fetches all clues from Supabase, zero hardcoded data |

### Database & Migrations
| File | Purpose |
|------|---------|
| `migrations/001_initial_schema.sql` | Initial DB schema (publications, puzzles, clues, user_progress) |
| `migrations/002_add_training_metadata.sql` | Adds `training_metadata` JSONB column to clues table |
| `migrations/004_add_training_locked.sql` | Adds `training_locked` column to puzzles table |
| `upload_training_metadata.py` | Uploads training metadata to Supabase (requires `--puzzle` or `--clue` filter) |
| `lock_puzzle.py` | Lock/unlock puzzle training data (auto-backs up before locking) |
| `backup_puzzle.py` | Backup puzzle training data from Supabase to `backups/{puzzle}.json` |
| `restore_puzzle.py` | Restore puzzle training data from backup file to Supabase |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence, auth headers on admin APIs)
     ├── trainer.js (stateless teaching UI)
     ├── auth.js (Google OAuth, role-based UI show/hide)
     │
     ├── crossword_server.py (Flask app + infrastructure routes)
     │        │
     │        ├── auth.py (JWT verification, @require_admin decorator)
     │        │        └── Uses service role client to read profiles (bypasses RLS)
     │        │
     │        ├── trainer_routes.py (Blueprint: thin HTTP layer, /trainer/* routes)
     │        │        └── delegates to training_handler.py
     │        │
     │        ├── training_handler.py (ALL trainer logic)
     │        │        ├── Lazy-loads clues.training_metadata from Supabase per request
     │        │        └── render_templates.json (presentation templates, always file-based)
     │        │
     │        └── puzzle_store_supabase.py → Supabase PostgreSQL
     │
     └── Supabase Auth (Google OAuth) → auth.users → profiles table (role)
```

Supabase is required. `SUPABASE_URL` and `SUPABASE_ANON_KEY` must be set in `.env`. The server will not start without a valid connection. Authentication requires `SUPABASE_JWT_SECRET` and `SUPABASE_SERVICE_ROLE_KEY` (admin routes return 401 without these).

For full architecture diagrams, data models, template system details, API endpoints, and UI specs, see `SPEC.md`.

## Teaching Mode — Key Concepts

**Simple Sequencer Engine:**
The trainer engine (`training_handler.py`, ~1100 lines) owns ALL trainer business logic: lazy clue lookup from Supabase, per-request validation, session management, the sequencer engine, and template variable resolution. It reads flat steps from clue metadata, looks up a render template by step type, presents each step, validates input, and advances. No nesting, no phases within steps (except `assembly` which has sub-phases for transforms). The routes layer (`trainer_routes.py`, ~150 lines) is a thin HTTP wrapper that only extracts request parameters and delegates to `training_handler`.

**Two-Layer Template System:**
- Layer 1: Clue step metadata — clue-specific data (which words, indices, expected answers, hints). Stored in Supabase `clues.training_metadata`.
- Layer 2: Render templates in `render_templates.json` — generic presentation logic (inputMode, prompt, intro, hint, onCorrect). Always file-based.
- Each step `type` maps 1:1 to a render template
- For indicator steps: `indicator_type` field drives type-specific text via dict-keyed lookup and `{indicatorType}` variable
- Assembly steps can override `failMessage`

**Current render templates (4 active):**
| Template | inputMode | Purpose |
|----------|-----------|---------|
| `definition` | `tap_words` | Find the definition at start/end of clue |
| `wordplay_type` | `multiple_choice` | Identify the type of wordplay (Charade, Container, etc.) |
| `indicator` | `tap_words` | Find indicator word — `indicator_type` drives type-specific text |
| `assembly` | `assembly` | Coaching context, parallel transforms, combined letter entry |

**Deprecated templates (still supported but no longer used in new clues):**
| Template | inputMode | Purpose |
|----------|-----------|---------|
| `outer_word` | `tap_words` | Identify which word wraps around |
| `inner_word` | `tap_words` | Identify which word goes inside |
| `fodder` | `tap_words` | Identify the word being operated on by an indicator |

**Why deprecated:** These tap steps are redundant — the words they identify are the same words the assembly transforms operate on. The assembly step handles both identification and transformation in one place, which is simpler for the student and avoids interdependency issues (e.g. when a word needs transformation before its role is clear).

**Step Menu with Non-Linear Completion:**
Steps are listed as a roadmap. All pre-assembly steps start as active (blue circles) — the student picks any order. Only one step is expanded at a time; clicking another active step switches the expansion. Assembly is gated on all prior steps being completed. Completed steps show green ✓ and completion text. Four visual states: completed, active+expanded, active+collapsed (clickable), pending. The `stepExpanded` flag in session state controls active step visibility.

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
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```
`SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_JWT_SECRET` are required for authentication. Without them, admin routes (`/upload`, `DELETE /puzzles`, `POST /answers`) return 401. The trainer remains public.

## Common Commands
```bash
python3 crossword_server.py                                          # Start server
python3 test_regression.py                                           # Run regression tests (server must be running — tests all clues dynamically)
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
python3 validate_training.py                                         # Validate all training items in Supabase (structural + semantic + convention + publication)
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

Present each step for confirmation: definition → indicators → assembly transforms. Then upload the metadata to Supabase and validate. (Do NOT add outer_word, inner_word, or fodder steps — all word identification and transformation is handled in the assembly.)

### Common pitfalls
- **Don't fumble through indicators before solving** — solve the wordplay first, then you know what the indicators are.
- **Verify letter-by-letter** — 1D taught us that "revolution" reverses the WHOLE container result (CIMEANA→ANAEMIC), not just one part. Always check.
- **Research before guessing** — if unsure about an abbreviation or synonym, look it up. Never hypothesise.
- **Watch for multi-word definitions** — the definition can be more than one word (e.g. "Classic beauty"), always at the start or end.
- **Connectors carry no letters** — words like "for", "and", "with", "in" (when not an indicator) are just grammatical glue.
- **Abbreviations hide in anagram fodder** — E=English, F=female, N=north etc. can supply single letters to an anagram alongside literal words.

## Clue Metadata Reference

See `SPEC.md` Section 4.2.3 for the full metadata format, step types and flows, structural rules, and reference clues.

**Claude-specific rules when editing clue metadata:**
- Hints must teach cryptic conventions (e.g. "'work' nearly always means OP"), not just define words
- Assembly intro should teach through consequence: show what happens with raw words first, then ask why it doesn't work
- Only change the clue you are asked to change

**Hint checklist — verify every hint before uploading:**
- Indicator step hints must NEVER contain the indicator type name (anagram, reversal, container, deletion, hidden word, ordering, letter selection) — the template's `completedTitle` already prefixes with it, so repeating it is redundant
- Hints teach the *convention*, not the *answer* (e.g. "In cryptics, 'mixed' signals rearranging letters" not "The anagram gives PERIPHERAL")
- Hints are short — one sentence, two at most
- No programmer jargon (transform, fodder, outer/inner, raw insertion)
- Read the hint back as a student would see it — does it explain *why*, not just *what*?

## Training Metadata Validation

See `SPEC.md` Section 14 for the full 4-layer validation architecture, integration points, convention checks, and publication-specific dictionaries.

## New Session Startup

When starting a new session, check these first:

1. **Run the validator** to see current state: `python3 validate_training.py` (validates all clues in Supabase)
2. **Check puzzle lock status**: `python3 lock_puzzle.py --list`
3. **Read this section** and "Current Work" below for what's in progress

**Key things a new session needs to know:**
- Puzzle **29453** (30 clues) is **locked** and 100% verified — never modify
- Puzzle **29147** (32/32 clues done) is complete — all clues annotated and validated
- Puzzle **29463** (30/30 clues done) is complete — all clues annotated and validated
- Training data lives in **Supabase** (`clues.training_metadata`), not in JSON files
- Training data is **lazy-loaded** from Supabase per request — no restart needed for DB changes
- Clues with validation errors return **422** with error details when clicked in the UI
- The standalone validator (`validate_training.py`) loads directly from Supabase
- OCR errors in the DB `text` column cause words-vs-clue mismatches — fix by updating the `text` column directly in Supabase

## Current Work

### Puzzle 29147 — COMPLETE (32/32 clues)
All 32 clues annotated, validated, and passing regression tests.

### Puzzle 29463 — COMPLETE (30/30 clues)
All 30 clues annotated, validated, and passing regression tests (1104/1104 tests pass across 92 total clues).

**Completed clues (29463):**
- **1A** — CAPUCHIN: deletion (CAPUCHINO - O)
- **1D** — CUTTER: double definition (knife + boat)
- **2D** — PATRIOTIC: charade + abbreviation (PAT + RIOT + IC)
- **3D** — CAESURA: container + reversal (CASE contains RUA reversed)
- **4D** — IMIDE: container (I'M containing IDE)
- **5A** — GAMBIT: charade (GAMB + IT)
- **6D** — ASHAMED: charade (AS + HAM + ED)
- **7D** — BRUIN: charade (B + RUIN)
- **8D** — THEORIST: anagram (HIS + OTTER)
- **9D** — PHOSGENE: container + charade (PH + OS containing H + ENE)
- **10A** — TO THE LIGHTHOUSE: charade (TO + THE + LIGHT + HOUSE)
- **11A** — EPICURE: container (EPIC containing URE)
- **12A** — SEMINAR: hidden word in houSEMINARy
- **13A** — STRADDLE: container (SADDLE containing TR)
- **14D** — DIATRIBE: container (DIRE containing AT + RIB)
- **15A** — DRIPS: charade (DR + IPS)
- **16D** — INTERBRED: anagram (BIRD + ENTER)
- **17D** — BAGPIPER: container (BIER containing AGP — A + GP)
- **18A** — ASCOT: deletion (MASCOT - M)
- **19D** — TRIREME: charade (TRIER + EME)
- **20A** — ACERBITY: container (ACERY containing BIT)
- **21D** — BELLINI: charade (BELL + IN + I)
- **22D** — TEASER: charade (TR + EASER)
- **23A** — POTTIER: anagram (AGRIPOT - AG + TIER)
- **24D** — TACIT: reversal (TICAT → TACIT)
- **25A** — SPLURGE: container + reversal (SURGE containing LP reversed)
- **25D** — SOLVE: charade (SO + LVE)
- **26A** — POCKET BILLIARDS: charade (POCKET + BILL + I + ARDS)
- **27A** — ROTTER: charade (ROT + TER)
- **28A** — BEWILDER: container (BEWIDER containing L from "left")

**Known issue (puzzle 29453 — DO NOT MODIFY 29453 DATA):**
- **9D** — has wrong apostrophe and wrong transform type. Not yet fixed.

**Validator changes made during 29147/29463 work:**
- `_check_container`: now handles 3+ predecessors (multiple inner pieces concatenated via permutations)
- `_find_consumed_predecessors`: now skips predecessors already consumed by intermediate dependent transforms
- `_check_reversal`: now strips non-alpha characters (handles multi-word answers like TO ORDER)
- `_check_substitution`: new check — result must be same length as input, differing by exactly one letter
- Added `substitution` to VALID_TRANSFORM_TYPES, VALID_INDICATOR_TYPES, and DEPENDENT_TRANSFORM_TYPES
- Added `abbreviation_scan` to VALID_STEP_TYPES and STEP_REQUIRED_FIELDS
- Added `inner_c` and `inner reversed` to roleDisplayNames in render_templates.json
- Added many entries to CRYPTIC_ABBREVIATIONS dictionary

**Process:** Two-phase approach: (1) Solve as AI expert with clue+definition+answer, (2) Encode as training metadata. Hints teach Times conventions (the macro-level checks become the hints).

### Security Hardening — COMPLETE
Baseline security implemented (see SPEC.md Section 15):
- **IS_PRODUCTION flag** — `os.environ.get("VERCEL")` gates debug features
- **Stack trace suppression** — production API errors return message only, tracebacks logged server-side
- **Server-info disabled in production** — `/server-info` returns `{}` on Vercel
- **XSS prevention** — `escapeHTML()` helper applied to all `innerHTML` in `crossword.js`
- **HMAC session signing** — client-carried sessions signed with SHA256, verified with constant-time comparison
- **Secure file uploads** — `secure_filename()` on all uploaded filenames

Remaining: rate limiting (Phase 5).

### User Authentication — COMPLETE
Supabase Auth with Google OAuth implemented (Phase 4):
- **Google OAuth** via Supabase Auth — handles token storage, refresh, session management
- **`profiles` table** — FK to `auth.users`, stores `role` column (`admin`/`user`), auto-created by trigger on sign-up
- **`auth.py`** — `get_current_user()` verifies JWT (HS256), looks up role via service role client (bypasses RLS). `@require_admin` decorator on protected routes.
- **`auth.js`** — Frontend module: Supabase JS client via CDN, `onAuthStateChange` listener, `updateUI()` shows/hides admin elements (Import tab, delete buttons)
- **Protected routes** — `POST /upload`, `DELETE /puzzles/<>/<>`, `POST /puzzles/<>/<>/answers` require admin JWT
- **Trainer is public** — no auth required for `/trainer/*` routes
- **`/auth/me`** — returns `{user: {email, role}}` or `{user: null}` for current session
- **Admin promotion** — manual SQL: `UPDATE profiles SET role = 'admin' WHERE email = '...';`

### Non-Linear Step Completion — COMPLETE
All pre-assembly steps available simultaneously. Assembly gated on all prior steps complete. `step_index` repurposed as expanded-step pointer. New `select_step` UI action for switching steps. Four visual states in step list rendering.

### Assembly Coaching Rework — IN PROGRESS
Reworking all assembly coaching text to read as coherent, flowing guidance from an expert teacher — not disconnected robotic steps. Each clue type gets a dedicated coaching template that connects the prior steps to the assembly as one natural paragraph.

**Principle:** Fidelity over efficiency. Each clue type deserves its own template rather than sharing generic text that reads mechanically.

**Completed:**
- **Simple anagram** — Dedicated `straightAnagramCoaching` template in `render_templates.json`. For clues with exactly one literal word → anagram (e.g. 12A SEMINAR), the student sees a single flowing paragraph: "You found the anagram indicator — notice you have '{word}', a {n}-letter word adjacent to the indicator. Now rearrange {WORD} into a {n}-letter word meaning '{definition}'." No separate definition line, no transform prompts, no fail message — just coaching text and letter boxes. See 12A as the reference example.

**TODO — Simple indicator-based clues (dedicated coaching flow, no transforms):**
- Simple container — indicator + outer + inner, no transforms needed
- Simple hidden word — indicator + source text, answer is literally inside
- Simple reversal — indicator + word, just reverse it
- Simple deletion — indicator + word, remove letters

**TODO — Clues with transforms (full assembly machinery: fail message, transform prompts, combined check):**
- Container with transforms — parts need synonyms/abbreviations before inserting
- Charade with transforms — parts need synonyms/abbreviations before joining
- Compound anagram — multiple parts (some transformed) → anagram
- Deletion with transforms — base word needs transformation before deletion

**TODO — Review existing:**
- Double definition — review current flow
- Reversal with transforms — review if needed

**IMPORTANT: Puzzle 29453 is the verified reference. It is locked in Supabase (`training_locked = TRUE`) and 100% read-only. The upload script and all store write methods refuse to modify locked puzzles. Use `python3 lock_puzzle.py --unlock 29453` only if you genuinely need to fix data.**

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch

To switch work between branches, cd to the appropriate directory.
