"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PlayerCardContainer } from "@/components/player-card/player-card-container";
import { PlayerCardFront } from "@/components/player-card/player-card-front";
import { PlayerCardBack } from "@/components/player-card/player-card-back";
import { PreferenceVisibilityToggles } from "@/components/player-card/preference-visibility-toggles";
import { CardExportButton } from "@/components/player-card/card-export-button";
import { ShareLinkGenerator } from "@/components/player-card/share-link-generator";
import { CardAnalyticsPanel } from "@/components/player-card/card-analytics-panel";
import { PhotoUpload } from "@/components/player-card/photo-upload";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type EvaluationRecord = {
  id: string;
  created_at?: string;
  position_track?: string;
  identity_input?: Record<string, unknown>;
  stats_input?: Record<string, unknown>;
  preferences_input?: Record<string, unknown>;
  prediction_response?: {
    final_prediction?: string;
    d1_probability?: number;
    p4_probability?: number | null;
  };
};

type EvaluationListResponse = {
  items: EvaluationRecord[];
};

type CardData = {
  id: string;
  user_id: string;
  latest_evaluation_run_id?: string;
  display_name: string;
  high_school_name?: string | null;
  class_year?: number | null;
  primary_position?: string | null;
  state?: string | null;
  stats_snapshot: Record<string, number>;
  prediction_level?: string | null;
  d1_probability?: number | null;
  p4_probability?: number | null;
  photo_storage_path?: string | null;
  photo_url?: string | null;
  video_links?: Array<{ url: string; label: string; platform?: string }>;
  bp_profile_link?: string | null;
  visible_preferences?: Record<string, boolean>;
  preferences_snapshot?: Record<string, unknown>;
  card_theme?: string | null;
};

type Tab = "edit" | "share" | "analytics";

function toStringValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value === null || value === undefined) return "";
  return String(value);
}

function statRows(position: string | null | undefined, stats: Record<string, unknown>): Array<{ label: string; value: string | number; unit?: string }> {
  const positionUpper = (position || "").toUpperCase();
  const base = [
    { label: "Height", key: "height", unit: "in" },
    { label: "Weight", key: "weight", unit: "lb" },
  ];

  const pitcher = [
    { label: "FB Max", key: "fastball_velo_max", unit: "mph" },
    { label: "FB Avg", key: "fastball_velo_range", unit: "mph" },
    { label: "FB Spin", key: "fastball_spin", unit: "rpm" },
    { label: "CH Velo", key: "changeup_velo", unit: "mph" },
    { label: "CB Velo", key: "curveball_velo", unit: "mph" },
    { label: "SL Velo", key: "slider_velo", unit: "mph" },
  ];

  const hitter = [
    { label: "Exit Velo", key: "exit_velo_max", unit: "mph" },
    { label: "Throw Velo", key: positionUpper === "OF" ? "of_velo" : positionUpper === "C" ? "c_velo" : "inf_velo", unit: "mph" },
    { label: "Pop Time", key: "pop_time", unit: "sec" },
    { label: "60 Time", key: "sixty_time", unit: "sec" },
  ];

  const selected = positionUpper.includes("HP") ? [...pitcher] : [...hitter, ...base];
  const unique = selected.filter((entry, index, arr) => arr.findIndex((candidate) => candidate.key === entry.key) === index);
  const rows: Array<{ label: string; value: string | number; unit?: string }> = [];

  for (const entry of unique) {
    const value = stats[entry.key];
    if (value === null || value === undefined || value === "") continue;
    rows.push({
      label: entry.label,
      value: typeof value === "number" ? Number(value.toFixed ? value.toFixed(2) : value) : toStringValue(value),
      unit: entry.unit,
    });
  }

  return rows;
}

function visiblePreferenceValues(card: CardData | null): Record<string, string> {
  if (!card) return {};
  const visibility = card.visible_preferences || {};
  const snapshot = card.preferences_snapshot || {};
  const visible: Record<string, string> = {};
  for (const [key, value] of Object.entries(snapshot)) {
    if (visibility[key] !== false) {
      visible[key] = toStringValue(value);
    }
  }
  return visible;
}

