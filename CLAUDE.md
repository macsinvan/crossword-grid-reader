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
1. `SPEC.md` - **Technical Specification** (reproducible app spec)

**All design documents MUST be in the working directory and tracked in the repo.**

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

**STATELESS CLIENT ARCHITECTURE** (See SPEC.md Section 4.4 for complete explanation)
The trainer UI (`trainer.js`) is a **thin, stateless rendering layer with ZERO state**:
- ALL state lives on the server (session dict in `training_handler.py`)
- Client receives a complete `render` object and displays it - nothing more
- Client makes NO decisions, has NO logic, stores NO variables
- User interactions call server endpoints which return updated `render` objects
- Client has no local variables for: selections, input values, visibility flags, progress, etc.
- If you're tempted to add `this.foo = ...` in trainer.js, STOP - it belongs on the server
- The client is a pure view layer—it only knows how to render what the server tells it

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

| File | Purpose |
|------|---------|
| `crossword_server.py` | Flask server (port 8080) |
| `training_handler.py` | Teaching mode logic: loads templates, get_render(), handle_input() |
| `clue_step_templates.json` | **EXTERNAL TO CODE** - Clue step template schemas (WHAT data from clue) |
| `render_templates.json` | **EXTERNAL TO CODE** - Render templates (HOW to present steps) |
| `step_display_templates.py` | Display flow templates for complex step types (container, charade) |
| `clues_db.json` | Pre-annotated clue database (30 clues with template metadata) |
| `static/trainer.js` | Stateless trainer UI (renders server state) |
| `static/crossword.js` | Grid UI, keyboard nav, localStorage persistence |
| `puzzle_store_supabase.py` | Supabase database storage |
| `puzzle_store.py` | Local file-based storage (fallback) |
| `pdf_processor.py` | PDF parsing, grid/clue extraction |
| `crossword_processor.py` | Grid structure detection |
| `templates/index.html` | Web UI (bump `?v=N` for cache busting) |

## Architecture

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI, persistence)
     ├── trainer.js (stateless teaching UI)
     ├── crossword_server.py (Flask)
     │        │
     │        ├── training_handler.py (teaching logic)
     │        ├── puzzle_store_supabase.py → Supabase PostgreSQL
     │        └── puzzle_store.py → Local files (fallback)
     │
     └── clues_db.json (30 annotated clues)
```

### Database Backend
The app auto-detects storage backend:
- **Supabase** (preferred): If `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in `.env`
- **Local files**: Falls back to `puzzles/` directory if Supabase not configured

A status indicator (green LED = Supabase, yellow = local) shows in the header.

## Teaching Mode (Template-Based Step Display)

### Architecture
Server-driven rendering with **thin stateless client**:

**CRITICAL: Client Has ZERO State**
- `trainer.js` is a dumb rendering layer with NO local state
- ALL state lives on server in `training_handler._sessions[clue_id]`
- Client only renders what server sends, sends input back, repeats
- No client-side variables for: selections, answers, visibility, progress

**Flow:**
1. User clicks "Solve" → `crossword.js` calls `/trainer/start` with clue_id
2. Server loads clue with pre-annotated `steps` array from `clues_db.json`
3. `training_handler.py` merges raw step + STEP_TEMPLATE → complete `render` object
4. `trainer.js` displays exactly what `render` specifies (no decisions, no logic)
5. User input sent to server → validated via `handle_input()` → new `render` returned
6. On completion, answer auto-applies to grid

### Template System: Two-Layer Architecture

**CRITICAL:** Each clue step template (metadata) maps 1:1 to a render template (code).

**LAYER 1: Clue Step Template (clues_db.json)** - Clue-specific data only:
- Step type identifier
- Which words from THIS clue to interact with (indices)
- Expected answers for THIS clue
- Reasoning text for THIS clue
- Schema compatible with render template

**LAYER 2: Render Template (training_handler.py)** - Generic presentation logic:
- Accepts clue step data as input
- Defines how to present in teaching mode
- Phases to step through
- Input modes (tap_words, text, multiple_choice, none)
- Action prompts
- Teaching panel formatting

**Example Mapping:**
```
Clue Step Template:   {"type": "synonym", "fodder": {...}, "result": "DRIVEL"}
                                ↓ 1:1 mapping
Render Template:      STEP_TEMPLATES["synonym"] = {phases: [fodder, result, teaching]}
```

**Available Render Templates (19 in training_handler.py):**
- `standard_definition` - Definition identification
- `synonym` - Word → synonym
- `abbreviation` - Word → abbreviation
- `literal` - Word used as-is
- `literal_phrase` - Phrase read literally
- `anagram` - Rearrange letters
- `reversal` - Reverse word
- `deletion` - Remove letter(s)
- `letter_selection` - First/last/middle letters
- `hidden` - Hidden word in phrase
- `container_verify` - One part inside another
- `charade_verify` - Combine parts in order
- `double_definition` - Two definitions
- `container` - Container clue discovery
- `clue_type_identify` - Identify clue type
- `wordplay_overview` - Wordplay explanation
- `deletion_discover` - Deletion discovery
- `alternation_discover` - Alternation discovery
- `connector` - Linking words

### Step Types (in clues_db.json)
- `standard_definition` - Definition identification
- `charade` - Parts assembled in sequence
- `anagram` - Letters rearranged
- `container` - One word inside another
- `reversal` - Word reversed
- `deletion` - Letter(s) removed
- `hidden` - Answer hidden in clue text
- `double_definition` - Two definitions
- `transformation_chain` - Multiple operations

