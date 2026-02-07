# Trainer Redesign

## Goal

The trainer code (training_handler.py: 1,865 lines, trainer_routes.py: 803 lines, trainer.js: 1,753 lines) has grown organically and is full of type-specific branching that belongs in configuration. If the clue metadata and render templates are designed correctly, the trainer engine should be ~200 lines — a simple sequencer.

This plan starts from first principles: what does the metadata need to look like?

---

## Part 1: The Natural Solve Sequence

Before touching code or templates, we need to establish what the student actually does when solving a clue. Everything flows from this.

### Example: 17D — "Embankment architect lengthened with cob?" (5,3) → ASWAN DAM

A teacher would guide a student through these steps, in this order:

1. **What type of clue is this?**
   There are instruction words ("lengthened"), a clear definition at the start, and wordplay in the rest. Standard cryptic clue.

2. **Find the definition.**
   "Embankment" at the start. It's defining a famous embankment — a dam.

3. **Spot the indicator.**
   "Lengthened" — this tells you one word is being stretched by putting letters inside it. That's a container/insertion.

4. **Identify the outer word.**
   "Architect" — the word being lengthened. Which architect? Robert Adam → ADAM.

5. **Identify the inner word.**
   "Cob?" — what's being inserted. A cob is a male swan → SWAN.

6. **Put it together.**
   SWAN goes inside ADAM: A + SWAN + DAM = ASWAN DAM. That's a famous embankment on the Nile. It works.

7. **Write the answer.**
   ASWAN DAM — 5,3 — matches the enumeration, matches the definition. Done.

### What this tells us about metadata

Each numbered step above is one interaction the student has. The metadata must represent exactly these steps — no more, no less. Each step needs:

- **What the student sees**: which words are available to tap, what question is being asked
- **What the student does**: tap words, type text, or choose from options
- **What counts as correct**: the expected answer
- **What the student learns on success**: the teaching insight
- **What help is available**: hint if they're stuck

The metadata should be a flat, ordered list of steps. Each step is self-contained. The engine reads step N, presents it, checks the answer, teaches, and moves to step N+1. That's it.

### Key insight: steps are the atoms

The current metadata has two levels — a `steps` array where each step is a high-level cryptic device (standard_definition, container), then the render templates and menu_items expand these into sub-steps. This indirection is the root cause of the complexity. The engine has to know how to expand each type differently.

If the metadata simply listed the actual student-facing steps in order, the engine wouldn't need to know anything about cryptic crossword types at all.

### Design constraint: lightweight clue metadata

There will be thousands of clues. The per-clue metadata must be as light as possible. This means:

- **Clue metadata carries only what is unique to that specific clue**: which words, which indices, expected answers, clue-specific hints.
- **Everything generic to a step type lives in render templates**: instructions, teaching text, technique explanations, input modes, UI layout.
- **The clue step says WHAT (data), the render template says HOW (presentation).** A step in the clue metadata is a type reference plus the minimum data the template needs to operate on this particular clue.
- **No duplication**: if 500 synonym steps all need the same instruction text, that text exists once in the render template, not 500 times in clue metadata.

---

## Part 2: New Metadata Schema (17D)

### The metadata

```json
{
  "id": "times-29453-17d",
  "clue": "Embankment architect lengthened with cob?",
  "enumeration": "5,3",
  "answer": "ASWAN DAM",
  "words": ["Embankment", "architect", "lengthened", "with", "cob"],
  "clue_type": "standard",
  "difficulty": {
    "definition": "medium",
    "wordplay": "hard",
    "overall": "hard"
  },
  "steps": [
    {
      "type": "definition",
      "indices": [0],
      "position": "start",
      "hint": "A famous structure on the Nile river"
    },
    {
      "type": "container_indicator",
      "indices": [2],
      "hint": "'Lengthened' suggests stretching a word by putting letters inside it"
    },
    {
      "type": "synonym",
      "role": "outer",
      "indices": [1],
      "result": "ADAM",
      "hint": "Think of a famous British architect"
    },
    {
      "type": "synonym",
      "role": "inner",
      "indices": [4],
      "result": "SWAN",
      "hint": "What kind of bird is a cob?"
    },
    {
      "type": "assembly",
      "parts": ["ADAM", "SWAN"],
      "result": "ASWAN DAM",
      "method": "container"
    },
    {
      "type": "answer",
      "expected": "ASWAN DAM"
    }
  ]
}
```

### Design principles applied

- **Flat steps**: 6 steps matching the 6 student interactions. No nesting, no expansion.
- **No derived text**: `indices: [2]` is enough — engine reads `words[2]`. No redundant `.text` fields.
- **No `template` field**: step `type` maps directly to a render template. No expansion instructions.
- **No `reasoning`**: replaced by `hint` which serves the student directly.
- **`role` on parts**: `"outer"` / `"inner"` tells the assembly step which part goes where.
- **Structural assembly**: `parts` + `method` instead of a pre-baked display string.
- **Connectors are implicit**: any word index not referenced by any step is a connector (e.g. "with" at index 3).
- **Difficulty at clue level**: three simple string ratings, no per-step difficulty.

### Step types used

| Type | Fields | Purpose |
|------|--------|---------|
| `definition` | `indices`, `position`, `hint` | Student taps the definition words |
| `container_indicator` | `indices`, `hint` | Student taps the indicator word |
| `synonym` | `role`, `indices`, `result`, `hint` | Student identifies and solves a synonym |
| `assembly` | `parts`, `result`, `method` | Student combines the parts |
| `answer` | `expected` | Student writes the final answer |

---

## Part 3: Render Templates

### Three-tier hint pattern

Every step follows the same hint pattern:

