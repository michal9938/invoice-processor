import { createBrowserClient } from "@supabase/ssr";

export function createSupabaseBrowserClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://xcnwbfmoxqacpdscgaef.supabase.co";
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "sb_publishable_ZMkfggTb6u5f7rEBc5l0Xw_91CLxQIk";

  if (!url || !anonKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY in environment.",
    );
  }

  return createBrowserClient(url, anonKey);
}


