-- Add training metadata column to clues table
-- Stores pre-annotated step data for the trainer (words, clue_type, difficulty, steps)
-- NULL means the clue has not been annotated for training

ALTER TABLE clues ADD COLUMN IF NOT EXISTS training_metadata JSONB;

-- Index for efficient lookup of annotated clues
CREATE INDEX IF NOT EXISTS idx_clues_training ON clues(puzzle_id) WHERE training_metadata IS NOT NULL;

-- Allow updates to clues (needed for uploading training metadata)
-- DROP first to make migration idempotent (CREATE POLICY has no IF NOT EXISTS)
DROP POLICY IF EXISTS "Allow updates" ON clues;
CREATE POLICY "Allow updates" ON clues FOR UPDATE USING (true);
