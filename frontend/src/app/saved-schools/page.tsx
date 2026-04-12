"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PreferencePoint = {
  preference?: string;
  description?: string;
};

type PreferenceMiss = {
  preference?: string;
  reason?: string;
};

type SavedSchoolDetail = {
  school_name?: string;
  display_school_name?: string;
  school_logo_image?: string | null;
  division_group?: string;
  division_label?: string;
  location?: {
    state?: string;
  };
  academics?: {
    grade?: string;
  };
  athletics?: {
    grade?: string;
  };
  match_analysis?: {
    total_nice_to_have_matches?: number;
    pros?: PreferencePoint[];
    cons?: PreferenceMiss[];
  };
  scores?: {
    playing_time_score?: number | null;
  };
  playing_time?: {
    available?: boolean;
    percentile?: number | null;
    bucket?: string | null;
    interpretation?: string | null;
    message?: string | null;
  };
};

type SavedSchoolRecord = {
  id: string;
  school_name: string;
  school_logo_image?: string | null;
  dedupe_key?: string;
  school_data?: SavedSchoolDetail;
  note?: string | null;
  created_at?: string;
  updated_at?: string;
};

type SavedSchoolsResponse = {
  items: SavedSchoolRecord[];
  count?: number;
};

function getPlayingTimePreview(school: SavedSchoolDetail | undefined): string {
  if (!school) return "Playing-time analysis unavailable";
  const playingTime = school.playing_time;
  if (playingTime?.available) {
    const bucket = playingTime.bucket || "Estimate available";
    if (typeof playingTime.percentile === "number") {
      return `${bucket} · ${playingTime.percentile.toFixed(1)} percentile`;
    }
    return bucket;
  }

  if (typeof school.scores?.playing_time_score === "number") {
    return `${school.scores.playing_time_score.toFixed(1)} score`;
  }

  return playingTime?.message || "Playing-time analysis unavailable";
}

