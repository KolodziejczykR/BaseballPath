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
};

export function RegionMap({ selected, onChange }: RegionMapProps) {
  const [hoveredRegion, setHoveredRegion] = useState<RegionName | null>(null);

  const allSelected = selected.length === 0 || selected.length === REGIONS.length;

  function toggleRegion(name: RegionName) {
    if (allSelected) {
      onChange([name]);
      return;
    }
    if (selected.includes(name)) {
      const next = selected.filter((r) => r !== name);
      if (next.length === 0) {
        onChange([]);
      } else {
        onChange(next);
      }
    } else {
      const next = [...selected, name];
      if (next.length === REGIONS.length) {
        onChange([]);
      } else {
        onChange(next);
      }
    }
  }

  function selectAll() {
    onChange([]);
  }

  function isRegionActive(name: RegionName): boolean {
    return allSelected || selected.includes(name);
  }

  function handleStateClick(abbr: string) {
    const region = getStateRegion(abbr) as RegionName | null;
    if (region) toggleRegion(region);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-[var(--foreground)]">Preferred regions</p>
        <button
          type="button"
          onClick={selectAll}
          className="text-xs font-semibold text-[var(--primary)] hover:underline"
        >
          {allSelected ? "All selected" : "Select all"}
        </button>
      </div>

      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 959 593"
        className="w-full max-w-lg mx-auto"
        style={{ filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.08))" }}
      >
        {Object.entries(STATE_PATHS).map(([abbr, d]) => {
          const region = getStateRegion(abbr) as RegionName | null;
          if (!region) return null;

          const active = isRegionActive(region);
          const hovered = hoveredRegion === region;
          const regionColor = REGION_COLORS[region] || "var(--stroke)";

          return (
            <path
              key={abbr}
              d={d}
              fill={active ? regionColor : "var(--clay-mist)"}
              fillOpacity={active ? (hovered ? 0.85 : 0.6) : (hovered ? 0.4 : 0.25)}
              stroke={active ? regionColor : "var(--stroke)"}
              strokeWidth={active ? 1 : 0.5}
              strokeLinejoin="round"
              onClick={() => handleStateClick(abbr)}
              onMouseEnter={() => region && setHoveredRegion(region)}
              onMouseLeave={() => setHoveredRegion(null)}
              style={{
                cursor: "pointer",
                transition: "fill-opacity 200ms, stroke-width 200ms",
              }}
            />
          );
        })}

        {/* Region labels at approximate centers (Removed) */}
      </svg>

      {/* Tag chips below map */}
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
    </div>
  );
}

export type { RegionName };