### Clue Metadata Format
```json
{
  "id": "times-29453-4a",
  "clue": {"number": "4A", "text": "...", "answer": "REPROACH"},
  "words": ["Twit", "copying", "antique", ...],
  "steps": [
    {
      "type": "standard_definition",
      "expected": {"indices": [0], "text": "Twit"},
      "position": "start"
    },
    {
      "type": "charade",
      "template": "charade_with_parts",
      "parts": [
        {
          "fodder": {"indices": [1, 2], "text": "copying antique"},
          "result": "REPRO",
          "type": "synonym",
          "reasoning": "A repro is a reproduction"
        }
      ],
      "result": "REPROACH",
      "assembly": "REPRO + ACH = REPROACH"
    }
  ]
}
```

## Step Menu Overview (Completed)

When clicking "Solve", users see a step menu with inline expansion:

**Display:**
- All steps shown as clickable menu items with status indicators (⭕ pending / ✓ completed)
- Answer boxes at top (always visible, editable for hypothesis testing)
- Reveal button for quick access to full solution

**Interaction:**
- Clicking a step expands it inline (no navigation away)
- Expanded section shows clue words as clickable elements
- Correct selections turn green, incorrect flash red
- Auto-generated contextual hints available via 💡 button
- Completion auto-detected when all expected words selected

**Completion Display:**
- Step collapses automatically after 500ms
- Title replaced with result: "DEFINITION: {text} found at the {position} of the clue"
- Status icon changes to ✓
- Step styled with green background/border

**Template Expansion:**
Templates with multiple atomic steps expand automatically:
- `insertion_with_two_synonyms` → 4 steps (indicator, outer literal, inner synonym, assembly)
- `insertion_with_one_synonym_outer` → 4 steps
- `insertion_with_charade_inner` → Multiple steps
- `charade_with_parts` → Steps for each part + assembly
- `anagram_with_fodder_pieces` → Fodder identification + anagram
- `transformation_chain` → Step for each transformation

## TODO

### Phase 6: Automated Clue Annotation (Future)
- [ ] Build solver that takes cold clues (+ optional answer) and generates metadata
- [ ] Input parser: Extract clue components, identify indicators, parse enumeration
- [ ] Template generator: Map parsed components to 13 step templates
- [ ] Synonym/abbreviation lookup: Build comprehensive dictionaries
- [ ] Assembly validator: Verify generated steps produce correct answer
- [ ] Confidence scoring: Rank generated annotations by certainty
- [ ] Human review UI: Allow manual refinement of auto-generated annotations
- [ ] Batch processing: Annotate entire puzzle sets automatically

## Current State

### Completed Features
- ✅ Supabase integration (Phase 1)
- ✅ Template-based step display system (Phase 2)
- ✅ Step menu overview with inline expansion (Phase 2.1)
- ✅ Interactive word selection with validation
- ✅ Auto-completion detection and clean result display
- ✅ Template expansion for complex step types
- ✅ Dynamic hint generation
- ✅ 30 clues fully annotated with templates
- ✅ Mobile responsive grid
- ✅ Progress persistence (localStorage)
- ✅ Auto-apply answers to grid
- ✅ Reveal button for quick solution access

### Data
- 30 annotated clues from Times puzzle 29453
- All step types have working templates
- clues_db.json auto-reloads on change

## Mobile Design Principles

**Grid uses CSS Grid with `1fr` units, NOT fixed pixel sizes.**

Key implementation:
- `crossword.js` sets `grid-template-columns: repeat(N, 1fr)`
- Cells use `aspect-ratio: 1` to stay square
- Mobile breakpoint at 600px uses `width: calc(100vw - 26px)`
- Font sizes use `clamp()` for fluid scaling

See `SPEC.md` Section 10 for full details.

## Storage

### Supabase Tables
- `publications` - Times, Guardian, Telegraph, Express
- `puzzles` - Primary entity (grid + metadata)
- `clues` - Belong to puzzles
- `user_progress` - Per-puzzle progress tracking

### Local Fallback
Puzzles stored in `puzzles/{series}/{number}/`:
- `puzzle.json` - grid, clues
- `original.pdf` - source PDF
- `answers.json` - optional answers

## Environment Variables
Create `.env` file (see `.env.example`):
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

## Common Commands
```bash
# Start server
python3 crossword_server.py

# Git workflow
git status && git diff
git add <files> && git commit -m "msg"
git push

# Validate clues_db.json
python3 -c "import json; json.load(open('clues_db.json')); print('Valid')"
```

## Cache Busting
When changing JS/CSS files, bump version in `templates/index.html`:
```html
<script src="/static/crossword.js?v=21"></script>
```

## Development Roadmap

### Phase 1: Supabase Database Integration ✅ Complete
### Phase 2: Template-Based Teaching Mode ✅ Complete
### Phase 3: Vercel Deployment (Next)
- Serverless Flask on Vercel
- Environment variables for keys

### Phase 4: User Authentication
- Supabase Auth (Google OAuth + email/password)
- Row-level security

### Phase 5: Multi-User Features
- Rate limiting, analytics, polish

See `PLAN.md` for full roadmap.

## Worktrees
This repo uses git worktrees:
- `/Users/andrewmackenzie/Desktop/Grid Reader` - main branch
- `/Users/andrewmackenzie/Desktop/Grid Reader/upbeat-driscoll` - upbeat-driscoll branch

To switch work between branches, cd to the appropriate directory.
