"use client";

import { useMemo, useState } from "react";
import {
  STATE_PATHS,
  REGION_STATES,
  REGION_COLORS,
  getStateRegion,
} from "./us-states-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SchoolPin = {
  rank: number;
  school_name: string;
  state: string;
};

type ResultsMapProps = {
  schools: SchoolPin[];
  selectedRank: number | null;
  onSelect: (rank: number) => void;
  highlightedRegions?: string[] | null;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResultsMap({ schools, selectedRank, onSelect, highlightedRegions }: ResultsMapProps) {
  const [hoveredState, setHoveredState] = useState<string | null>(null);

  // Group schools by state → { state: SchoolPin[] }
  const schoolsByState = useMemo(() => {
    const map: Record<string, SchoolPin[]> = {};
    for (const s of schools) {
      const st = s.state?.toUpperCase();
      if (!st) continue;
      if (!map[st]) map[st] = [];
      map[st].push(s);
    }
    return map;
  }, [schools]);

  // Set of states that have schools
  const schoolStates = useMemo(() => new Set(Object.keys(schoolsByState)), [schoolsByState]);

  // Build set of highlighted region states
  const highlightedStates = useMemo(() => {
    if (!highlightedRegions || highlightedRegions.length === 0) return null;
    const s = new Set<string>();
    for (const region of highlightedRegions) {
      const states = REGION_STATES[region];
      if (states) states.forEach((st) => s.add(st));
    }
    return s;
  }, [highlightedRegions]);

  // Which state is selected (from selectedRank)
  const selectedState = useMemo(() => {
    if (selectedRank == null) return null;
    const school = schools.find((s) => s.rank === selectedRank);
    return school?.state?.toUpperCase() || null;
  }, [selectedRank, schools]);

  function handleStateClick(abbr: string) {
    const stateSchools = schoolsByState[abbr];
    if (!stateSchools || stateSchools.length === 0) return;
    // If already viewing a school in this state, cycle to the next one
    const currentIdx = stateSchools.findIndex((s) => s.rank === selectedRank);
    const nextIdx = (currentIdx + 1) % stateSchools.length;
    onSelect(stateSchools[nextIdx].rank);
  }

  return (
    <div className="glass rounded-2xl p-4 shadow-soft">
      <p className="mb-3 text-xs uppercase tracking-[0.3em] text-[var(--muted)]">School locations</p>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 959 593"
        className="w-full"
        style={{ maxHeight: 400 }}
      >
        {/* State outlines */}
        <g>
          {Object.entries(STATE_PATHS).map(([abbr, d]) => {
            const hasSchool = schoolStates.has(abbr);
            const region = getStateRegion(abbr);
            const inHighlighted = highlightedStates ? highlightedStates.has(abbr) : true;
            const regionColor = region ? REGION_COLORS[region] : "var(--stroke)";
            const isHovered = hoveredState === abbr && hasSchool;
            const isSelected = selectedState === abbr;

            let fill: string;
            let fillOpacity: number;
            let stroke: string;

            if (hasSchool) {
              fill = regionColor;
              fillOpacity = isSelected ? 0.55 : isHovered ? 0.45 : 0.3;
              stroke = regionColor;
            } else if (inHighlighted) {
              fill = "var(--cool-stroke-strong)";
              fillOpacity = 0.55;
              stroke = "var(--cool-stroke-strong)";
            } else {
              fill = "var(--cool-stroke-strong)";
              fillOpacity = 0.4;
              stroke = "var(--cool-stroke-strong)";
            }

            return (
              <path
                key={abbr}
                d={d}
                fill={fill}
                fillOpacity={fillOpacity}
                stroke={stroke}
                strokeWidth={isSelected ? 2 : hasSchool ? 1.2 : 0.7}
                strokeLinejoin="round"
                onClick={() => handleStateClick(abbr)}
                onMouseEnter={() => hasSchool && setHoveredState(abbr)}
                onMouseLeave={() => setHoveredState(null)}
                style={{
                  cursor: hasSchool ? "pointer" : "default",
                  transition: "fill-opacity 150ms, stroke-width 150ms",
                }}
              />
            );
          })}
        </g>

      </svg>
    </div>
  );
}
