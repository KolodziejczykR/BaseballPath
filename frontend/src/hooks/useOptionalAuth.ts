"use client";

import { useEffect, useMemo, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

type UseOptionalAuthResult = {
  loading: boolean;
  session: Session | null;
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
};

/**
 * Like useRequireAuth, but does NOT redirect unauthenticated users.
 * Returns isAuthenticated=false instead.
 */
export function useOptionalAuth(): UseOptionalAuthResult {
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadSession() {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;
      setSession(data.session ?? null);
      setLoading(false);
    }

    loadSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, authSession) => {
      if (!mounted) return;
      setSession(authSession ?? null);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [supabase]);

  return {
    loading,
    session,
    user: session?.user ?? null,
    accessToken: session?.access_token ?? null,
    isAuthenticated: !!session,
  };
}
