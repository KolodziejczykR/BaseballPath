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
    <header className="sticky top-0 z-40 border-b border-[var(--stroke)]/30 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/predict" className="flex items-center gap-3">
          <Image
            src="/BP-brown-logo-circle.png"
            alt="BaseballPath"
            width={44}
            height={44}
            className="h-11 w-11"
          />
          <div className="leading-tight">
            <p className="text-xs uppercase tracking-[0.34em] text-[var(--muted)]">BaseballPath</p>
            <p className="text-base font-semibold">Recruitment Assistant</p>
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
                  className={`transition-colors py-4 border-b-2 ${active ? "text-[var(--foreground)] border-[var(--primary)]" : "text-[var(--muted)] hover:text-[var(--foreground)] border-transparent"}`}
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
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-72 rounded-2xl border border-[var(--stroke)] bg-[var(--parchment)] p-3 shadow-strong">
                <div className="rounded-xl border border-[var(--stroke)] bg-[var(--sand)]/45 p-3">
                  <p className="text-sm font-semibold text-[var(--navy)]">{fullName || "My Account"}</p>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">{displayEmail}</p>
                </div>

                <div className="mt-3 grid gap-2 text-sm">
                  {hasPastEvals && (
                    <Link
                      href="/evaluations"
                      className="rounded-xl border border-[var(--stroke)] px-3 py-2 font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                      onClick={() => setMenuOpen(false)}
                    >
                      Past Evaluations
                    </Link>
                  )}
                  <Link
                    href="/account"
                    className="rounded-xl border border-[var(--stroke)] px-3 py-2 font-semibold text-[var(--navy)] hover:bg-[var(--sand)]/45"
                    onClick={() => setMenuOpen(false)}
                  >
                    Account Settings
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
