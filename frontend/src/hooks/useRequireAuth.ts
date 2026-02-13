"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

type UseRequireAuthResult = {
  loading: boolean;
  session: Session | null;
  user: User | null;
  accessToken: string | null;
};

export function useRequireAuth(nextPathOverride?: string): UseRequireAuthResult {
  const router = useRouter();
  const pathname = usePathname();
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let mounted = true;
    const nextPath = nextPathOverride ?? pathname ?? "/";

    async function loadSession() {
      const { data, error } = await supabase.auth.getSession();
      if (!mounted) return;

      if (error || !data.session) {
        router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
        setLoading(false);
        return;
      }

      setSession(data.session);
      setLoading(false);
    }

    loadSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, authSession) => {
      if (!mounted) return;
      setSession(authSession ?? null);
      if (!authSession) {
        router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [pathname, nextPathOverride, router, supabase]);

  return {
    loading,
    session,
    user: session?.user ?? null,
    accessToken: session?.access_token ?? null,
  };
}

