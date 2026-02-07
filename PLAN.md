# Plan: Grid Reader → Public Multi-User Web App

## Target Stack
- **Backend**: Flask on Vercel (serverless functions)
- **Database**: Supabase (PostgreSQL) — required, no local fallback
- **Auth**: Supabase Auth
- **Frontend**: Static HTML/JS (current) served from Vercel

---

## Incremental Phases

### Phase 1: Supabase Database Integration ✅ Complete
Replaced file-based storage with Supabase PostgreSQL.

See SPEC.md §9 for database schema, SPEC.md §3 for architecture.

### Phase 2: Interactive Teaching Mode ✅ Complete
Ported cryptic-trainer teaching system locally. No AI/LLM — uses pre-annotated step data.

See SPEC.md §4–6 for teaching mode architecture, template system, and step menu.

### Phase 3: Vercel Deployment (Next)
Deploy to Vercel as serverless Flask app.

**Changes:**
- Add `vercel.json` configuration
- Adapt Flask app for serverless (stateless)
- Environment variables for Supabase keys
- Static assets served from Vercel

**Validation:** App accessible at public Vercel URL

### Phase 4: User Authentication
Add Supabase Auth for user accounts.

**Changes:**
- Add sign up / login UI (Google OAuth + email/password)
- Progress tied to authenticated user
- Row-level security in Supabase
- Guest mode for trying without account

**Validation:** Login works, progress syncs across devices

### Phase 5: Multi-User Features & Security
Polish for public release.

**Changes:**
- Rate limiting on `/trainer/*` endpoints
- Input validation / sanitization
- Usage tracking / analytics
- Error handling improvements

**Validation:** Security review, load testing

---

## Publication-Based Architecture (Future)

The app will use a **publication-focused** home page — users select their publication first, then access features.

**User Flow:**
```
HOME → Select Publication (Dojo) → Publication Page → Training/Solver/Manual Entry
```

**Publications:** Times, Guardian, Telegraph, Express — each with strictness rules, named setters, and house style.

**Design Decisions:**
- Publication-based navigation (users follow specific publications)
- Port `PUBLICATIONS` data structure and `DojoRules` for publication-specific solving hints
- Port external blogger links (community resources)
- Preserve setter metadata for teaching context

---

## Key Architecture Change: Puzzle-Based vs Clue-Based

**cryptic-trainer (old):** Clue-based — individual clues in a flat list, no puzzle context.

**Grid Reader (new):** Puzzle-based — puzzles are the primary entity, clues exist within puzzle context. See SPEC.md §9 for data model.

**Benefits:** Natural cross-letter support, puzzle-level progress, PDF import workflow, coherent UX.

**Migration:** cryptic-trainer clues map `times-29453-1a` → puzzle `times/29453`, clue `1A`. Step templates unchanged.

---

## Key Assets to Port from cryptic-trainer

| Asset | Purpose |
|-------|---------|
| `PUBLICATIONS` + `DojoRules` | Publication metadata and solving rules |
| `EXTERNAL_BLOGGERS` | Community resource links |
| `CRYPTIC_GLOSSARY` | Indicators by type, abbreviations |
| `ABBREVS` / `SYNONYMS` / `PHRASES` | Standard dictionaries |

**Design Principles to Preserve:**
1. Stateless client (SPEC.md §4.4)
2. Constraint-first validation — no AI guessing
3. Hypothesis-driven solving — definition → hypothesis → verify wordplay
4. Two-path verification — answer must work via definition AND wordplay

---

## Decisions Made

- **Auth method**: Both Google OAuth and email/password
- **Pricing model**: TBD (decide before Phase 5)

---

## Supabase Project

**Project URL:** `https://tycvflrjvlvmsiokjaef.supabase.co`
**Anon Key:** `sb_publishable_ZJKuj06UILTJewkA_gy2xg_U7fSYEwr`

Note: Service role key needed for server-side operations (get from Supabase dashboard → Settings → API)
