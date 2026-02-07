# Technical Debt Audit - Grid Reader

**Last Updated**: Post-Blueprint refactoring (trainer_routes.py extracted)

---

## 1. Unused Code in trainer_routes.py

**Functions that could be removed** (only used for external file import):
- `find_annotated_puzzle_file()`
- `load_annotated_puzzle()`
- `find_clue_in_annotated_data()`

**Endpoints to evaluate:**
- `POST /trainer/import-puzzle` — may still be useful for importing new puzzles
- `GET /trainer/check-puzzle` — may still be useful

**Decision:** Keep for now — they support importing new annotated puzzles.

---

## 2. Unused Code in training_handler.py

Functions defined but not called from server:
- `get_session()` — useful for debugging
- `clear_session()` — useful for cleanup
- `get_all_learnings()` — useful for reveal functionality

**Decision:** Keep for potential future use.

---

## 3. Dead Files

| File | Status | Notes |
|------|--------|-------|
| `puzzle_store.py` | Unused | Supabase is required, no fallback. Can be deleted. |

---

## 4. Pending: Supabase Steps Column

Steps currently loaded from local `clues_db.json`. Future: add `steps` JSONB column to Supabase `clues` table so step data lives in the cloud.

Not blocking — current implementation works.

---

## 5. Documentation Gaps

- `README.md` Quick Start section could mention `.env` setup more prominently
- Consider deleting `TEMPLATE_VERIFICATION.md` if no longer used for active work

---

## 6. Code Metrics

| File | Lines | Status |
|------|-------|--------|
| `crossword_server.py` | ~380 | Active (infrastructure only) |
| `trainer_routes.py` | ~580 | Active (Blueprint: /trainer/*) |
| `training_handler.py` | ~2133 | Active (teaching logic) |
| `trainer.js` | ~574 | Active |
| `crossword.js` | ~1000 | Active |
| `puzzle_store_supabase.py` | ~270 | Active |
| `puzzle_store.py` | ~213 | Unused |

**Total Python**: ~3600 lines | **Total JS**: ~1600 lines

For current architecture, see SPEC.md §3 and CLAUDE.md.
