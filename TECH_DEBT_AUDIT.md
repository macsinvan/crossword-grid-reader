# Technical Debt Audit - Grid Reader

## Summary

**Last Updated**: Phase 2 Implementation Complete

The codebase has evolved through Phase 1 (Supabase) and Phase 2 (Local Teaching Mode). The trainer proxy has been replaced with a local implementation. This audit tracks remaining cleanup.

---

## Phase 2 Status: COMPLETE

### What Was Done:
- ✅ Removed proxy to cryptic-trainer (port 5001 no longer needed)
- ✅ Ported `training_handler.py` locally (2133 lines)
- ✅ Ported `teaching_hints.json` and `clues_db.json`
- ✅ Updated `/trainer/*` endpoints to use local handler
- ✅ Removed `import requests` dependency for trainer
- ✅ Removed `TRAINER_API_BASE` constant

### What Was Kept:
- ✅ `trainer.js` - Still used for interactive teaching UI
- ✅ Trainer modal in `index.html` - Still used
- ✅ `.trainer-*` CSS styles - Still used
- ✅ Trainer hooks in `crossword.js` - Still used

---

## 1. REMAINING CLEANUP (Low Priority)

### `crossword_server.py`

**Functions that could be removed** (not currently used):
- `find_annotated_puzzle_file()` - Only for external file import
- `load_annotated_puzzle()` - Only for external file import
- `find_clue_in_annotated_data()` - Only for external file import

**Endpoints to evaluate**:
- `POST /trainer/import-puzzle` - May still be useful for importing new puzzles
- `GET /trainer/check-puzzle` - May still be useful

**Note**: Keep these for now - they support importing new annotated puzzles.

---

## 2. UNUSED CODE IN training_handler.py

### Functions defined but not called from server:
- `get_session()` - Could be useful for debugging
- `clear_session()` - Could be useful for cleanup
- `get_all_learnings()` - Could be useful for reveal functionality

**Recommendation**: Keep for potential future use or debugging.

---

## 3. REDUNDANT FILE STORAGE (Low Priority)

### `puzzle_store.py` - Local file-based storage

**Status**: FALLBACK ONLY - Supabase is primary

**Current behavior**: Auto-falls back to local storage if Supabase not configured

**Recommendation**: Keep as fallback for offline development.

---

## 4. DOCUMENTATION (Medium Priority)

### `README.md` - Needs update

**Outdated sections**:
- Quick Start - Missing `.env` setup for Supabase
- "Guided Solving" section - References old cryptic-trainer requirement
- Missing: Teaching mode now runs locally

### Files updated for Phase 2:
- ✅ `CLAUDE.md` - Updated with correct architecture
- ✅ `PLAN.md` - Updated Phase 2 section

---

## 5. PENDING: Supabase Steps Column

### `clues` table

**Current**: Steps loaded from local `clues_db.json`

**Future**: Add `steps` JSONB column to Supabase clues table

This would allow:
- Storing step data in the cloud
- Per-puzzle step annotations
- No need for local clues_db.json

**Not blocking**: Current implementation works with local file.

---

## 6. FILES ADDED IN PHASE 2

| File | Lines | Purpose |
|------|-------|---------|
| `training_handler.py` | 2133 | Step template engine |
| `teaching_hints.json` | ~500 | Expert hints for steps |
| `clues_db.json` | ~3300 | 30 pre-annotated clues |

---

## 7. CURRENT ARCHITECTURE

```
Grid Reader (8080)
     │
     ├── crossword.js (grid UI)
     ├── trainer.js (teaching UI)
     ├── crossword_server.py
     │        │
     │        ├── training_handler.py (LOCAL - no proxy)
     │        │        └── clues_db.json (step data)
     │        │
     │        ├── puzzle_store_supabase.py → Supabase
     │        └── puzzle_store.py → Local files (fallback)
```

---

## 8. NEXT STEPS

### Phase 3: Vercel Deployment
- No major cleanup needed before deployment
- Ensure all files are committed

### Future Cleanup (Optional):
1. Add `steps` column to Supabase
2. Update README.md
3. Remove unused import helper functions if not needed

---

## 9. CODE METRICS

| File | Lines | Status |
|------|-------|--------|
| `crossword_server.py` | ~715 | Active |
| `training_handler.py` | 2133 | New (Phase 2) |
| `trainer.js` | 574 | Active (kept) |
| `crossword.js` | ~1000 | Active |
| `puzzle_store_supabase.py` | ~270 | Active |
| `puzzle_store.py` | ~213 | Fallback |

**Total Python**: ~3300 lines
**Total JS**: ~1600 lines
