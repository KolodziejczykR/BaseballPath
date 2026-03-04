"use client";

const labelMap: Record<string, string> = {
  preferred_regions: "Preferred Regions",
  preferred_school_size: "School Size",
  min_academic_rating: "Min Academic Rating",
  min_athletics_rating: "Min Athletics Rating",
  party_scene_preference: "Party Scene",
  max_budget: "Max Budget",
};

type PreferenceVisibilityTogglesProps = {
  values: Record<string, boolean>;
  onChange: (next: Record<string, boolean>) => void;
};

export function PreferenceVisibilityToggles({ values, onChange }: PreferenceVisibilityTogglesProps) {
  const keys = Object.keys(values);

  return (
    <div className="space-y-2">
      {keys.length === 0 ? <p className="text-sm text-[var(--muted)]">No preferences available for visibility toggles.</p> : null}
      {keys.map((key) => {
        const checked = Boolean(values[key]);
        const label = labelMap[key] || key;
        return (
          <label
            key={key}
            className="flex items-center justify-between rounded-xl border border-[var(--stroke)] bg-white/75 px-3 py-2 text-sm"
          >
            <span className="font-medium text-[var(--navy)]">{label}</span>
            <button
              type="button"
              role="switch"
              aria-checked={checked}
              className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-[var(--primary)]" : "bg-[var(--muted)]/40"}`}
              onClick={() => onChange({ ...values, [key]: !checked })}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`}
              />
            </button>
          </label>
        );
      })}
    </div>
  );
}