function parseError(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export default function CardPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/card");
  const [fromEval, setFromEval] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [card, setCard] = useState<CardData | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);

  const [selectedEvalId, setSelectedEvalId] = useState("");
  const [step, setStep] = useState(1);
  const [draftDisplayName, setDraftDisplayName] = useState("");
  const [draftHighSchool, setDraftHighSchool] = useState("");
  const [draftClassYear, setDraftClassYear] = useState("");
  const [draftVideoLinks, setDraftVideoLinks] = useState<Array<{ url: string; label: string; platform?: string }>>([{ url: "", label: "", platform: "general" }]);
  const [draftVisibility, setDraftVisibility] = useState<Record<string, boolean>>({});
  const [pendingPhoto, setPendingPhoto] = useState<File | null>(null);
  const [pendingPhotoPreview, setPendingPhotoPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [editDisplayName, setEditDisplayName] = useState("");
  const [editHighSchool, setEditHighSchool] = useState("");
  const [editClassYear, setEditClassYear] = useState("");
  const [editVideoLinks, setEditVideoLinks] = useState<Array<{ url: string; label: string; platform?: string }>>([]);
  const [editVisibility, setEditVisibility] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<Tab>("edit");

  const cardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const next = new URLSearchParams(window.location.search).get("from_eval") || "";
    setFromEval(next);
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        };

        const [cardResp, evalResp] = await Promise.all([
          fetch(`${API_BASE_URL}/cards/me`, { headers }),
          fetch(`${API_BASE_URL}/evaluations?limit=20&offset=0`, { headers }),
        ]);

        const evalPayload = (await evalResp.json()) as EvaluationListResponse | { detail?: string };
        if (!evalResp.ok) {
          throw new Error(parseError(evalPayload, "Failed to load evaluations."));
        }

        const evalItems = (evalPayload as EvaluationListResponse).items || [];

        let nextCard: CardData | null = null;
        if (cardResp.ok) {
          nextCard = (await cardResp.json()) as CardData;
        } else {
          const cardPayload = (await cardResp.json()) as { detail?: string };
          if (cardResp.status !== 404) {
            throw new Error(parseError(cardPayload, "Failed to load card."));
          }
        }

        if (!mounted) return;
        setEvaluations(evalItems);
        setCard(nextCard);
        if (nextCard) {
          setEditDisplayName(nextCard.display_name || "");
          setEditHighSchool(nextCard.high_school_name || "");
          setEditClassYear(nextCard.class_year ? String(nextCard.class_year) : "");
          setEditVideoLinks(nextCard.video_links || []);
          setEditVisibility(nextCard.visible_preferences || {});
        }
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load card page.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  useEffect(() => {
    if (!evaluations.length) return;
    if (!selectedEvalId) {
      if (fromEval && evaluations.some((item) => item.id === fromEval)) {
        setSelectedEvalId(fromEval);
      } else {
        setSelectedEvalId(evaluations[0].id);
      }
    }
  }, [fromEval, evaluations, selectedEvalId]);

  const selectedEvaluation = useMemo(
    () => evaluations.find((evaluation) => evaluation.id === selectedEvalId) || null,
    [evaluations, selectedEvalId],
  );

  useEffect(() => {
    if (!selectedEvaluation || card) return;

    if (!draftDisplayName) {
      const rawName = toStringValue(selectedEvaluation.identity_input?.name);
      setDraftDisplayName(rawName || user?.email?.split("@")[0] || "Player");
    }

    if (Object.keys(draftVisibility).length === 0) {
      const prefs = selectedEvaluation.preferences_input || {};
      const nextVisibility: Record<string, boolean> = {};
      for (const key of Object.keys(prefs)) nextVisibility[key] = true;
      setDraftVisibility(nextVisibility);
    }
  }, [selectedEvaluation, card, draftDisplayName, draftVisibility, user?.email]);

  const previewCard = card
    ? card
    : {
        id: "preview",
        user_id: "preview",
        display_name: draftDisplayName || "Player",
        high_school_name: draftHighSchool,
        class_year: draftClassYear ? Number(draftClassYear) : null,
        primary_position: toStringValue(selectedEvaluation?.identity_input?.primary_position || selectedEvaluation?.position_track || ""),
        stats_snapshot: (selectedEvaluation?.stats_input || {}) as Record<string, number>,
        prediction_level: selectedEvaluation?.prediction_response?.final_prediction || "Prospect",
        d1_probability: selectedEvaluation?.prediction_response?.d1_probability || 0,
        p4_probability: selectedEvaluation?.prediction_response?.p4_probability || null,
        photo_url: pendingPhotoPreview,
        video_links: draftVideoLinks.filter((link) => link.url.trim()),
        visible_preferences: draftVisibility,
        preferences_snapshot: (selectedEvaluation?.preferences_input || {}) as Record<string, unknown>,
      };

  const previewStats = statRows(previewCard.primary_position || null, previewCard.stats_snapshot || {});

  const previewFront = (
    <PlayerCardFront
      displayName={previewCard.display_name || "Player"}
      position={toStringValue(previewCard.primary_position || "-")}
      classYear={previewCard.class_year || undefined}
      photoUrl={previewCard.photo_url || undefined}
      stats={previewStats}
    />
  );

  const previewBack = (
    <PlayerCardBack
      predictionLevel={previewCard.prediction_level || "Prospect"}
      d1Probability={previewCard.d1_probability || 0}
      p4Probability={previewCard.p4_probability || null}
      videoLinks={previewCard.video_links || []}
      visiblePreferences={visiblePreferenceValues(previewCard as CardData)}
      profileLink={previewCard.bp_profile_link || undefined}
      shareUrl={undefined}
    />
  );

  async function uploadPendingPhoto() {
    if (!pendingPhoto || !accessToken) return;
    const formData = new FormData();
    formData.append("file", pendingPhoto);
    const response = await fetch(`${API_BASE_URL}/cards/me/photo`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      body: formData,
    });
    const payload = (await response.json()) as { detail?: string; card?: CardData };
    if (!response.ok) throw new Error(parseError(payload, "Failed to upload photo."));
    if (payload.card) {
      setCard(payload.card);
    }
  }

  async function handleCreateCard() {
    if (!accessToken) return;
    if (!selectedEvalId) {
      setError("Select an evaluation before creating your card.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const payload = {
        evaluation_run_id: selectedEvalId,
        display_name: draftDisplayName || "Player",
        high_school_name: draftHighSchool || null,
        class_year: draftClassYear ? Number(draftClassYear) : null,
        video_links: draftVideoLinks.filter((link) => link.url.trim()),
        visible_preferences: draftVisibility,
      };

      const response = await fetch(`${API_BASE_URL}/cards`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
      const data = (await response.json()) as CardData | { detail?: string };
      if (!response.ok) {
        throw new Error(parseError(data, "Failed to create card."));
      }
      const created = data as CardData;
      setCard(created);
      setEditDisplayName(created.display_name || "");
      setEditHighSchool(created.high_school_name || "");
      setEditClassYear(created.class_year ? String(created.class_year) : "");
      setEditVideoLinks(created.video_links || []);
      setEditVisibility(created.visible_preferences || {});

      if (pendingPhoto) {
        await uploadPendingPhoto();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create card.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateCard() {
    if (!accessToken || !card) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/cards/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          display_name: editDisplayName,
          high_school_name: editHighSchool || null,
          class_year: editClassYear ? Number(editClassYear) : null,
          video_links: editVideoLinks.filter((link) => link.url.trim()),
          visible_preferences: editVisibility,
        }),
      });
      const data = (await response.json()) as CardData | { detail?: string };
      if (!response.ok) throw new Error(parseError(data, "Failed to update card."));
      setCard(data as CardData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update card.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRefreshFromLatest() {
    if (!accessToken) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/cards/me/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const data = (await response.json()) as CardData | { detail?: string };
      if (!response.ok) throw new Error(parseError(data, "Failed to refresh card."));
      setCard(data as CardData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh card.");
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading your player card...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Player Card</p>
              <h1 className="display-font mt-2 text-4xl md:text-5xl">Build and Share Your Card</h1>
            </div>
            {card ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleRefreshFromLatest()}
                  disabled={submitting}
                  className="rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-sm font-semibold text-[var(--navy)]"
                >
                  Refresh from Latest Evaluation
                </button>
                <CardExportButton cardRef={cardRef} />
              </div>
            ) : null}
          </div>

          {error ? <div className="mt-4 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

          {!card ? (
            <section className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="glass rounded-2xl p-6 shadow-soft">
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Creation Wizard</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setStep(value)}
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${step === value ? "bg-[var(--primary)] text-white" : "border border-[var(--stroke)] bg-white/80 text-[var(--navy)]"}`}
                    >
                      Step {value}
                    </button>
                  ))}
                </div>

                {step === 1 ? (
                  <div className="mt-5 space-y-3">
                    <p className="text-sm font-semibold">Select evaluation</p>
                    {evaluations.length === 0 ? <p className="text-sm text-[var(--muted)]">No evaluations found. Run one first.</p> : null}
                    {evaluations.map((evaluation) => (
                      <label key={evaluation.id} className="flex cursor-pointer items-center justify-between rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <div>
                          <p className="text-sm font-semibold text-[var(--navy)]">{evaluation.prediction_response?.final_prediction || "Saved evaluation"}</p>
                          <p className="text-xs text-[var(--muted)]">{evaluation.created_at ? new Date(evaluation.created_at).toLocaleString() : evaluation.id}</p>
                        </div>
                        <input
                          type="radio"
                          checked={selectedEvalId === evaluation.id}
                          onChange={() => setSelectedEvalId(evaluation.id)}
                        />
                      </label>
                    ))}
                    <button
                      type="button"
                      onClick={() => setStep(2)}
                      disabled={!selectedEvalId}
                      className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      Continue
                    </button>
                  </div>
                ) : null}

                {step === 2 ? (
                  <div className="mt-5 space-y-3">
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">Display name</span>
                      <input value={draftDisplayName} onChange={(e) => setDraftDisplayName(e.target.value)} className="form-control" />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">High school</span>
                      <input value={draftHighSchool} onChange={(e) => setDraftHighSchool(e.target.value)} className="form-control" />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">Class year</span>
                      <input value={draftClassYear} onChange={(e) => setDraftClassYear(e.target.value)} className="form-control" type="number" />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">Photo (optional)</span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="form-control"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          setPendingPhoto(file);
                          setPendingPhotoPreview(file ? URL.createObjectURL(file) : null);
                        }}
                      />
                    </label>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setStep(1)} className="rounded-full border border-[var(--stroke)] px-4 py-2 text-sm">
                        Back
                      </button>
                      <button type="button" onClick={() => setStep(3)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                        Continue
                      </button>
                    </div>
                  </div>
                ) : null}

                {step === 3 ? (
                  <div className="mt-5 space-y-3">
                    <p className="text-sm font-semibold">Video links</p>
                    {draftVideoLinks.map((link, index) => (
                      <div key={index} className="grid gap-2 md:grid-cols-3">
                        <input
                          value={link.label}
                          onChange={(e) =>
                            setDraftVideoLinks((prev) => prev.map((item, i) => (i === index ? { ...item, label: e.target.value } : item)))
                          }
                          placeholder="Label"
                          className="form-control"
                        />
                        <input
                          value={link.url}
                          onChange={(e) =>
                            setDraftVideoLinks((prev) => prev.map((item, i) => (i === index ? { ...item, url: e.target.value } : item)))
                          }
                          placeholder="URL"
                          className="form-control md:col-span-2"
                        />
                      </div>
                    ))}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold"
                        onClick={() => setDraftVideoLinks((prev) => [...prev, { url: "", label: "", platform: "general" }])}
                      >
                        Add Link
                      </button>
                      <button type="button" onClick={() => setStep(4)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                        Continue
                      </button>
                    </div>
                  </div>
                ) : null}

                {step === 4 ? (
                  <div className="mt-5 space-y-3">
                    <p className="text-sm font-semibold">Preference visibility</p>
                    <PreferenceVisibilityToggles values={draftVisibility} onChange={setDraftVisibility} />
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setStep(3)} className="rounded-full border border-[var(--stroke)] px-4 py-2 text-sm">
                        Back
                      </button>
                      <button type="button" onClick={() => setStep(5)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                        Continue
                      </button>
                    </div>
                  </div>
                ) : null}

                {step === 5 ? (
                  <div className="mt-5 space-y-3">
                    <p className="text-sm text-[var(--muted)]">Preview your card and confirm to create it.</p>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setStep(4)} className="rounded-full border border-[var(--stroke)] px-4 py-2 text-sm">
                        Back
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleCreateCard()}
                        disabled={submitting || !selectedEvalId}
                        className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      >
                        {submitting ? "Creating..." : "Create Card"}
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="glass rounded-2xl p-6 shadow-soft">
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Card Preview</p>
                <div ref={cardRef} className="mt-4 flex justify-center">
                  <PlayerCardContainer front={previewFront} back={previewBack} />
                </div>
              </div>
            </section>
          ) : (
            <section className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="glass rounded-2xl p-6 shadow-soft">
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Live Card Preview</p>
                <div ref={cardRef} className="mt-4 flex justify-center">
                  <PlayerCardContainer front={previewFront} back={previewBack} />
                </div>
              </div>

              <div className="glass rounded-2xl p-6 shadow-soft">
                <div className="mb-4 flex flex-wrap gap-2">
                  {(["edit", "share", "analytics"] as Tab[]).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setActiveTab(tab)}
                      className={`rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] ${activeTab === tab ? "bg-[var(--primary)] text-white" : "border border-[var(--stroke)] bg-white/80 text-[var(--navy)]"}`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                {activeTab === "edit" ? (
                  <div className="space-y-3">
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">Display name</span>
                      <input value={editDisplayName} onChange={(e) => setEditDisplayName(e.target.value)} className="form-control" />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">High school</span>
                      <input value={editHighSchool} onChange={(e) => setEditHighSchool(e.target.value)} className="form-control" />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-sm font-semibold text-[var(--navy)]">Class year</span>
                      <input value={editClassYear} onChange={(e) => setEditClassYear(e.target.value)} className="form-control" type="number" />
                    </label>

                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-sm font-semibold text-[var(--navy)]">Photo</p>
                      <div className="mt-2">
                        <PhotoUpload
                          accessToken={accessToken || ""}
                          currentPhotoUrl={card.photo_url}
                          onUploaded={(photoUrl) => setCard((prev) => (prev ? { ...prev, photo_url: photoUrl } : prev))}
                        />
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-sm font-semibold text-[var(--navy)]">Video links</p>
                      <div className="mt-2 space-y-2">
                        {editVideoLinks.map((link, index) => (
                          <div key={index} className="grid gap-2 md:grid-cols-3">
                            <input
                              value={link.label}
                              onChange={(e) =>
                                setEditVideoLinks((prev) => prev.map((item, i) => (i === index ? { ...item, label: e.target.value } : item)))
                              }
                              placeholder="Label"
                              className="form-control"
                            />
                            <input
                              value={link.url}
                              onChange={(e) =>
                                setEditVideoLinks((prev) => prev.map((item, i) => (i === index ? { ...item, url: e.target.value } : item)))
                              }
                              placeholder="URL"
                              className="form-control md:col-span-2"
                            />
                          </div>
                        ))}
                        <button
                          type="button"
                          className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold"
                          onClick={() => setEditVideoLinks((prev) => [...prev, { url: "", label: "", platform: "general" }])}
                        >
                          Add Link
                        </button>
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-sm font-semibold text-[var(--navy)]">Visible preferences</p>
                      <div className="mt-2">
                        <PreferenceVisibilityToggles values={editVisibility} onChange={setEditVisibility} />
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => void handleUpdateCard()}
                      disabled={submitting}
                      className="rounded-full bg-[var(--primary)] px-5 py-2 text-sm font-semibold text-white"
                    >
                      {submitting ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                ) : null}

                {activeTab === "share" && accessToken ? <ShareLinkGenerator accessToken={accessToken} /> : null}
                {activeTab === "analytics" && accessToken ? <CardAnalyticsPanel accessToken={accessToken} /> : null}
              </div>
            </section>
          )}

          {!evaluations.length ? (
            <div className="mt-8 rounded-2xl border border-[var(--stroke)] bg-white/75 p-5 text-sm text-[var(--muted)]">
              Run an evaluation first to create a card. <Link href="/predict" className="font-semibold text-[var(--primary)]">Go to Predict</Link>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
