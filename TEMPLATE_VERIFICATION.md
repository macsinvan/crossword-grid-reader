# Template Verification for Step Menu Implementation

## Purpose
Verify that both clue metadata templates and render templates have everything needed to implement the step menu overview feature.

## Template Storage Locations

**Clue Step Templates (Schema Definitions):**
- **Authoritative Source:** `clue_step_templates.json`
- **Purpose:** Capture data from the clue in a form that can be used by the render template to present the step. Has NO knowledge of presentation/process. ONLY has knowledge of the clue itself.
- **Contents:** Required/optional fields that extract clue-specific data (indices, text, reasoning)
- **Used in:** Supabase `clues.training_metadata` → `steps[]`
- **We control this:** This is our custom schema, optimized for data extraction from clues
- **Documentation:** SPEC.md Appendix B, CLAUDE.md line 73

**Render Templates (EXTERNAL TO CODE):**
- **Authoritative Source:** `render_templates.json`
- **Purpose:** Generic presentation logic - phases, input modes, prompts. Defines HOW to present each step type.
- **Contents:** Phases, input modes, action prompts, panel formatting for each template type
- **Used by:** `training_handler.py` loads and uses these templates
- **Documentation:** SPEC.md Section 5.1, CLAUDE.md

**Display Flow Templates:**
- **Location:** `step_display_templates.py` → `CONTAINER_TEMPLATES` dictionary
- **Purpose:** Defines sub-steps for complex templates (e.g., container, charade)
- **Documentation:** CLAUDE.md line 72

## Verification Process
For each step type, verify:
1. **Clue Metadata Template** - What fields exist in training metadata
2. **Render Template** - What phases are defined in training_handler.py
3. **Display Flow** - What sub-steps are defined in step_display_templates.py (if applicable)
4. **Menu Title Generation** - How to generate human-readable menu title
5. **Gaps** - What's missing or unclear

---

## 1. standard_definition

### 1.1 Clue Metadata Template (training metadata)
**Location:** `clue_data["steps"][i]` where `type == "standard_definition"`

**Fields Present:**
- `type`: "standard_definition"
- `expected`: {indices, text} - The definition words
- `position`: "start" | "end" - Where in clue
- `explicit`: boolean - Whether obvious

**Documentation:** CLAUDE.md lines 190-192

**Status:** ✅ Fields documented

### 1.2 Render Template (training_handler.py)
**Location:** `STEP_TEMPLATES["standard_definition"]` (line 117)

**Phases Defined:**
1. "select" - User taps definition words
   - inputMode: tap_words
   - actionPrompt: "Tap the definition words"
2. "teaching" - Show what was found
   - inputMode: none
   - Shows: "DEFINITION FOUND: {definition_text}"

**Documentation:** SPEC.md line 562: "select → teaching"

**Status:** ✅ Phases documented

### 1.3 Display Flow (step_display_templates.py)
**Does standard_definition have sub-steps?** NO

Standard_definition is a single atomic step. It does NOT expand into multiple teaching sub-steps.

**Status:** ✅ No display_flow needed (atomic step)

### 1.4 Menu Title Generation
**Required:** "Identify Definition"

**How to generate:**
- Simple mapping: type "standard_definition" → title "Identify Definition"
- No dynamic parts needed (unlike container which needs indicator text)

**Status:** ✅ Clear how to generate

### 1.5 Gaps
- [ ] None identified for standard_definition

### 1.6 Acceptance Criteria for 17D (ASWAN DAM)
**Clue:** "Embankment architect lengthened with cob? (5,3)"
**Answer:** ASWAN DAM

**Step 1 metadata:**
```json
{
  "type": "standard_definition",
  "expected": {"indices": [0], "text": "Embankment"},
  "position": "start",
  "explicit": true
}
```

**Expected menu item:**
```
⭕ 1. Identify Definition
```

**When user clicks:**
- Navigate to standard_definition step detail
- Show phase 1: "Tap the definition words"
- User taps "Embankment"
- Show phase 2: "DEFINITION FOUND: Embankment"
- Return to menu with: ✓ 1. Identify Definition

**Status:** ✅ Acceptance criteria clear

---

## Summary for standard_definition
- [x] Clue metadata template documented
- [x] Render template documented
- [x] Menu title generation clear
- [x] Acceptance criteria defined
- [x] No gaps identified

**VERIFIED:** standard_definition is ready for step menu implementation
