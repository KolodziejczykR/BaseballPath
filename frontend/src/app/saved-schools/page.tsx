"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  MetricComparisonsSection,
  ResearchSourcesCard,
  type School,
  SchoolCompareCard,
  SchoolFitBadges,
  SchoolHeader,
  SchoolListCard,
  SchoolStatsGrid,
  WhyThisSchoolCard,
} from "@/components/evaluation/school-display";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SavedSchoolRecord = {
  id: string;
  school_name: string;
  school_logo_image?: string | null;
  dedupe_key?: string;
  school_data?: School;
  note?: string | null;
  created_at?: string;
  updated_at?: string;
};

type SavedSchoolsResponse = {
  items: SavedSchoolRecord[];
  count?: number;
};

function getRecordSchool(record: SavedSchoolRecord): School {
  // Saved rows from before the eval-style detail panel landed may only have
  // the top-level fields the API returns; merge them so the display still has
  // a name + logo to render.
  return {
    school_name: record.school_name,
    school_logo_image: record.school_logo_image ?? null,
    ...(record.school_data || {}),
  };
}

function getRecordDisplayName(record: SavedSchoolRecord): string {
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
  const [compareMode, setCompareMode] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);

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

  const selectedSchool = useMemo(
    () => (selectedSavedSchool ? getRecordSchool(selectedSavedSchool) : null),
    [selectedSavedSchool],
  );

  const comparePair = useMemo<[School, School] | null>(() => {
    if (compareIds.length !== 2) return null;
    const records = compareIds
      .map((id) => savedSchools.find((school) => school.id === id))
      .filter((record): record is SavedSchoolRecord => Boolean(record));
    if (records.length !== 2) return null;
    return [getRecordSchool(records[0]), getRecordSchool(records[1])];
  }, [compareIds, savedSchools]);

  useEffect(() => {
    setNoteDraft(selectedSavedSchool?.note || "");
    setSaveMessage("");
  }, [selectedSavedSchool?.id, selectedSavedSchool?.note]);

  // Drop ids that no longer exist (e.g. after unsave) from the compare slots.
  useEffect(() => {
    setCompareIds((current) => current.filter((id) => savedSchools.some((school) => school.id === id)));
  }, [savedSchools]);

  function toggleCompareSelection(id: string) {
    setCompareIds((current) => {
      if (current.includes(id)) return current.filter((existing) => existing !== id);
      if (current.length >= 2) return current;
      return [...current, id];
    });
  }

  function exitCompareMode() {
    setCompareMode(false);
    setCompareIds([]);
  }

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
      setSavedSchools((current) =>
        current.map((school) => (school.id === updated.id ? { ...school, ...updated } : school)),
      );
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
      `Remove ${getRecordDisplayName(selectedSavedSchool)} from your saved schools list?`,
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

      <main className="px-6 pt-10 pb-10 md:pt-14 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">
                Your Shortlist
              </p>
              <h1 className="display-font text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight mt-3">
                Saved schools.
              </h1>
              <p className="mt-3 text-sm text-[var(--cool-ink-muted)]">
                {savedSchools.length} saved {savedSchools.length === 1 ? "school" : "schools"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {savedSchools.length >= 2 && (
                <button
                  type="button"
                  onClick={() => (compareMode ? exitCompareMode() : setCompareMode(true))}
                  aria-pressed={compareMode}
                  className={`rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${
                    compareMode
                      ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "border-[var(--cool-stroke)] bg-white text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)]"
                  }`}
                >
                  {compareMode ? "Exit compare" : "Compare schools"}
                </button>
              )}
              <Link
                href="/predict"
                className="rounded-full bg-[var(--burnt-sienna)] px-5 py-2.5 text-sm font-semibold !text-white shadow-cool hover:-translate-y-0.5 transition-transform"
              >
                Run New Evaluation
              </Link>
            </div>
          </div>

          {compareMode && (
            <div className="mt-5 rounded-2xl border border-[var(--primary)]/30 bg-[var(--primary)]/5 p-4 text-sm text-[var(--cool-ink)]">
              <p className="font-semibold">Pick two schools to compare.</p>
              <p className="mt-1 text-xs text-[var(--cool-ink-muted)]">
                Selected {compareIds.length} of 2. Tap a card to add or remove it.
              </p>
            </div>
          )}

          {error ? (
            <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          ) : null}

          {savedSchools.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-[var(--stroke)] bg-white/80 p-6">
              <p className="text-sm font-semibold text-[var(--navy)]">No saved schools yet.</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Open an evaluation report and use the Save School action on a school you want to track.
              </p>
              <Link
                href="/evaluations"
                className="mt-4 inline-flex rounded-full bg-[var(--burnt-sienna)] px-4 py-1.5 text-xs font-semibold !text-white shadow-cool hover:-translate-y-0.5 transition-transform"
              >
                Go to Evaluations
              </Link>
            </div>
          ) : (
            <section className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
              <div className="space-y-3">
                {savedSchools.map((record) => {
                  const isCompareSelected = compareIds.includes(record.id);
                  const isCompareSelectable = compareIds.length < 2 || isCompareSelected;
                  return (
                    <SchoolListCard
                      key={record.id}
                      school={getRecordSchool(record)}
                      isActive={record.id === selectedSavedSchoolId}
                      onSelect={() =>
                        compareMode
                          ? toggleCompareSelection(record.id)
                          : setSelectedSavedSchoolId(record.id)
                      }
                      showRankMedal={false}
                      selectionMode={compareMode}
                      isSelected={isCompareSelected}
                      isSelectable={isCompareSelectable}
                    />
                  );
                })}
              </div>

              <aside className="glass rounded-2xl p-5 shadow-soft lg:sticky lg:top-24 lg:max-h-[82vh] lg:overflow-y-auto">
                {compareMode ? (
                  comparePair ? (
                    <SchoolCompareCard schools={comparePair} />
                  ) : (
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-6 text-center">
                      <p className="text-sm font-semibold text-[var(--foreground)]">
                        Pick two saved schools to see a side-by-side comparison.
                      </p>
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        Selected {compareIds.length} of 2.
                      </p>
                    </div>
                  )
                ) : selectedSavedSchool && selectedSchool ? (
                  <div key={selectedSavedSchool.id} className="detail-slide-in space-y-4">
                    <SchoolHeader school={selectedSchool} showRankMedal={false} />
                    <SchoolFitBadges school={selectedSchool} />
                    <SchoolStatsGrid school={selectedSchool} />

                    <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">School note</p>
                      <textarea
                        value={noteDraft}
                        onChange={(event) => setNoteDraft(event.target.value)}
                        placeholder="Write what you want to do at this school."
                        className="form-control mt-3 min-h-[96px] resize-y text-sm"
                      />
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
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

                    <WhyThisSchoolCard school={selectedSchool} />
                    <ResearchSourcesCard sources={selectedSchool.research_sources} />
                    <MetricComparisonsSection school={selectedSchool} />
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

      <style jsx>{`
        .detail-slide-in {
          animation: detailSlideIn 220ms ease;
        }
        @keyframes detailSlideIn {
          from {
            opacity: 0;
            transform: translateX(12px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
