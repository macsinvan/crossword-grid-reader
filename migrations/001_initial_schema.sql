-- Grid Reader Database Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/tycvflrjvlvmsiokjaef/sql

-- Publications (Times, Guardian, etc.)
CREATE TABLE IF NOT EXISTS publications (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  logo_color TEXT,
  country_flag TEXT,
  ximenean_strictness INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Puzzles (the primary entity)
CREATE TABLE IF NOT EXISTS puzzles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  publication_id TEXT REFERENCES publications(id),
  puzzle_number TEXT NOT NULL,
  title TEXT,
  date DATE,
  grid_layout JSONB NOT NULL,  -- 2D array of cell types
  grid_size INTEGER NOT NULL,  -- e.g., 15 for 15x15
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(publication_id, puzzle_number)
);

-- Clues (belong to puzzles)
CREATE TABLE IF NOT EXISTS clues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('across', 'down')),
  text TEXT NOT NULL,
  enumeration TEXT NOT NULL,  -- e.g., "6" or "3-4"
  answer TEXT,  -- NULL if answers not provided
  start_row INTEGER NOT NULL,
  start_col INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(puzzle_id, number, direction)
);

-- User progress (per puzzle)
CREATE TABLE IF NOT EXISTS user_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,  -- anonymous session initially, user_id later
  puzzle_id UUID REFERENCES puzzles(id) ON DELETE CASCADE,
  grid_state JSONB NOT NULL,  -- 2D array of entered letters
  selected_cell JSONB,  -- {row, col}
  direction TEXT,  -- 'across' or 'down'
  started_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  UNIQUE(session_id, puzzle_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_puzzles_publication ON puzzles(publication_id);
CREATE INDEX IF NOT EXISTS idx_clues_puzzle ON clues(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_progress_session ON user_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_progress_puzzle ON user_progress(puzzle_id);

-- Disable RLS for development (enable with proper policies before production)
ALTER TABLE publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE puzzles ENABLE ROW LEVEL SECURITY;
ALTER TABLE clues ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_progress ENABLE ROW LEVEL SECURITY;

-- Allow public read access to publications and puzzles
CREATE POLICY "Public read access" ON publications FOR SELECT USING (true);
CREATE POLICY "Public read access" ON puzzles FOR SELECT USING (true);
CREATE POLICY "Public read access" ON clues FOR SELECT USING (true);

-- Allow anonymous inserts for development
CREATE POLICY "Allow inserts" ON publications FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow inserts" ON puzzles FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow inserts" ON clues FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow all" ON user_progress FOR ALL USING (true);

-- Seed initial publications
INSERT INTO publications (id, name, description, logo_color, country_flag, ximenean_strictness) VALUES
  ('times', 'The Times', 'The pinnacle of cryptic excellence. Strictly fair, flawlessly smooth.', '#111827', '🇬🇧', 10),
  ('guardian', 'The Guardian', 'Progressive, playful, and often humorous. Modern style.', '#052962', '🇬🇧', 6),
  ('telegraph', 'Daily Telegraph', 'Elegant surfaces and consistent mechanisms.', '#ee1c2e', '🇬🇧', 8),
  ('express', 'Daily Express', 'High fairness, straightforward surfaces.', '#1e3a8a', '🇬🇧', 9)
ON CONFLICT (id) DO NOTHING;
