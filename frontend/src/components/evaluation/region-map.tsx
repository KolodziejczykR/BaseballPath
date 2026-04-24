"use client";

import { useState } from "react";
import {
  STATE_PATHS,
  REGION_COLORS,
  getStateRegion,
} from "./us-states-data";

type RegionName = "Northeast" | "Southeast" | "Midwest" | "Southwest" | "West";

const REGIONS: { name: RegionName; label: string; color: string }[] = [
  { name: "Northeast", label: "Northeast", color: "var(--primary)" },
  { name: "Southeast", label: "Southeast", color: "var(--copper)" },
  { name: "Midwest", label: "Midwest", color: "var(--sage-green)" },
  { name: "Southwest", label: "Southwest", color: "var(--golden-sand)" },
  { name: "West", label: "West", color: "var(--walnut)" },
];

type RegionMapProps = {
  selected: RegionName[];
  onChange: (regions: RegionName[]) => void;
  selectedStates: string[];
  onStatesChange: (states: string[]) => void;
  excludedStates: string[];
  onExcludedStatesChange: (states: string[]) => void;
};

export function RegionMap({
  selected,
  onChange,
  selectedStates,
  onStatesChange,
  excludedStates,
  onExcludedStatesChange,
}: RegionMapProps) {
  const [hoveredState, setHoveredState] = useState<string | null>(null);

  // "All selected" means no explicit filter — everything is in play.
  const noFilter =
    selected.length === 0 &&
    selectedStates.length === 0 &&
    excludedStates.length === 0;

  function statesInRegion(region: RegionName): string[] {
    return Object.keys(STATE_PATHS).filter(
      (abbr) => getStateRegion(abbr) === region,
    );
  }

  function toggleRegion(name: RegionName) {
    const regionStates = statesInRegion(name);
    if (selected.includes(name)) {
      // Deselecting a region — drop any exclusions inside it (they're
      // meaningless without the region) and any individual inclusions
      // (the state isn't covered by any region anymore, so clearing is
      // safer than leaving stale selections).
      onChange(selected.filter((r) => r !== name));
      const clean = (arr: string[]) =>
        arr.filter((s) => !regionStates.includes(s));
      onExcludedStatesChange(clean(excludedStates));
      onStatesChange(clean(selectedStates));
    } else {
      const next = [...selected, name];
      // States individually included in this region are now redundant
      // (covered by the region); clear them to keep state tidy.
      const pruned = selectedStates.filter((s) => !regionStates.includes(s));
      if (next.length === REGIONS.length) {
        // All regions selected → no filter; clear everything.
        onChange([]);
        onStatesChange([]);
        onExcludedStatesChange([]);
      } else {
        onChange(next);
        if (pruned.length !== selectedStates.length) {
          onStatesChange(pruned);
        }
      }
    }
  }

  function clearAll() {
    onChange([]);
    onStatesChange([]);
    onExcludedStatesChange([]);
  }

  function toggleState(abbr: string) {
    const region = getStateRegion(abbr) as RegionName | null;
    const regionSelected = region != null && selected.includes(region);

    if (regionSelected) {
      // State's region is selected — clicking toggles exclusion.
      if (excludedStates.includes(abbr)) {
        onExcludedStatesChange(excludedStates.filter((s) => s !== abbr));
      } else {
        onExcludedStatesChange([...excludedStates, abbr]);
      }
    } else {
      // State's region is NOT selected — clicking toggles individual
      // inclusion.
      if (selectedStates.includes(abbr)) {
        onStatesChange(selectedStates.filter((s) => s !== abbr));
      } else {
        onStatesChange([...selectedStates, abbr]);
      }
    }
  }

  function isStateActive(abbr: string): boolean {
    if (noFilter) return true;
    if (excludedStates.includes(abbr)) return false;
    if (selectedStates.includes(abbr)) return true;
    const region = getStateRegion(abbr) as RegionName | null;
    return region != null && selected.includes(region);
  }

  function isRegionActive(name: RegionName): boolean {
    return noFilter || selected.includes(name);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-[var(--foreground)]">
          Preferred regions & states
        </p>
        <button
          type="button"
          onClick={clearAll}
          className="text-xs font-semibold text-[var(--primary)] hover:underline"
        >
          {noFilter ? "All selected" : "Clear"}
        </button>
      </div>

      <p className="text-xs text-[var(--muted)]">
        Click the region chips for whole regions, then click states on the
        map to add or remove individual ones.
      </p>

      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 959 593"
        className="w-full max-w-lg mx-auto"
        style={{ filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.08))" }}
      >
        {Object.entries(STATE_PATHS).map(([abbr, d]) => {
          const region = getStateRegion(abbr) as RegionName | null;
          if (!region) return null;

          const active = isStateActive(abbr);
          const hovered = hoveredState === abbr;
          const regionColor = REGION_COLORS[region] || "var(--stroke)";
          const individuallyIncluded = selectedStates.includes(abbr);
          const excluded = excludedStates.includes(abbr);

          return (
            <path
              key={abbr}
              d={d}
              fill={active ? regionColor : "var(--clay-mist)"}
              fillOpacity={
                active ? (hovered ? 0.9 : 0.65) : hovered ? 0.4 : 0.25
              }
              stroke={
                excluded
                  ? "var(--danger, #c0392b)"
                  : individuallyIncluded
                    ? "var(--foreground)"
                    : active
                      ? regionColor
                      : "var(--stroke)"
              }
              strokeWidth={excluded || individuallyIncluded ? 1.4 : active ? 1 : 0.5}
              strokeDasharray={excluded ? "3 2" : undefined}
              strokeLinejoin="round"
              onClick={() => toggleState(abbr)}
              onMouseEnter={() => setHoveredState(abbr)}
              onMouseLeave={() => setHoveredState(null)}
              style={{
                cursor: "pointer",
                transition: "fill-opacity 200ms, stroke-width 200ms",
              }}
            >
              <title>{abbr}</title>
            </path>
          );
        })}
      </svg>

      {/* Region chips below map */}
      <div className="flex flex-wrap gap-2 justify-center">
        {REGIONS.map(({ name, label, color }) => {
          const active = isRegionActive(name);
          return (
            <button
              key={name}
              type="button"
              onClick={() => toggleRegion(name)}
              className="rounded-full px-3 py-1 text-xs font-semibold transition-all"
              style={{
                background: active ? color : "transparent",
                color: active ? "white" : "var(--muted)",
                border: `1.5px solid ${active ? color : "var(--stroke)"}`,
                opacity: active ? 1 : 0.7,
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Chip rows summarising individual additions / exclusions */}
      {(selectedStates.length > 0 || excludedStates.length > 0) && (
        <div className="space-y-1.5 pt-1">
          {selectedStates.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-center">
              <span className="text-xs text-[var(--muted)] self-center mr-1">
                Also included:
              </span>
              {selectedStates.map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => toggleState(st)}
                  className="rounded-full px-2 py-0.5 text-[11px] font-semibold transition-all"
                  style={{
                    background: "var(--foreground)",
                    color: "var(--background)",
                    border: "1px solid var(--foreground)",
                  }}
                  title="Click to remove"
                >
                  {st} ✕
                </button>
              ))}
            </div>
          )}
          {excludedStates.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-center">
              <span className="text-xs text-[var(--muted)] self-center mr-1">
                Excluded:
              </span>
              {excludedStates.map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => toggleState(st)}
                  className="rounded-full px-2 py-0.5 text-[11px] font-semibold transition-all"
                  style={{
                    background: "transparent",
                    color: "var(--danger, #c0392b)",
                    border: "1px dashed var(--danger, #c0392b)",
                  }}
                  title="Click to re-include"
                >
                  {st} ✕
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export type { RegionName };
