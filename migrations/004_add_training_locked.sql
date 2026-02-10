-- Add training_locked flag to puzzles table
-- When TRUE, no training metadata (or clue data) can be modified for this puzzle
-- Default FALSE: existing and new puzzles are unlocked

ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS training_locked BOOLEAN DEFAULT FALSE;

-- Lock puzzle 29453 immediately (verified reference puzzle)
UPDATE puzzles SET training_locked = TRUE
WHERE publication_id = 'times' AND puzzle_number = '29453';