function getNcaLogoUrl(record: SavedSchoolRecord): string | null {
  const logoKey = (record.school_logo_image || record.school_data?.school_logo_image || "").trim();
  if (!logoKey) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(logoKey)}.svg`;
}

function mapLegacyDivisionGroup(group: string | undefined): string | null {
  if (!group) return null;
  const lowered = group.trim().toLowerCase();
  if (!lowered) return null;
  if (lowered.includes("power") && lowered.includes("4")) return "Power 4";
  if (lowered.includes("non-p4") || lowered.includes("non p4")) return "Division 1";
  if (lowered.includes("non-d1") || lowered.includes("non d1")) return null;
  if (lowered.includes("d3") || lowered.includes("division 3") || lowered.includes("division iii")) return "Division 3";
  if (lowered.includes("d2") || lowered.includes("division 2") || lowered.includes("division ii")) return "Division 2";
  if (lowered.includes("d1") || lowered.includes("division 1") || lowered.includes("division i")) return "Division 1";
  return null;
}

function getDivisionBadgeLabel(detail: SavedSchoolDetail | undefined): string | null {
  if (!detail) return null;
  return detail.division_label || mapLegacyDivisionGroup(detail.division_group);
}

function getDisplaySchoolName(record: SavedSchoolRecord): string {
  return record.school_data?.display_school_name || record.school_name;
}

export default function SavedSchoolsPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/saved-schools");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedSchools, setSavedSchools] = useState<SavedSchoolRecord[]>([]);
  const [selectedSavedSchoolId, setSelectedSavedSchoolId] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [deletingSchool, setDeletingSchool] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadSavedSchools() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/saved-schools`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const payload = (await response.json()) as SavedSchoolsResponse | { detail?: string };
        if (!response.ok) {
          throw new Error(
            typeof payload === "object" && payload && "detail" in payload
              ? payload.detail || "Failed to load saved schools."
              : "Failed to load saved schools.",
          );
        }
        if (!mounted) return;
        const items = (payload as SavedSchoolsResponse).items || [];
        setSavedSchools(items);
      } catch (loadError) {
        if (!mounted) return;
        setError(loadError instanceof Error ? loadError.message : "Failed to load saved schools.");
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    }

    void loadSavedSchools();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  useEffect(() => {
    if (savedSchools.length === 0) {
      setSelectedSavedSchoolId(null);
      setNoteDraft("");
      return;
    }
    if (!selectedSavedSchoolId || !savedSchools.some((school) => school.id === selectedSavedSchoolId)) {
      setSelectedSavedSchoolId(savedSchools[0].id);
    }
  }, [savedSchools, selectedSavedSchoolId]);

  const selectedSavedSchool = useMemo(() => {
    if (!selectedSavedSchoolId) return null;
    return savedSchools.find((school) => school.id === selectedSavedSchoolId) || null;
  }, [savedSchools, selectedSavedSchoolId]);

  useEffect(() => {
    setNoteDraft(selectedSavedSchool?.note || "");
    setSaveMessage("");
  }, [selectedSavedSchool?.id, selectedSavedSchool?.note]);

  async function saveNote() {
    if (!accessToken || !selectedSavedSchool || savingNote) return;
    setSavingNote(true);
    setSaveMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/saved-schools/${selectedSavedSchool.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          note: noteDraft.trim() || "",
        }),
      });
      const payload = (await response.json()) as SavedSchoolRecord | { detail?: string };
      if (!response.ok) {
        throw new Error(
          typeof payload === "object" && payload && "detail" in payload
            ? payload.detail || "Failed to save note."
            : "Failed to save note.",
        );
      }

      const updated = payload as SavedSchoolRecord;
      setSavedSchools((current) => current.map((school) => (school.id === updated.id ? { ...school, ...updated } : school)));
      setSaveMessage("Note saved.");
    } catch (saveError) {
      setSaveMessage(saveError instanceof Error ? saveError.message : "Failed to save note.");
    } finally {
      setSavingNote(false);
    }
  }

  async function unsaveSelectedSchool() {
    if (!accessToken || !selectedSavedSchool || deletingSchool) return;
    const confirmed = window.confirm(
      `Remove ${getDisplaySchoolName(selectedSavedSchool)} from your saved schools list?`,
    );
    if (!confirmed) return;

    setDeletingSchool(true);
    setSaveMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/saved-schools/${selectedSavedSchool.id}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to remove saved school.");
      }
      setSavedSchools((current) => current.filter((school) => school.id !== selectedSavedSchool.id));
      setSaveMessage("School removed from saved list.");
    } catch (deleteError) {
      setSaveMessage(deleteError instanceof Error ? deleteError.message : "Failed to remove saved school.");
    } finally {
      setDeletingSchool(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading saved schools...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 pt-5 pb-10 md:pt-6 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="display-font mt-2 text-4xl md:text-5xl">Your saved school list</h1>
              <p className="mt-2 pl-1 text-sm text-[var(--muted)]">{savedSchools.length} saved schools</p>
            </div>
            <Link
              href="/predict"
              className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold !text-white shadow-strong"
            >
              Run New Evaluation
            </Link>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

          {savedSchools.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-[var(--stroke)] bg-white/80 p-6">
              <p className="text-sm font-semibold text-[var(--navy)]">No saved schools yet.</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Open an evaluation report and use the Save School action on a school you want to track.
              </p>
              <Link
                href="/evaluations"
                className="mt-4 inline-flex rounded-full bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white"
              >
                Go to Evaluations
              </Link>
            </div>
          ) : (
            <section className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="space-y-3">
                {savedSchools.map((record) => {
                  const isActive = record.id === selectedSavedSchoolId;
                  const logoUrl = getNcaLogoUrl(record);
                  const detail = record.school_data;
                  return (
                    <button
                      key={record.id}
                      type="button"
                      onClick={() => setSelectedSavedSchoolId(record.id)}
                      className={`w-full rounded-2xl border bg-white/80 p-4 text-left shadow-soft transition duration-200 ${isActive
                          ? "border-[var(--primary)] ring-1 ring-[var(--primary)]"
                          : "border-[var(--stroke)] hover:-translate-y-0.5 hover:border-[var(--primary)]/40"
                        }`}
                    >
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3">
                        <div className="min-w-0">
                          <p className="text-base font-semibold text-[var(--foreground)]">{getDisplaySchoolName(record)}</p>
                          <div className="mt-1 grid gap-1 text-sm text-[var(--muted)]">
                            <p>
                              Matching preferences:{" "}
                              <span className="font-semibold text-[var(--navy)]">{detail?.match_analysis?.total_nice_to_have_matches ?? 0}</span>
                            </p>
                            <p>
                              Playing-time calc: <span className="font-semibold text-[var(--navy)]">{getPlayingTimePreview(detail)}</span>
                            </p>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-2">
                          {logoUrl ? (
                            <>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={logoUrl}
                                alt={`${getDisplaySchoolName(record)} logo`}
                                loading="lazy"
                                onError={(event) => {
                                  event.currentTarget.style.display = "none";
                                }}
                                className="h-14 w-14 rounded-md border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
                              />
                            </>
                          ) : null}
                          {getDivisionBadgeLabel(detail) && (
                            <span className="whitespace-nowrap rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                              {getDivisionBadgeLabel(detail)}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              <aside className="glass rounded-2xl p-5 shadow-soft lg:sticky lg:top-24 lg:max-h-[76vh] lg:overflow-hidden">
                {selectedSavedSchool ? (
                  <div className="flex h-full flex-col">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-lg font-semibold">{getDisplaySchoolName(selectedSavedSchool)}</p>
                      {getDivisionBadgeLabel(selectedSavedSchool.school_data) && (
                        <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                          {getDivisionBadgeLabel(selectedSavedSchool.school_data)}
                        </span>
                      )}
                    </div>

                    <p className="mt-2 text-sm text-[var(--muted)]">
                      {selectedSavedSchool.school_data?.location?.state
                        ? `State: ${selectedSavedSchool.school_data.location.state} · `
                        : ""}
                      {selectedSavedSchool.school_data?.academics?.grade
                        ? `Academics: ${selectedSavedSchool.school_data.academics.grade} · `
                        : ""}
                      {selectedSavedSchool.school_data?.athletics?.grade
                        ? `Athletics: ${selectedSavedSchool.school_data.athletics.grade}`
                        : "Athletics grade unavailable"}
                    </p>

                    <div className="mt-4 rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">School note</p>
                      <textarea
                        value={noteDraft}
                        onChange={(event) => setNoteDraft(event.target.value)}
                        placeholder="Write what you want to do at this school."
                        className="form-control mt-3 min-h-[120px] resize-y text-sm"
                      />
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={saveNote}
                            disabled={savingNote || deletingSchool}
                            className="rounded-full bg-[var(--primary)] px-4 py-2 text-xs font-semibold !text-white shadow-strong disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {savingNote ? "Saving..." : "Save note"}
                          </button>
                          <button
                            type="button"
                            onClick={unsaveSelectedSchool}
                            disabled={deletingSchool || savingNote}
                            className="rounded-full border border-red-300 bg-white px-4 py-2 text-xs font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {deletingSchool ? "Removing..." : "Unsave school"}
                          </button>
                        </div>
                        <span className="text-xs text-[var(--muted)]">
                          {selectedSavedSchool.updated_at
                            ? `Updated ${new Date(selectedSavedSchool.updated_at).toLocaleString()}`
                            : ""}
                        </span>
                      </div>
                      {saveMessage ? <p className="mt-2 text-xs text-[var(--muted)]">{saveMessage}</p> : null}
                    </div>

                    <div className="mt-4 space-y-3 overflow-y-auto pr-1 lg:max-h-[52vh]">
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Why this matches</p>
                        {selectedSavedSchool.school_data?.match_analysis?.pros?.length ? (
                          <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                            {selectedSavedSchool.school_data.match_analysis.pros.map((pro, index) => (
                              <li key={`${pro.preference}-${index}`}>- {pro.description || pro.preference}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-[var(--muted)]">No preference matches recorded.</p>
                        )}
                      </div>

                      <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Tradeoffs</p>
                        {selectedSavedSchool.school_data?.match_analysis?.cons?.length ? (
                          <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                            {selectedSavedSchool.school_data.match_analysis.cons.map((con, index) => (
                              <li key={`${con.preference}-${index}`}>- {con.reason || con.preference}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-[var(--muted)]">No major preference tradeoffs detected.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                    <p className="text-sm text-[var(--muted)]">Select a saved school to view details and edit notes.</p>
                  </div>
                )}
              </aside>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
