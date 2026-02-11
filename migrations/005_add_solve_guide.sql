-- Add solve_guide column to clues table
-- Stores the Times for the Times blog parse guide (optional, used during training metadata encoding)
-- NULL means no solve guide is available for this clue

ALTER TABLE clues ADD COLUMN IF NOT EXISTS solve_guide TEXT;
