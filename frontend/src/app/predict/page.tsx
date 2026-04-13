"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useOptionalAuth } from "@/hooks/useOptionalAuth";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { RegionMap, type RegionName } from "@/components/evaluation/region-map";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PositionCode = "LHP" | "RHP" | "C" | "1B" | "2B" | "SS" | "3B" | "OF";
type Step = 1 | 2 | 3 | 4;

type MLPrediction = {
  final_prediction: string;
  d1_probability: number;
  p4_probability: number | null;
  confidence: string;
  d1_details?: Record<string, unknown>;
  p4_details?: Record<string, unknown>;
  player_info?: Record<string, unknown>;
};

type TeaserSchool = {
  school_name: string;
  display_school_name?: string | null;
  division_group?: string | null;
  division_label?: string | null;
  baseball_division?: number | null;
  school_logo_image?: string | null;
};

function getNcaLogoUrl(logoKey: string | null | undefined): string | null {
  const key = (logoKey || "").trim();
  if (!key) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(key)}.svg`;
}

function teaserDivisionLabel(school: TeaserSchool): string {
  if (school.division_label) return school.division_label;
  if (school.division_group?.includes("Power 4")) return "Power 4";
  if (school.division_group?.includes("Non-P4")) return "Division 1";
  if (school.baseball_division === 2) return "Division 2";
  if (school.baseball_division === 3) return "Division 3";
  return school.division_group || "";
}

// ---------------------------------------------------------------------------
// Position helpers
// ---------------------------------------------------------------------------

const PITCHER_POSITIONS = new Set(["LHP", "RHP"]);
const CATCHER_POSITIONS = new Set(["C", "CATCHER"]);

function isPitcher(pos: string): boolean {
  return PITCHER_POSITIONS.has(pos.toUpperCase());
}

function mlEndpoint(pos: string): string {
  const p = pos.toUpperCase();
  if (PITCHER_POSITIONS.has(p)) return "pitcher";
  if (p === "OF") return "outfielder";
  if (CATCHER_POSITIONS.has(p)) return "catcher";
  return "infielder";
}

// ---------------------------------------------------------------------------
// State / region mapping
// ---------------------------------------------------------------------------

const NE = new Set(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"]);
const MW = new Set(["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"]);
const S = new Set(["AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD", "MS", "NC", "OK", "SC", "TN", "TX", "VA", "WV"]);

function stateToRegion(st: string): string {
  const s2 = st.toUpperCase();
  if (NE.has(s2)) return "Northeast";
  if (MW.has(s2)) return "Midwest";
  if (S.has(s2)) return "South";
  return "West";
}

// ---------------------------------------------------------------------------
// Budget options
// ---------------------------------------------------------------------------

const BUDGET_OPTIONS = [
  { label: "Under $20K", value: "under_20k" },
  { label: "$20K – $35K", value: "20k_35k" },
  { label: "$35K – $50K", value: "35k_50k" },
  { label: "$50K – $65K", value: "50k_65k" },
  { label: "$65K+", value: "65k_plus" },
  { label: "No preference", value: "no_preference" },
];

// ---------------------------------------------------------------------------
// Position options
// ---------------------------------------------------------------------------

const POSITION_OPTIONS: { label: string; value: PositionCode }[] = [
  { label: "RHP (Right-Handed Pitcher)", value: "RHP" },
  { label: "LHP (Left-Handed Pitcher)", value: "LHP" },
  { label: "C (Catcher)", value: "C" },
  { label: "1B (First Base)", value: "1B" },
  { label: "2B (Second Base)", value: "2B" },
  { label: "SS (Shortstop)", value: "SS" },
  { label: "3B (Third Base)", value: "3B" },
  { label: "OF (Outfield)", value: "OF" },
];

const GRAD_YEARS = [
  { label: "2026", value: 2026 },
  { label: "2027", value: 2027 },
  { label: "2028", value: 2028 },
  { label: "2029+", value: 2029 },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function num(v: string): number | undefined {
  const n = Number(v.trim());
  return v.trim() && Number.isFinite(n) ? n : undefined;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PredictPage() {
  return (
    <Suspense fallback={<div className="min-h-screen px-6 py-16" />}>
      <PredictContent />
    </Suspense>
  );
}

function PredictContent() {
  const { loading: authLoading, accessToken, user, isAuthenticated } = useOptionalAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [step, setStep] = useState<Step>(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Check if user returned from cancelled checkout
  useEffect(() => {
    if (searchParams.get("checkout") === "cancelled") {
      setError("Checkout was cancelled. You can try again when you're ready.");
    }
  }, [searchParams]);

  // Profile data
  const [userState, setUserState] = useState("");

  // Step 1: Baseball
  const [position, setPosition] = useState<PositionCode | "">("");
  const [gradYear, setGradYear] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [throwingHand, setThrowingHand] = useState("R");
  const [hittingHand, setHittingHand] = useState("R");
  // Hitter
  const [exitVelo, setExitVelo] = useState("");
  const [sixtyTime, setSixtyTime] = useState("");
  const [infVelo, setInfVelo] = useState("");
  const [ofVelo, setOfVelo] = useState("");
  const [cVelo, setCVelo] = useState("");
  const [popTime, setPopTime] = useState("");
  // Pitcher
  const [fbVeloMax, setFbVeloMax] = useState("");
  const [fbVeloAvg, setFbVeloAvg] = useState("");
  const [fbSpin, setFbSpin] = useState("");
  const [chVelo, setChVelo] = useState("");
  const [chSpin, setChSpin] = useState("");
  const [cbVelo, setCbVelo] = useState("");
  const [cbSpin, setCbSpin] = useState("");
  const [slVelo, setSlVelo] = useState("");
  const [slSpin, setSlSpin] = useState("");

  // Step 2: Academics
  const [gpa, setGpa] = useState("");
  const [satScore, setSatScore] = useState("");
  const [actScore, setActScore] = useState("");
  const [apCourses, setApCourses] = useState("");

  // Step 3: Preferences
  const [selectedRegions, setSelectedRegions] = useState<RegionName[]>([]);
  const [budget, setBudget] = useState("no_preference");
  const [rankingPriority, setRankingPriority] = useState("");

  // ML prediction result (fires in background after Step 1)
  const mlResultRef = useRef<Promise<MLPrediction | null> | null>(null);
  const [mlRunning, setMlRunning] = useState(false);

  // Step 4: Preview/Payment state
  const [sessionToken, setSessionToken] = useState("");
  const [priceCents, setPriceCents] = useState<number | null>(null);
  const [isFirstEval, setIsFirstEval] = useState<boolean | null>(null);
  const [teaserSchools, setTeaserSchools] = useState<TeaserSchool[]>([]);

  // Load profile state (only if authenticated)
  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API}/account/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data?.profile?.state) setUserState(data.profile.state);
      })
      .catch(() => { });
  }, [accessToken]);

  // ---------------------------------------------------------------------------
  // Step 1 submit → fire ML prediction in background
  // ---------------------------------------------------------------------------

  function buildMLPayload(): Record<string, unknown> {
    const pos = position as PositionCode;
    if (isPitcher(pos)) {
      return {
        height: Number(height),
        weight: Number(weight),
        primary_position: pos,
        player_region: userState ? stateToRegion(userState) : "West",
        throwing_hand: throwingHand,
        fastball_velo_max: Number(fbVeloMax),
        ...(num(fbVeloAvg) !== undefined && { fastball_velo_range: num(fbVeloAvg) }),
        ...(num(fbSpin) !== undefined && { fastball_spin: num(fbSpin) }),
        ...(num(chVelo) !== undefined && { changeup_velo: num(chVelo) }),
        ...(num(chSpin) !== undefined && { changeup_spin: num(chSpin) }),
        ...(num(cbVelo) !== undefined && { curveball_velo: num(cbVelo) }),
        ...(num(cbSpin) !== undefined && { curveball_spin: num(cbSpin) }),
        ...(num(slVelo) !== undefined && { slider_velo: num(slVelo) }),
        ...(num(slSpin) !== undefined && { slider_spin: num(slSpin) }),
      };
    }
    // Position player
    const base: Record<string, unknown> = {
      height: Number(height),
      weight: Number(weight),
      primary_position: pos === "C" ? "C" : pos,
      player_region: userState ? stateToRegion(userState) : "West",
      throwing_hand: throwingHand,
      hitting_handedness: hittingHand,
      sixty_time: Number(sixtyTime),
      exit_velo_max: Number(exitVelo),
    };
    if (pos === "C") {
      base.c_velo = Number(cVelo);
      base.pop_time = Number(popTime);
    } else if (pos === "OF") {
      base.of_velo = Number(ofVelo);
    } else {
      base.inf_velo = Number(infVelo);
    }
    return base;
  }

  function fireMLPrediction() {
    const payload = buildMLPayload();
    const endpoint = mlEndpoint(position);

    setMlRunning(true);
    const promise = fetch(`${API}/predict/${endpoint}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(payload),
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "ML prediction failed");
        }
        return res.json() as Promise<MLPrediction>;
      })
      .catch((err) => {
        console.error("ML prediction error:", err);
        return null;
      })
      .finally(() => setMlRunning(false));

    mlResultRef.current = promise;
  }

  function handleStep1Submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    fireMLPrediction();
    setStep(2);
  }

  function handleStep2Submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!satScore.trim() && !actScore.trim()) {
      setError("Please provide at least one test score (SAT or ACT).");
      return;
    }
    setStep(3);
  }

  async function handleStep3Submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      // Wait for ML result
      const mlResult = mlResultRef.current ? await mlResultRef.current : null;
      if (!mlResult) {
        setError("Baseball prediction failed. Please go back and try again.");
        setSubmitting(false);
        return;
      }

      const payload = {
        baseball_metrics: {
          ...buildMLPayload(),
          graduation_year: num(gradYear),
        },
        ml_prediction: mlResult,
        academic_input: {
          gpa: Number(gpa),
          sat_score: num(satScore) ?? null,
          act_score: num(actScore) ?? null,
          ap_courses: Number(apCourses) || 0,
        },
        preferences: {
          regions: selectedRegions.length > 0 ? selectedRegions : null,
          max_budget: budget,
          ranking_priority: rankingPriority || null,
        },
      };

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
      }

      const res = await fetch(`${API}/evaluations/preview`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Evaluation failed");
      }

      const result = await res.json();
      setSessionToken(result.session_token);
      setPriceCents(result.price_cents);
      setIsFirstEval(result.is_first_eval);
      setTeaserSchools(Array.isArray(result.teaser_schools) ? result.teaser_schools : []);

      // Store session token in localStorage as backup
      localStorage.setItem("bp_session_token", result.session_token);

      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Step 4: Payment handlers
  // ---------------------------------------------------------------------------

  function handlePayment() {
    if (isAuthenticated) {
      router.push(`/predict/checkout?session_token=${sessionToken}`);
      return;
    }
    // Anonymous users must create an account before paying.
    const next = `/predict/checkout?session_token=${sessionToken}`;
    router.push(`/signup?session_token=${sessionToken}&next=${encodeURIComponent(next)}`);
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  const step1Valid = useMemo(() => {
    if (!position || !height || !weight || !gradYear) return false;
    if (isPitcher(position)) {
      return !!fbVeloMax;
    }
    if (!exitVelo || !sixtyTime) return false;
    if (position === "C" && (!cVelo || !popTime)) return false;
    if (position === "OF" && !ofVelo) return false;
    if (["1B", "2B", "SS", "3B"].includes(position) && !infVelo) return false;
    return true;
  }, [position, height, weight, gradYear, fbVeloMax, exitVelo, sixtyTime, infVelo, ofVelo, cVelo, popTime]);

  const step2Valid = useMemo(() => {
    return !!gpa && (!!satScore || !!actScore) && apCourses !== "";
  }, [gpa, satScore, actScore, apCourses]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (authLoading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading...</p>
        </div>
      </div>
    );
  }

  // Price display helper
  const displayPrice = priceCents
    ? `$${(priceCents / 100).toFixed(0)}`
    : isFirstEval === null
      ? "$69"
      : isFirstEval
        ? "$69"
        : "$29";

  return (
    <div className="min-h-screen">
      {isAuthenticated && accessToken && (
        <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />
      )}

      <main className="px-6 pt-5 pb-10 md:pt-6 md:pb-12">
        <div className="mx-auto max-w-2xl">
          {/* Header */}
          <h1 className="display-font mt-3 text-3xl md:text-4xl text-center">
            Player Evaluation
          </h1>
          <p className="mt-2 text-center text-sm text-[var(--muted)]">
            Get matched with the best college baseball programs for you.
          </p>

          {/* Step indicator */}
          <div className="mt-6 mb-8 flex items-start justify-center">
            {[1, 2, 3].map((s) => {
              const label = s === 1 ? "Baseball" : s === 2 ? "Academics" : "Preferences";
              return (
                <div key={s} className="flex items-center">
                  <div className="relative flex flex-col items-center">
                    <div
                      className="flex h-8 w-8 z-10 items-center justify-center rounded-full text-xs font-bold transition-colors"
                      style={{
                        background: step >= s ? "var(--primary)" : "var(--clay-mist)",
                        color: step >= s ? "white" : "var(--muted)",
                      }}
                    >
                      {step > 3 && s === 3 ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        s
                      )}
                    </div>
                    <span
                      className={`absolute top-10 w-24 text-center text-xs ${step === s ? "font-semibold text-[var(--foreground)]" : "text-[var(--muted)]"
                        }`}
                    >
                      {label}
                    </span>
                  </div>
                  {s < 3 && (
                    <div
                      className="mx-2 h-0.5 w-10 sm:w-16 sm:mx-3"
                      style={{
                        background: step > s ? "var(--primary)" : "var(--stroke)",
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {error && (
            <div className="mt-4 rounded-2xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* ============================================================= */}
          {/* STEP 1: Baseball Metrics */}
          {/* ============================================================= */}
          {step === 1 && (
            <form onSubmit={handleStep1Submit} className="mt-6 space-y-5">
              <div className="glass rounded-2xl p-6 shadow-soft space-y-4">
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
                  Player Info
                </p>

                {/* Position */}
                <div>
                  <label className="block text-sm font-medium mb-1">Position</label>
                  <select
                    className="form-control"
                    value={position}
                    onChange={(e) => setPosition(e.target.value as PositionCode)}
                    required
                  >
                    <option value="">Select position...</option>
                    {POSITION_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>

                {/* Graduation year */}
                <div>
                  <label className="block text-sm font-medium mb-1">Graduation Year</label>
                  <select className="form-control" value={gradYear} onChange={(e) => setGradYear(e.target.value)} required>
                    <option value="">Select year...</option>
                    {GRAD_YEARS.map((y) => (
                      <option key={y.value} value={String(y.value)}>{y.label}</option>
                    ))}
                  </select>
                </div>

                {/* Height / Weight */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Height (inches)</label>
                    <input type="number" className="form-control" value={height} onChange={(e) => setHeight(e.target.value)} min={60} max={84} step={1} placeholder="72" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Weight (lbs)</label>
                    <input type="number" className="form-control" value={weight} onChange={(e) => setWeight(e.target.value)} min={120} max={320} step={1} placeholder="185" required />
                  </div>
                </div>

                {/* Throwing / Hitting hand */}
                {!isPitcher(position || "") && position && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium mb-1">Throwing Hand</label>
                      <select className="form-control" value={throwingHand} onChange={(e) => setThrowingHand(e.target.value)}>
                        <option value="R">Right</option>
                        <option value="L">Left</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Hitting Handedness</label>
                      <select className="form-control" value={hittingHand} onChange={(e) => setHittingHand(e.target.value)}>
                        <option value="R">Right</option>
                        <option value="L">Left</option>
                        <option value="S">Switch</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* Position-specific metrics */}
              {position && (
                <div className="glass rounded-2xl p-6 shadow-soft space-y-4">
                  <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
                    {isPitcher(position) ? "Pitching Metrics" : "Hitting & Athletic Metrics"}
                  </p>

                  {isPitcher(position) ? (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1">Fastball Velocity Max (mph) *</label>
                        <input type="number" className="form-control" value={fbVeloMax} onChange={(e) => setFbVeloMax(e.target.value)} min={60} max={105} step={0.1} placeholder="90.0" required />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Fastball Velocity Avg (mph)</label>
                        <input type="number" className="form-control" value={fbVeloAvg} onChange={(e) => setFbVeloAvg(e.target.value)} min={60} max={105} step={0.1} placeholder="88.0" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Fastball Spin Rate (rpm)</label>
                        <input type="number" className="form-control" value={fbSpin} onChange={(e) => setFbSpin(e.target.value)} min={1200} max={3500} step={1} placeholder="2200" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium mb-1">Curveball Velo (mph)</label>
                          <input type="number" className="form-control" value={cbVelo} onChange={(e) => setCbVelo(e.target.value)} min={55} max={95} step={0.1} placeholder="74.0" />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Curveball Spin (rpm)</label>
                          <input type="number" className="form-control" value={cbSpin} onChange={(e) => setCbSpin(e.target.value)} min={1200} max={3500} step={1} placeholder="2200" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium mb-1">Slider Velo (mph)</label>
                          <input type="number" className="form-control" value={slVelo} onChange={(e) => setSlVelo(e.target.value)} min={60} max={100} step={0.1} placeholder="78.0" />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Slider Spin (rpm)</label>
                          <input type="number" className="form-control" value={slSpin} onChange={(e) => setSlSpin(e.target.value)} min={1200} max={3500} step={1} placeholder="2250" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium mb-1">Changeup Velo (mph)</label>
                          <input type="number" className="form-control" value={chVelo} onChange={(e) => setChVelo(e.target.value)} min={60} max={95} step={0.1} placeholder="80.0" />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Changeup Spin (rpm)</label>
                          <input type="number" className="form-control" value={chSpin} onChange={(e) => setChSpin(e.target.value)} min={800} max={3200} step={1} placeholder="1700" />
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium mb-1">Exit Velocity (mph) *</label>
                          <input type="number" className="form-control" value={exitVelo} onChange={(e) => setExitVelo(e.target.value)} min={50} max={130} step={0.1} placeholder="92" required />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">60-Yard Dash (sec) *</label>
                          <input type="number" className="form-control" value={sixtyTime} onChange={(e) => setSixtyTime(e.target.value)} min={5.0} max={10.0} step={0.01} placeholder="6.85" required />
                        </div>
                      </div>

                      {/* Position-specific defensive metric */}
                      {["1B", "2B", "SS", "3B"].includes(position) && (
                        <div>
                          <label className="block text-sm font-medium mb-1">Infield Velocity (mph) *</label>
                          <input type="number" className="form-control" value={infVelo} onChange={(e) => setInfVelo(e.target.value)} min={50} max={100} step={0.1} placeholder="83" required />
                        </div>
                      )}
                      {position === "OF" && (
                        <div>
                          <label className="block text-sm font-medium mb-1">Outfield Velocity (mph) *</label>
                          <input type="number" className="form-control" value={ofVelo} onChange={(e) => setOfVelo(e.target.value)} min={50} max={110} step={0.1} placeholder="88" required />
                        </div>
                      )}
                      {position === "C" && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-sm font-medium mb-1">Catcher Velocity (mph) *</label>
                            <input type="number" className="form-control" value={cVelo} onChange={(e) => setCVelo(e.target.value)} min={50} max={100} step={0.1} placeholder="78" required />
                          </div>
                          <div>
                            <label className="block text-sm font-medium mb-1">Pop Time (sec) *</label>
                            <input type="number" className="form-control" value={popTime} onChange={(e) => setPopTime(e.target.value)} min={1.5} max={4.0} step={0.01} placeholder="1.95" required />
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={!step1Valid}
                className="w-full rounded-full bg-[var(--primary)] py-3 text-sm font-semibold !text-white shadow-strong disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue to Academics
              </button>
            </form>
          )}

          {/* ============================================================= */}
          {/* STEP 2: Academic Input */}
          {/* ============================================================= */}
          {step === 2 && (
            <form onSubmit={handleStep2Submit} className="mt-6 space-y-5">
              {mlRunning && (
                <div className="rounded-2xl border border-[var(--accent)]/30 bg-[var(--accent)]/10 p-3 text-sm text-[var(--foreground)] text-center">
                  Processing your baseball metrics in the background...
                </div>
              )}

              <div className="glass rounded-2xl p-6 shadow-soft space-y-4">
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
                  Academic Profile
                </p>

                <div>
                  <label className="block text-sm font-medium mb-1">GPA (4.0 unweighted scale) *</label>
                  <input type="number" className="form-control" value={gpa} onChange={(e) => setGpa(e.target.value)} min={0} max={4.0} step={0.01} placeholder="3.70" required />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">SAT Score {!actScore.trim() ? "*" : ""}</label>
                    <input type="number" className="form-control" value={satScore} onChange={(e) => setSatScore(e.target.value)} min={400} max={1600} step={10} placeholder="1350" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">ACT Score {!satScore.trim() ? "*" : ""}</label>
                    <input type="number" className="form-control" value={actScore} onChange={(e) => setActScore(e.target.value)} min={1} max={36} step={1} placeholder="30" />
                  </div>
                </div>
                <p className="text-xs text-[var(--muted)]">At least one test score is required.</p>

                <div>
                  <label className="block text-sm font-medium mb-1">Number of AP/Honors Courses *</label>
                  <input type="number" className="form-control" value={apCourses} onChange={(e) => setApCourses(e.target.value)} min={0} step={1} placeholder="5" required />
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="flex-1 rounded-full border border-[var(--stroke)] py-3 text-sm font-semibold text-[var(--foreground)]"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={!step2Valid}
                  className="flex-1 rounded-full bg-[var(--primary)] py-3 text-sm font-semibold !text-white shadow-strong disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Continue to Preferences
                </button>
              </div>
            </form>
          )}

          {/* ============================================================= */}
          {/* STEP 3: Preferences */}
          {/* ============================================================= */}
          {step === 3 && (
            <form onSubmit={handleStep3Submit} className="mt-6 space-y-5">
              <div className="glass rounded-2xl p-6 shadow-soft space-y-5">
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
                  School Preferences
                </p>

                {/* Region map */}
                <RegionMap selected={selectedRegions} onChange={setSelectedRegions} />

                {/* Budget */}
                <div>
                  <label className="block text-sm font-medium mb-1">Maximum Annual Budget</label>
                  <select className="form-control" value={budget} onChange={(e) => setBudget(e.target.value)}>
                    {BUDGET_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>

                {/* Ranking Priority */}
                <div>
                  <label className="block text-sm font-medium mb-1">What matters most to you?</label>
                  <div className="grid grid-cols-1 gap-2">
                    {[
                      { value: "", label: "Balanced", desc: "Equal weight across all factors" },
                      { value: "playing_time", label: "Day 1 Playing Time", desc: "Prioritize roster opportunity" },
                      { value: "baseball_fit", label: "Best Baseball Fit", desc: "Closest competitive match" },
                      { value: "academics", label: "Best Academics", desc: "Strongest school you can play at" },
                    ].map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setRankingPriority(option.value)}
                        className={`text-left rounded-xl border p-3 transition-all ${
                          rankingPriority === option.value
                            ? "border-[var(--primary)] bg-[var(--primary)]/5"
                            : "border-[var(--stroke)] hover:border-[var(--muted)]"
                        }`}
                      >
                        <p className="text-sm font-medium">{option.label}</p>
                        <p className="text-xs text-[var(--muted)]">{option.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="flex-1 rounded-full border border-[var(--stroke)] py-3 text-sm font-semibold text-[var(--foreground)]"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 rounded-full bg-[var(--primary)] py-3 text-sm font-semibold !text-white shadow-strong disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? "Analyzing your profile..." : "Get Results"}
                </button>
              </div>
            </form>
          )}

          {/* ============================================================= */}
          {/* STEP 4: Results Ready — Payment Gate */}
          {/* ============================================================= */}
          {step === 4 && (
            <div className="mt-6 space-y-6">
              <div className="glass rounded-2xl p-8 shadow-soft text-center space-y-5">

                <div>
                  <h2 className="display-font text-2xl md:text-3xl">
                    You fit at schools like these
                  </h2>
                  <p className="mt-2 text-sm text-[var(--muted)] max-w-md mx-auto">
                    Unlock your full evaluation to see the complete list with deep analysis.
                  </p>
                </div>

                {/* Teaser schools */}
                {teaserSchools.length > 0 && (
                  <div className="grid gap-3 sm:grid-cols-3">
                    {teaserSchools.map((school, idx) => {
                      const logo = getNcaLogoUrl(school.school_logo_image);
                      const displayName = school.display_school_name || school.school_name;
                      const level = teaserDivisionLabel(school);
                      return (
                        <div
                          key={`${school.school_name}-${idx}`}
                          className="rounded-2xl border border-[var(--stroke)] bg-white/70 p-4 flex flex-col items-center text-center gap-2"
                        >
                          <div className="h-12 w-12 flex items-center justify-center">
                            {logo ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={logo}
                                alt={displayName}
                                className="max-h-12 max-w-12 object-contain"
                              />
                            ) : (
                              <div className="h-12 w-12 rounded-full bg-[var(--clay-mist)]" />
                            )}
                          </div>
                          <p className="text-sm font-semibold text-[var(--foreground)] leading-tight">
                            {displayName}
                          </p>
                          {level && (
                            <p className="text-xs text-[var(--muted)]">{level}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* What's included */}
                <div className="text-left mx-auto max-w-sm space-y-2">
                  <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)] text-center">
                    Your full evaluation includes
                  </p>
                  {[
                    "10-15 best-fit school matches ranked for you",
                    "A personalized breakdown of why each school fits your baseball and academic profile",
                    "How your baseball metrics compare to players who committed at each level",
                  ].map((item) => (
                    <div key={item} className="flex items-start gap-2">
                      <svg className="mt-0.5 h-4 w-4 shrink-0 text-[var(--sage)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-sm">{item}</span>
                    </div>
                  ))}
                </div>

                {/* Price */}
                <div className="rounded-xl border border-[var(--stroke)] bg-[var(--clay-mist)]/50 p-4">
                  <p className="display-font text-3xl">{displayPrice}</p>
                  <p className="text-xs text-[var(--muted)] mt-1">
                    {isAuthenticated ? "Per evaluation" : "One payment. No subscription."}
                  </p>
                </div>

                {/* CTA */}
                <button
                  onClick={handlePayment}
                  className="w-full rounded-full bg-[var(--primary)] py-3.5 text-sm font-semibold !text-white shadow-strong"
                >
                  {isAuthenticated ? "Unlock My Results" : "Create account & unlock results"}
                </button>

                {!isAuthenticated && (
                  <p className="text-xs text-[var(--muted)]">
                    Already have an account?{" "}
                    <a
                      href={`/login?next=${encodeURIComponent(`/predict/checkout?session_token=${sessionToken}`)}`}
                      className="underline text-[var(--primary)]"
                    >
                      Log in
                    </a>
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => setStep(3)}
                className="w-full rounded-full border border-[var(--stroke)] py-3 text-sm font-semibold text-[var(--foreground)]"
              >
                Back to Preferences
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
