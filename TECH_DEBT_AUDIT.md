# Technical Debt Audit - Grid Reader

## Summary

The codebase has evolved to include Supabase integration (Phase 1), but retains legacy code from the cryptic-trainer integration that will be replaced in Phase 2. This audit identifies files and code sections to clean up.

---

## 1. LEGACY TRAINER PROXY CODE (High Priority - Remove in Phase 2)

### `crossword_server.py` - Lines 383-708

**Status**: DEPRECATED - Will be replaced by `/solve/*` endpoints in Phase 2

**Functions to remove**:
- `find_annotated_puzzle_file()` - Looks for pre-annotated JSON files
- `load_annotated_puzzle()` - Loads annotated puzzle data
- `import_puzzle_to_trainer()` - Imports to external trainer DB
- `find_clue_in_annotated_data()` - Searches annotated data

**Endpoints to remove**:
- `POST /trainer/import-puzzle` - Imports to external trainer
- `GET /trainer/check-puzzle` - Checks for annotations
- `POST /trainer/start` - Proxies to cryptic-trainer:5001
- `POST /trainer/input` - Proxies user input
- `POST /trainer/continue` - Proxies continue action

**Dependencies to remove**:
- `import requests` (line 388) - Only used for trainer proxy
- `TRAINER_API_BASE` constant (line 390)
- `ANNOTATED_PUZZLES_DIR` constant (line 392-393)

**Recommendation**: Remove ~330 lines of code when Phase 2 `/solve/*` endpoints are implemented.

---

## 2. LEGACY TRAINER UI (High Priority - Remove in Phase 2)

### `static/trainer.js` - Entire file (574 lines)

**Status**: DEPRECATED - Ported from React TemplateTrainer.tsx

**What it does**:
- Complex state machine for step-by-step guided solving
- Renders word highlighting, multiple choice, teaching panels
- Manages session state with cryptic-trainer server

**Why remove**:
- Requires external cryptic-trainer server on port 5001
- Requires pre-annotated clue data
- State synchronization issues between browser and server
- Overly complex for what will become a simpler LLM-powered solve

**Recommendation**: Delete entirely when Phase 2 is complete. Replace with simple solve UI.

---

## 3. LEGACY TRAINER UI HOOKS (Medium Priority)

### `static/crossword.js` - Trainer-related code

**Functions to remove**:
- `openTrainer()` method - Opens trainer modal
- `closeTrainer()` method - Closes modal
- `handleTrainerComplete()` method - Applies solved answer

**Event listeners to remove**:
- `solve-btn` click handler
- `trainer-close` click handler

**HTML elements to remove** (in `templates/index.html`):
- `#trainer-modal` (lines 103-113)
- `#trainer-container`
- `#trainer-clue-number`
- `#trainer-clue-text`
- `#trainer-close` button

**CSS to remove** (in `static/crossword.css`):
- `.trainer-*` styles (lines 402-589) - ~180 lines

**Recommendation**: Remove after Phase 2 when new solve UI is ready.

---

## 4. REDUNDANT FILE STORAGE (Low Priority)

### `puzzle_store.py` - Local file-based storage

**Status**: FALLBACK ONLY - Supabase is primary

**Current behavior**: Auto-falls back to local storage if Supabase not configured

**Options**:
1. **Keep as fallback** (recommended for now) - Useful for offline dev
2. **Remove entirely** - Once Supabase is proven stable in production

**Recommendation**: Keep for Phase 3 Vercel deployment, then evaluate removal.

---

## 5. UNUSED IMPORTS & DEAD CODE

### `crossword_server.py`

**Potentially unused**:
- `shutil` import (line 19) - Only used if PDF storage enabled
- `Path` from pathlib (line 20) - Verify usage

### `static/crossword.js`

**Unused class properties**:
- `this.templateTrainer` (line 22) - Set but usage unclear
- `this.trainerWordData` (line 23) - Set but usage unclear

---

## 6. DOCUMENTATION SYNC ISSUES

### `README.md` - Needs update

**Outdated sections**:
- Quick Start - Missing `.env` setup for Supabase
- "Guided Solving" section - Still references cryptic-trainer requirement
- API Endpoints - Missing `/status` endpoint
- Missing: Supabase setup instructions

### `PLAN.md` - OK but could trim

**Consider removing**:
- Detailed cryptic-trainer architecture docs (no longer needed)

---

## 7. FILES TO DELETE (Future)

After Phase 2 completion:

| File | Lines | Reason |
|------|-------|--------|
| `static/trainer.js` | 574 | Replaced by new solve UI |
| `puzzle_store.py` | 213 | Optional - keep as fallback |

After Phase 2 in `crossword_server.py`:

| Section | Lines | Reason |
|---------|-------|--------|
| Trainer proxy section | ~330 | Replaced by /solve/* endpoints |

After Phase 2 in `static/crossword.css`:

| Section | Lines | Reason |
|---------|-------|--------|
| `.trainer-*` styles | ~180 | No longer needed |

---

## 8. RECOMMENDED CLEANUP ORDER

### Phase 2 Start (Before adding new code):
1. Document what trainer code will be replaced
2. Keep trainer code functional until replacement ready

### Phase 2 End (After /solve/* works):
1. Delete `static/trainer.js`
2. Remove trainer proxy code from `crossword_server.py`
3. Remove trainer modal from `templates/index.html`
4. Remove `.trainer-*` CSS
5. Remove trainer hooks from `crossword.js`
6. Update README.md and docs

### Phase 3+ (Production):
1. Evaluate removing `puzzle_store.py` fallback
2. Final documentation cleanup

---

## 9. ESTIMATED CLEANUP IMPACT

| Metric | Before | After Phase 2 Cleanup |
|--------|--------|----------------------|
| `crossword_server.py` | 715 lines | ~400 lines |
| `static/trainer.js` | 574 lines | 0 (deleted) |
| `static/crossword.css` | ~933 lines | ~750 lines |
| `static/crossword.js` | ~1000 lines | ~900 lines |
| Total JS/CSS/Python | ~3200 lines | ~2050 lines |

**~35% code reduction** when Phase 2 cleanup is complete.

---

## 10. IMMEDIATE ACTIONS (No Breaking Changes)

These can be done now without breaking functionality:

1. **Add `.DS_Store` cleanup**: `git rm --cached .DS_Store` (if tracked)
2. **Update README.md**: Add Supabase setup instructions
3. **Add code comments**: Mark trainer code as "DEPRECATED - Phase 2"
4. **Clean up `Times_PDF/`**: Should be in .gitignore (verify)

---

## Next Steps

1. Review this audit
2. Decide whether to do immediate cleanups
3. Proceed with Phase 2 implementation
4. Clean up legacy code after Phase 2 is working
