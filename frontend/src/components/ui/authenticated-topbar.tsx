"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AccountMeResponse = {
  profile?: {
    full_name?: string | null;
  };
};

type EvaluationsListResponse = {
  items?: unknown[];
  total?: number | null;
};

type AuthenticatedTopBarProps = {
  accessToken: string;
  userEmail?: string | null;
};

export function AuthenticatedTopBar({ accessToken, userEmail }: AuthenticatedTopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);
  const [menuOpen, setMenuOpen] = useState(false);
  const [account, setAccount] = useState<AccountMeResponse | null>(null);
  const [hasPastEvals, setHasPastEvals] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      };
      const [accountResp, runsResp] = await Promise.all([
        fetch(`${API_BASE_URL}/account/me`, { headers }),
        fetch(`${API_BASE_URL}/evaluations?limit=1`, { headers }),
      ]);
      if (accountResp.ok) {
        const data = (await accountResp.json()) as AccountMeResponse;
        if (mounted) setAccount(data);
      }
      if (runsResp.ok) {
        const data = (await runsResp.json()) as EvaluationsListResponse;
        const count =
          typeof data.total === "number"
            ? data.total
            : Array.isArray(data.items)
              ? data.items.length
              : 0;
        if (mounted) setHasPastEvals(count > 0);
      }
    }
    load();
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
  const displayEmail = userEmail || "Signed in";
  const avatarLabel = (fullName || displayEmail || "U").trim().charAt(0).toUpperCase();

  // Build nav items dynamically — Past Evaluations only shown if user has evals
  const navItems = [
    { href: "/predict", label: "Evaluate" },
    ...(hasPastEvals ? [{ href: "/evaluations", label: "Past Evaluations" }] : []),
    { href: "/saved-schools", label: "Saved Schools" },
    { href: "/account", label: "Account" },
  ];

  async function signOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--cool-stroke)] bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/predict" className="flex items-center gap-3">
          <Image
            src="/BP-brown-logo-circle.png"
            alt="BaseballPath"
            width={40}
            height={40}
            className="h-10 w-10 rounded-full"
          />
          <p className="text-sm uppercase tracking-[0.28em] font-semibold text-[var(--cool-ink)]">
            BaseballPath
          </p>
        </Link>

        <div className="flex items-center gap-4">
          <nav className="hidden items-center gap-6 text-sm font-medium md:flex">
            {navItems.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`transition-colors py-4 border-b-2 ${active ? "text-[var(--cool-ink)] border-[var(--burnt-sienna)]" : "text-[var(--cool-ink-muted)] hover:text-[var(--cool-ink)] border-transparent"}`}
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
              className="inline-flex items-center gap-3 rounded-full border border-[var(--cool-stroke)] bg-white px-3 py-1.5 text-sm font-semibold text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
            >
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--burnt-sienna)] text-xs font-bold text-white">
                {avatarLabel}
              </span>
              <span className="hidden text-left text-xs leading-tight sm:block">
                <span className="block font-semibold">{fullName || "My Account"}</span>
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-72 rounded-2xl border border-[var(--cool-stroke)] bg-white p-3 shadow-cool-strong">
                <div className="rounded-xl border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] p-3">
                  <p className="text-sm font-semibold text-[var(--cool-ink)]">{fullName || "My Account"}</p>
                  <p className="mt-0.5 text-xs text-[var(--cool-ink-muted)]">{displayEmail}</p>
                </div>

                <div className="mt-3 grid gap-1.5 text-sm">
                  {hasPastEvals && (
                    <Link
                      href="/evaluations"
                      className="rounded-xl px-3 py-2 font-medium text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
                      onClick={() => setMenuOpen(false)}
                    >
                      Past Evaluations
                    </Link>
                  )}
                  <Link
                    href="/account"
                    className="rounded-xl px-3 py-2 font-medium text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
                    onClick={() => setMenuOpen(false)}
                  >
                    Account Settings
                  </Link>
                  <button
                    type="button"
                    onClick={signOut}
                    className="rounded-xl px-3 py-2 text-left font-medium text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
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
