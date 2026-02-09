-- Add DELETE policies for puzzles and clues tables
-- Without these, RLS blocks DELETE operations (even with ON DELETE CASCADE on clues)

DROP POLICY IF EXISTS "Allow deletes" ON puzzles;
CREATE POLICY "Allow deletes" ON puzzles FOR DELETE USING (true);

DROP POLICY IF EXISTS "Allow deletes" ON clues;
CREATE POLICY "Allow deletes" ON clues FOR DELETE USING (true);