1. **Intro** (always visible): Generic guidance for this step type. How to approach it cold. Same for every clue.
2. **Hint** (hidden, revealed on request): Type-specific narrowing. Lives in the render template, keyed by technique/clue type where relevant.
3. **Solved** (shown on correct answer): Confirms what was found + the clue-specific `hint` from metadata as the teaching payoff.

Wrong taps flash red (already implemented). No text message needed for wrong answers on `tap_words` steps.

### definition

```json
{
  "definition": {
    "inputMode": "tap_words",
    "prompt": "Tap the definition words",
    "intro": "Every cryptic clue contains a straight definition — a word or phrase that means the same as the answer, just as you'd find in a dictionary.\n\nTo spot it, ignore the misleading surface story. Read the start and end of the clue separately — does either phrase describe something specific? Could it be a dictionary entry?",
    "hint": {
      "standard": "This is a standard cryptic clue. The definition is always at the very start or very end, never in the middle.",
      "double_definition": "This is a double definition. Two separate meanings sit side by side — find the first one.",
      "cryptic_definition": "The whole clue is the definition — one playful description with a misleading surface.",
      "and_lit": "The whole clue works as both definition and wordplay simultaneously."
    },
    "expected_source": "indices",
    "onCorrect": "Can you find a word ({enumeration}) meaning '{words}' — {hint}."
  }
}
```

**Variables resolved by engine:**
- `{words}` — joined from `words[i]` for each `i` in step `indices`
- `{enumeration}` — from clue-level `enumeration` field
- `{position}` — from step `position` field
- `{hint}` — from step `hint` field (clue-specific teaching payoff)

**Hint key:** engine uses the clue-level `clue_type` field (e.g. `"standard"`) to select the right hint string.

---

## Current UI (preserve in refactor)

The existing UI works well and must be preserved. Three states captured for 17D:

### State 1: Initial menu (collapsed)
```
┌─────────────────────────────────────────────────┐
│ 17D  Embankment architect lengthened with cob?  │
│      (5,3)                                       │
├─────────────────────────────────────────────────┤
│ [_][_][_][_][_] [_][_][_]    [Check] [Reveal]   │
├─────────────────────────────────────────────────┤
│ Steps to solve:                                  │
│                                                  │
│  ○ 1.   Identify Definition                     │
│  ○ 1.1. Identify Container Indicator             │
│  ○ 1.2. Identify Outer Word                     │
│  ○ 1.3. Identify Inner Word                     │
│  ○ 1.4. Assemble                                │
│                                                  │
│         Click any step to begin                  │
└─────────────────────────────────────────────────┘
```

### State 2: Step expanded (definition, in progress)
```
┌─────────────────────────────────────────────────┐
│  ○ 1.  Identify Definition                      │
│  ┌─────────────────────────────────────────────┐│
│  │ Embankment  architect  lengthened  with  cob ││
│  │                                              ││
│  │ Click on the clue words to identify          ││
│  │ definition.                            💡    ││
│  └─────────────────────────────────────────────┘│
│  ○ 1.1. Identify Container Indicator             │
│  ○ 1.2. Identify Outer Word                     │
│  ...                                             │
└─────────────────────────────────────────────────┘
```
- Clue words shown as tappable chips
- Instruction below the word chips
- Lightbulb icon (💡) for hint access
- Wrong taps flash red, correct taps turn green

### State 3: Step completed (definition, solved)
```
┌─────────────────────────────────────────────────┐
│  ✓ 1.  ┌──────────────────────────────────────┐ │
│         │ 'Embankment' at the start is the     │ │
│         │ definition.                          │ │
│         │                                      │ │
│         │ Can you find a word (5,3) meaning    │ │
│         │ 'Embankment' — a famous structure on │ │
│         │ the Nile river.                      │ │
│         └──────────────────────────────────────┘ │
│  ○ 1.1. Identify Container Indicator             │
│  ...                                             │
└─────────────────────────────────────────────────┘
```
- Green background on completed step
- Check mark replaces circle
- Completion text replaces the interactive area
- Answer boxes at top persist across all steps

### UI elements to preserve
- **Header bar**: clue number, text, enumeration (dark blue)
- **Answer boxes**: letter input grid with word-break gaps, Check/Reveal buttons
- **Step menu**: numbered list with expand-in-place interaction
- **Word chips**: tappable clue words for `tap_words` input mode
- **Hint lightbulb**: reveals type-specific hint on tap
- **Visual feedback**: green highlight on correct, red flash on wrong
- **Completion summary**: green box with teaching text replaces interactive area
- **Progressive disclosure**: steps complete top-down, each revealing more

---

## Implementation Approach: Vertical Slices

Don't design all templates then build all engine code. Instead, implement one step type end-to-end, verify it works in the browser, then move to the next. This catches architecture mistakes early on the simplest step.

### Slice 1: Definition (first)
1. New render template for `definition` (done in Part 3)
2. Convert 17D metadata to new schema (definition step only needs to work)
3. New engine code that handles `definition` step type
4. Client renders it using existing UI patterns
5. Verify in browser: tap "Embankment", see green, see solved message

Other step types (indicator, synonym, assembly, answer) stay on the old code path until definition proves the pattern.

### Slice 2-N: Remaining step types
Each subsequent type follows the same pattern: template → metadata → engine → client → verify. Only proceed to the next slice when the previous one works in the browser.

---

## Status

- [x] Part 1: Natural solve sequence established (17D)
- [x] Part 2: New metadata schema for 17D
- [x] Part 3: Render template — definition
- [ ] Part 3: Render templates — remaining types
- [ ] Slice 1: Definition end-to-end implementation
- [ ] Slice 2-N: Remaining step types
