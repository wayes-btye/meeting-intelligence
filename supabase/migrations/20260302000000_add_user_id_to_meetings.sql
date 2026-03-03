-- Add user_id column referencing Supabase auth users
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id);

-- Assign existing meetings to reviewer@example.com
UPDATE meetings
SET user_id = (SELECT id FROM auth.users WHERE email = 'reviewer@example.com')
WHERE user_id IS NULL;

-- Enforce NOT NULL now that the backfill is complete.
-- If any rows are still NULL here the migration will fail loudly, which is the
-- right behaviour — it means reviewer@example.com doesn't exist in auth.users
-- and those meetings would be silently inaccessible to all users. (#71)
ALTER TABLE meetings ALTER COLUMN user_id SET NOT NULL;
