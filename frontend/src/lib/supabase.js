import { createClient } from "@supabase/supabase-js";

const url = process.env.REACT_APP_SUPABASE_URL;
const anon = process.env.REACT_APP_SUPABASE_ANON_KEY;

export const supabase = url && anon ? createClient(url, anon, {
  realtime: { params: { eventsPerSecond: 5 } },
  auth: { persistSession: false, autoRefreshToken: false },
}) : null;
