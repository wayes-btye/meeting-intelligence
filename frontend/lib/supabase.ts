import { createBrowserClient } from "@supabase/ssr";

// Supabase browser client — used for auth (sign in / sign out / session)
// NEXT_PUBLIC_SUPABASE_ANON_KEY must be set in .env.local (get from Supabase dashboard → Settings → API)
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
