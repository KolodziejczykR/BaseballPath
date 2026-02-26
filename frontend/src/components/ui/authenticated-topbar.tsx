"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AccountMeResponse = {
  profile?: {
    full_name?: string | null;
  };
  plan?: {
    tier?: string;
    remaining_evals?: number | null;
    monthly_eval_limit?: number | null;
  };
};

type AuthenticatedTopBarProps = {
  accessToken: string;
  userEmail?: string | null;
};

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/predict", label: "Predict" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/plans", label: "Plans" },
  { href: "/account", label: "Account" },
];

export function AuthenticatedTopBar({ accessToken, userEmail }: AuthenticatedTopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [account, setAccount] = useState<AccountMeResponse | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadAccount() {
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/account/me`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        if (!response.ok) return;
        const data = (await response.json()) as AccountMeResponse;
        if (!mounted) return;
        setAccount(data);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    loadAccount();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!menuOpen) return;
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [menuOpen]);

  const fullName = account?.profile?.full_name || "";
  const planTier = (account?.plan?.tier || "starter").toUpperCase();
  const remainingEvals = account?.plan?.remaining_evals;
  const monthlyLimit = account?.plan?.monthly_eval_limit;
  const displayEmail = userEmail || "Signed in";
  const avatarLabel = (fullName || displayEmail || "U").trim().charAt(0).toUpperCase();

  async function signOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-black/10 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--navy)] text-sm font-bold tracking-wide text-white">
            BP
          </div>
          <div className="leading-tight">
            <p className="text-xs uppercase tracking-[0.34em] text-[var(--muted)]">BaseballPath</p>
            <p className="text-base font-semibold">Recruiting Console</p>
          </div>
        </Link>

        <div className="flex items-center gap-4">
          <nav className="hidden items-center gap-5 text-sm font-semibold text-[var(--muted)] md:flex">
            {navItems.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`transition-colors ${active ? "text-[var(--foreground)]" : "hover:text-[var(--foreground)]"}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              className="inline-flex items-center gap-3 rounded-full border border-[var(--stroke)] bg-white/80 px-3 py-1.5 text-sm font-semibold text-[var(--navy)]"
            >
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-xs font-bold text-white">
                {avatarLabel}
              </span>
              <span className="hidden text-left text-xs leading-tight sm:block">
                <span className="block font-semibold">{fullName || "My Account"}</span>
                <span className="block text-[var(--muted)]">{loading ? "Loading..." : planTier}</span>
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-72 rounded-2xl border border-[var(--stroke)] bg-white p-3 shadow-strong">
                <div className="rounded-xl border border-[var(--stroke)] bg-[var(--sand)]/45 p-3">
                  <p className="text-sm font-semibold text-[var(--navy)]">{fullName || "My Account"}</p>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">{displayEmail}</p>
                  <p className="mt-2 text-xs font-semibold text-[var(--navy)]">
                    {planTier}
                    {typeof remainingEvals === "number" && typeof monthlyLimit === "number"
                      ? ` · ${remainingEvals}/${monthlyLimit} left`
                      : ""}
                  </p>
                </div>

                <div className="mt-3 grid gap-2 text-sm">
                  <Link
                    href="/evaluations"
                    className="rounded-xl border border-[var(--stroke)] px-3 py-2 font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                    onClick={() => setMenuOpen(false)}
                  >
                    Past Evaluations
                  </Link>
                  <Link
                    href="/account"
                    className="rounded-xl border border-[var(--stroke)] px-3 py-2 font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                    onClick={() => setMenuOpen(false)}
                  >
                    Account Settings
                  </Link>
                  <Link
                    href="/account#billing"
                    className="rounded-xl border border-[var(--stroke)] px-3 py-2 font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                    onClick={() => setMenuOpen(false)}
                  >
                    Upgrade or Manage Plan
                  </Link>
                  <button
                    type="button"
                    onClick={signOut}
                    className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-left font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
