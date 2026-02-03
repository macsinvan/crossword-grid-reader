# Plan: Grid Reader → Public Multi-User Web App

## Target Stack
- **Backend**: Flask on Vercel (serverless functions)
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth
- **Frontend**: Static HTML/JS (current) served from Vercel

---

## Incremental Phases

### Phase 1: Supabase Database Integration
Replace file-based storage with Supabase PostgreSQL.

**Changes:**
- Create Supabase project with tables: `puzzles`, `clues`, `answers`, `user_progress`
- Replace `puzzle_store.py` with Supabase client
- Store progress server-side (session-based initially)
- Keep localStorage as offline cache

**Validation:** App works locally with Supabase backend

---

### Phase 2: Simple LLM Solve Endpoint
Replace cryptic-trainer with single `/solve` endpoint.

**Changes:**
- Create abstract LLM interface (supports Anthropic + OpenAI)
- Add `/solve` endpoint that calls LLM API
- Simple UI: "Solving..." → answer + explanation
- Delete `trainer.js` and all proxy code
- Environment variable for API key + provider selection

**Validation:** Can solve any clue without cryptic-trainer server

---

### Phase 3: Vercel Deployment (No Auth)
Deploy to Vercel as serverless Flask app.

**Changes:**
- Add `vercel.json` configuration
- Adapt Flask app for serverless (stateless)
- Environment variables for Supabase + LLM keys
- Static assets served from Vercel

**Validation:** App accessible at public Vercel URL

---

### Phase 4: User Authentication
Add Supabase Auth for user accounts.

**Changes:**
- Add sign up / login UI (Google OAuth + email/password)
- Progress tied to authenticated user
- Row-level security in Supabase
- Guest mode for trying without account

**Validation:** Login works, progress syncs across devices

---

### Phase 5: Multi-User Features & Security
Polish for public release.

**Changes:**
- Rate limiting on `/solve` endpoint
- Input validation / sanitization
- Usage tracking / analytics
- Error handling improvements

**Validation:** Security review, load testing

---

## Decisions Made

- **LLM Provider**: Abstract interface, decide in Phase 2 (support both Anthropic/OpenAI)
- **Auth method**: Both Google OAuth and email/password
- **Pricing model**: TBD (decide before Phase 5)

---

## Files to Modify (Phase 1)

| File | Changes |
|------|---------|
| `puzzle_store.py` | Replace file ops with Supabase client |
| `crossword_server.py` | Use new puzzle_store, add session progress |
| `requirements.txt` | Add `supabase` package |
| `.env` | Supabase URL + key |

## Verification (Phase 1)
1. Create Supabase project
2. Run migrations to create tables
3. Start local server with Supabase connection
4. Import a puzzle → verify in Supabase dashboard
5. Solve partially → verify progress saved to DB
