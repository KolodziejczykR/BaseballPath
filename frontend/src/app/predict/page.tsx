"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FadeOnScroll } from "@/components/ui/fade-on-scroll";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Step = 1 | 2 | 3;
type PositionCode = "LHP" | "RHP" | "1B" | "2B" | "SS" | "3B" | "OF";
type PositionTrack = "Pitcher" | "Infielder" | "Outfielder";

type Option = {
  label: string;
  value: string;
};

type FieldConfig = {
  id: string;
  label: string;
  type: "number" | "text" | "select";
  multiple?: boolean;
  placeholder?: string;
  step?: string;
  min?: number;
  max?: number;
  required: boolean;
  options?: Option[];
};

type EvaluationRunApiResponse = {
  run_id: string;
  entitlement?: {
    plan_tier?: string;
    monthly_eval_limit?: number | null;
    remaining_evals?: number | null;
    usage_before?: number;
    usage_after?: number;
  };
};

const validGrades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"];

const states = [
  "AL",
  "AK",
  "AZ",
  "AR",
  "CA",
  "CO",
  "CT",
  "DE",
  "FL",
  "GA",
  "HI",
  "ID",
  "IL",
  "IN",
  "IA",
  "KS",
  "KY",
  "LA",
  "ME",
  "MD",
  "MA",
  "MI",
  "MN",
  "MS",
  "MO",
  "MT",
  "NE",
  "NV",
  "NH",
  "NJ",
  "NM",
  "NY",
  "NC",
  "ND",
  "OH",
  "OK",
  "OR",
  "PA",
  "RI",
  "SC",
  "SD",
  "TN",
  "TX",
  "UT",
  "VT",
  "VA",
  "WA",
  "WV",
  "WI",
  "WY",
];

const battingHandOptions: Option[] = [
  { label: "Right", value: "R" },
  { label: "Left", value: "L" },
  { label: "Switch", value: "S" },
];

const throwingHandOptions: Option[] = [
  { label: "Right", value: "R" },
  { label: "Left", value: "L" },
];

const primaryPositionOptions: Option[] = [
  { label: "LHP", value: "LHP" },
  { label: "RHP", value: "RHP" },
  { label: "1B", value: "1B" },
  { label: "2B", value: "2B" },
  { label: "SS", value: "SS" },
  { label: "3B", value: "3B" },
  { label: "OF", value: "OF" },
];

const regionPreferenceOptions: Option[] = [
  { label: "Northeast", value: "Northeast" },
  { label: "Midwest", value: "Midwest" },
  { label: "South", value: "South" },
  { label: "West", value: "West" },
];

const schoolSizeOptions: Option[] = [
  { label: "Small (5000 students or less)", value: "Small" },
  { label: "Medium (5-15k students)", value: "Medium" },
  { label: "Large (15-30k students)", value: "Large" },
  { label: "Very Large (More than 30k students)", value: "Very Large" },
];

const partySceneOptions: Option[] = [
  { label: "Active (A+, A, A- grade)", value: "Active" },
  { label: "Moderate (B+, B, B- grade)", value: "Moderate" },
  { label: "Quiet (C+ and below grade)", value: "Quiet" },
];

const gradeOptions: Option[] = validGrades.map((grade) => ({ label: grade, value: grade }));

const preferenceFields: FieldConfig[] = [
  {
    id: "preferredRegion",
    label: "Preferred region",
    type: "select",
    multiple: true,
    required: false,
    options: regionPreferenceOptions,
  },
  {
    id: "preferredSchoolSize",
    label: "Preferred school size",
    type: "select",
    multiple: true,
    required: false,
    options: schoolSizeOptions,
  },
  {
    id: "minAcademicRating",
    label: "Minimum academic rating",
    type: "select",
    required: false,
    options: gradeOptions,
  },
  {
    id: "minAthleticsRating",
    label: "Minimum athletics rating",
    type: "select",
    required: false,
    options: gradeOptions,
  },
  {
    id: "partyScenePreference",
    label: "Party scene preference",
    type: "select",
    multiple: true,
    required: false,
    options: partySceneOptions,
  },
  {
    id: "maxBudget",
    label: "Max yearly budget (USD)",
    type: "number",
    required: false,
    step: "1",
    min: 0,
    placeholder: "Example: 35000",
  },
];

const pitcherFields: FieldConfig[] = [
  {
    id: "height",
    label: "Height (inches)",
    type: "number",
    required: true,
    min: 60,
    max: 84,
    step: "1",
    placeholder: "Example: 74",
  },
  {
    id: "weight",
    label: "Weight (lbs)",
    type: "number",
    required: true,
    min: 120,
    max: 320,
    step: "1",
    placeholder: "Example: 200",
  },
  {
    id: "fastballVeloRange",
    label: "Fastball velocity average (mph)",
    type: "number",
    required: false,
    min: 60,
    max: 105,
    step: "0.1",
    placeholder: "Example: 88.0",
  },
  {
    id: "fastballVeloMax",
    label: "Fastball velocity max (mph)",
    type: "number",
    required: true,
    min: 60,
    max: 105,
    step: "0.1",
    placeholder: "Example: 92.0",
  },
  {
    id: "fastballSpin",
    label: "Fastball spin rate (rpm)",
    type: "number",
    required: false,
    min: 1200,
    max: 3500,
    step: "1",
    placeholder: "Example: 2250",
  },
  {
    id: "changeupVelo",
    label: "Changeup velocity (mph)",
    type: "number",
    required: false,
    min: 60,
    max: 95,
    step: "0.1",
    placeholder: "Example: 80.0",
  },
  {
    id: "changeupSpin",
    label: "Changeup spin (rpm)",
    type: "number",
    required: false,
    min: 800,
    max: 3200,
    step: "1",
    placeholder: "Example: 1700",
  },
  {
    id: "curveballVelo",
    label: "Curveball velocity (mph)",
    type: "number",
    required: false,
    min: 55,
    max: 95,
    step: "0.1",
    placeholder: "Example: 74.0",
  },
  {
    id: "curveballSpin",
    label: "Curveball spin (rpm)",
    type: "number",
    required: false,
    min: 1200,
    max: 3500,
    step: "1",
    placeholder: "Example: 2200",
  },
  {
    id: "sliderVelo",
    label: "Slider velocity (mph)",
    type: "number",
    required: false,
    min: 60,
    max: 100,
    step: "0.1",
    placeholder: "Example: 78.0",
  },
  {
    id: "sliderSpin",
    label: "Slider spin (rpm)",
    type: "number",
    required: false,
    min: 1200,
    max: 3500,
    step: "1",
    placeholder: "Example: 2300",
  },
];

const infielderFields: FieldConfig[] = [
  {
    id: "height",
    label: "Height (inches)",
    type: "number",
    required: true,
    min: 60,
    max: 84,
    step: "1",
    placeholder: "Example: 72",
  },
  {
    id: "weight",
    label: "Weight (lbs)",
    type: "number",
    required: true,
    min: 120,
    max: 300,
    step: "1",
    placeholder: "Example: 180",
  },
  {
    id: "sixtyTime",
    label: "60-yard time (seconds)",
    type: "number",
    required: true,
    min: 5.0,
    max: 10.0,
    step: "0.01",
    placeholder: "Example: 6.95",
  },
  {
    id: "exitVeloMax",
    label: "Exit velocity max (mph)",
    type: "number",
    required: true,
    min: 50,
    max: 130,
    step: "0.1",
    placeholder: "Example: 92",
  },
  {
    id: "infVelo",
    label: "Infield velocity (mph)",
    type: "number",
    required: true,
    min: 50,
    max: 100,
    step: "0.1",
    placeholder: "Example: 83",
  },
  {
    id: "throwingHand",
    label: "Throwing hand",
    type: "select",
    required: true,
    options: throwingHandOptions,
  },
  {
    id: "hittingHandedness",
    label: "Hitting handedness",
    type: "select",
    required: true,
    options: battingHandOptions,
  },
];

const outfielderFields: FieldConfig[] = [
  {
    id: "height",
    label: "Height (inches)",
    type: "number",
    required: true,
    min: 60,
    max: 84,
    step: "1",
    placeholder: "Example: 72",
  },
  {
    id: "weight",
    label: "Weight (lbs)",
    type: "number",
    required: true,
    min: 120,
    max: 300,
    step: "1",
    placeholder: "Example: 180",
  },
  {
    id: "sixtyTime",
    label: "60-yard time (seconds)",
    type: "number",
    required: true,
    min: 5.0,
    max: 10.0,
    step: "0.01",
    placeholder: "Example: 6.85",
  },
  {
    id: "exitVeloMax",
    label: "Exit velocity max (mph)",
    type: "number",
    required: true,
    min: 50,
    max: 130,
    step: "0.1",
    placeholder: "Example: 94",
  },
  {
    id: "ofVelo",
    label: "Outfield velocity (mph)",
    type: "number",
    required: true,
    min: 50,
    max: 110,
    step: "0.1",
    placeholder: "Example: 88",
  },
  {
    id: "throwingHand",
    label: "Throwing hand",
    type: "select",
    required: true,
    options: throwingHandOptions,
  },
  {
    id: "hittingHandedness",
    label: "Hitting handedness",
    type: "select",
    required: true,
    options: battingHandOptions,
  },
];

const allFields = [
  ...pitcherFields,
  ...infielderFields,
  ...outfielderFields,
  ...preferenceFields,
];
const allFieldIds = Array.from(new Set(allFields.map((field) => field.id)));
const initialFieldState = Object.fromEntries(allFieldIds.map((id) => [id, ""])) as Record<string, string>;
const initialMultiSelectState: Record<string, string[]> = {
  preferredRegion: [],
  preferredSchoolSize: [],
  partyScenePreference: [],
};

const northeastStates = new Set(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"]);
const midwestStates = new Set(["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"]);
const southStates = new Set(["AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD", "MS", "NC", "OK", "SC", "TN", "TX", "VA", "WV"]);

function toNumber(value: string): number {
  return Number(value);
}

function numberIfPresent(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) return undefined;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function mapStateToPlayerRegion(stateAbbrev: string): string {
  const state = stateAbbrev.toUpperCase();
  if (northeastStates.has(state)) return "Northeast";
  if (midwestStates.has(state)) return "Midwest";
  if (southStates.has(state)) return "South";
  return "West";
}

function getPositionTrack(position: PositionCode | ""): PositionTrack {
  if (position === "LHP" || position === "RHP") return "Pitcher";
  if (position === "OF") return "Outfielder";
  return "Infielder";
}

function pickStatsFields(position: PositionCode | ""): FieldConfig[] {
  const track = getPositionTrack(position);
  if (track === "Pitcher") return pitcherFields;
  if (track === "Outfielder") return outfielderFields;
  return infielderFields;
}

function endpointForPosition(position: PositionCode): string {
  const track = getPositionTrack(position);
  if (track === "Pitcher") return "pitcher";
  if (track === "Outfielder") return "outfielder";
  return "infielder";
}

export default function PredictPage() {
  const router = useRouter();
  const { loading: authLoading, accessToken, user } = useRequireAuth("/predict");
  const [step, setStep] = useState<Step>(1);
  const [fields, setFields] = useState<Record<string, string>>(initialFieldState);
  const [multiSelectValues, setMultiSelectValues] = useState<Record<string, string[]>>(initialMultiSelectState);
  const [openMultiSelectId, setOpenMultiSelectId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState("");
  const multiDropdownRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [identity, setIdentity] = useState({
    name: "",
    state: "",
    primaryPosition: "" as PositionCode | "",
    graduatingClass: "",
  });

  const currentYear = new Date().getFullYear();
  const graduatingClasses = Array.from({ length: 9 }, (_, index) => String(currentYear + index));
  const positionTrack = getPositionTrack(identity.primaryPosition);
  const statsFields = useMemo(() => pickStatsFields(identity.primaryPosition), [identity.primaryPosition]);
  const pitcherRequiredFields = useMemo(
    () => pitcherFields.filter((field) => field.required),
    [],
  );
  const pitcherOptionalFields = useMemo(
    () => pitcherFields.filter((field) => !field.required),
    [],
  );

  const stepSummary = [
    { id: 1, title: "Identity", detail: "Name, state, position, and graduating class" },
    { id: 2, title: "Positional stats", detail: "Backend-aligned metrics for your selected position" },
    { id: 3, title: "Preferences", detail: "Optional fit signals for school matching and ranking" },
  ] as const;

  const identityComplete = Boolean(
    identity.name.trim() &&
      identity.state.trim() &&
      identity.primaryPosition &&
      identity.graduatingClass.trim(),
  );

  const statsComplete = statsFields
    .filter((field) => field.required)
    .every((field) => fields[field.id].trim() !== "");

  const preferencesComplete = preferenceFields
    .filter((field) => field.required)
    .every((field) =>
      field.multiple ? (multiSelectValues[field.id] || []).length > 0 : fields[field.id].trim() !== "",
    );

  const canMoveForward = step === 1 ? identityComplete : step === 2 ? statsComplete : preferencesComplete;

  function setFieldValue(fieldId: string, value: string) {
    setFields((prev) => ({ ...prev, [fieldId]: value }));
  }

  function setMultiSelectFieldValue(fieldId: string, values: string[]) {
    setMultiSelectValues((prev) => ({ ...prev, [fieldId]: values }));
  }

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!openMultiSelectId) return;
      const dropdownRoot = multiDropdownRefs.current[openMultiSelectId];
      if (!dropdownRoot) return;
      if (!dropdownRoot.contains(event.target as Node)) {
        setOpenMultiSelectId(null);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [openMultiSelectId]);

  function nextStep() {
    if (!canMoveForward || step === 3) return;
    setStep((prev) => (prev + 1) as Step);
  }

  function prevStep() {
    if (step === 1) return;
    setStep((prev) => (prev - 1) as Step);
  }

  function buildPredictionPayload(position: PositionCode, playerRegion: string): Record<string, unknown> {
    const track = getPositionTrack(position);

    if (track === "Pitcher") {
      const throwingHand = position === "LHP" ? "L" : "R";
      const payload: Record<string, unknown> = {
        height: toNumber(fields.height),
        weight: toNumber(fields.weight),
        primary_position: position,
        player_region: playerRegion,
        throwing_hand: throwingHand,
        fastball_velo_max: toNumber(fields.fastballVeloMax),
      };

      const optionalPitchMetrics: Array<[string, number | undefined]> = [
        ["fastball_velo_range", numberIfPresent(fields.fastballVeloRange)],
        ["fastball_spin", numberIfPresent(fields.fastballSpin)],
        ["changeup_velo", numberIfPresent(fields.changeupVelo)],
        ["changeup_spin", numberIfPresent(fields.changeupSpin)],
        ["curveball_velo", numberIfPresent(fields.curveballVelo)],
        ["curveball_spin", numberIfPresent(fields.curveballSpin)],
        ["slider_velo", numberIfPresent(fields.sliderVelo)],
        ["slider_spin", numberIfPresent(fields.sliderSpin)],
      ];

      for (const [key, value] of optionalPitchMetrics) {
        if (value !== undefined) payload[key] = value;
      }

      return payload;
    }

    if (track === "Outfielder") {
      return {
        height: toNumber(fields.height),
        weight: toNumber(fields.weight),
        sixty_time: toNumber(fields.sixtyTime),
        exit_velo_max: toNumber(fields.exitVeloMax),
        of_velo: toNumber(fields.ofVelo),
        primary_position: "OF",
        hitting_handedness: fields.hittingHandedness,
        throwing_hand: fields.throwingHand,
        player_region: playerRegion,
      };
    }

    return {
      height: toNumber(fields.height),
      weight: toNumber(fields.weight),
      sixty_time: toNumber(fields.sixtyTime),
      exit_velo_max: toNumber(fields.exitVeloMax),
      inf_velo: toNumber(fields.infVelo),
      primary_position: position,
      hitting_handedness: fields.hittingHandedness,
      throwing_hand: fields.throwingHand,
      player_region: playerRegion,
    };
  }

  function buildPlayerInfoForPreferences(position: PositionCode, playerRegion: string): Record<string, unknown> {
    const track = getPositionTrack(position);

    if (track === "Pitcher") {
      const throwingHand = position === "LHP" ? "L" : "R";
      const playerInfo: Record<string, unknown> = {
        height: toNumber(fields.height),
        weight: toNumber(fields.weight),
        primary_position: position,
        region: playerRegion,
        throwing_hand: throwingHand,
        fastball_velo_max: toNumber(fields.fastballVeloMax),
      };

      const optionalPitchMetrics: Array<[string, number | undefined]> = [
        ["fastball_velo_range", numberIfPresent(fields.fastballVeloRange)],
        ["fastball_spin", numberIfPresent(fields.fastballSpin)],
        ["changeup_velo", numberIfPresent(fields.changeupVelo)],
        ["changeup_spin", numberIfPresent(fields.changeupSpin)],
        ["curveball_velo", numberIfPresent(fields.curveballVelo)],
        ["curveball_spin", numberIfPresent(fields.curveballSpin)],
        ["slider_velo", numberIfPresent(fields.sliderVelo)],
        ["slider_spin", numberIfPresent(fields.sliderSpin)],
      ];

      for (const [key, value] of optionalPitchMetrics) {
        if (value !== undefined) playerInfo[key] = value;
      }

      return playerInfo;
    }

    if (track === "Outfielder") {
      return {
        height: toNumber(fields.height),
        weight: toNumber(fields.weight),
        primary_position: "OF",
        exit_velo_max: toNumber(fields.exitVeloMax),
        sixty_time: toNumber(fields.sixtyTime),
        of_velo: toNumber(fields.ofVelo),
        throwing_hand: fields.throwingHand,
        hitting_handedness: fields.hittingHandedness,
        region: playerRegion,
      };
    }

    return {
      height: toNumber(fields.height),
      weight: toNumber(fields.weight),
      primary_position: position,
      exit_velo_max: toNumber(fields.exitVeloMax),
      sixty_time: toNumber(fields.sixtyTime),
      inf_velo: toNumber(fields.infVelo),
      throwing_hand: fields.throwingHand,
      hitting_handedness: fields.hittingHandedness,
      region: playerRegion,
    };
  }

  async function runEvaluation() {
    if (!identity.primaryPosition || !accessToken) return;

    setSubmitting(true);
    setSubmissionError("");

    try {
      const playerRegion = mapStateToPlayerRegion(identity.state);
      const predictionPayload = buildPredictionPayload(identity.primaryPosition, playerRegion);
      const positionEndpoint = endpointForPosition(identity.primaryPosition);

      const userPreferencesPayload: Record<string, unknown> = {
        user_state: identity.state,
        hs_graduation_year: Number(identity.graduatingClass),
      };
      if (multiSelectValues.preferredRegion.length > 0) {
        userPreferencesPayload.preferred_regions = multiSelectValues.preferredRegion;
      }
      if (multiSelectValues.preferredSchoolSize.length > 0) {
        userPreferencesPayload.preferred_school_size = multiSelectValues.preferredSchoolSize;
      }
      if (multiSelectValues.partyScenePreference.length > 0) {
        userPreferencesPayload.party_scene_preference = multiSelectValues.partyScenePreference;
      }
      if (fields.minAcademicRating.trim()) {
        userPreferencesPayload.min_academic_rating = fields.minAcademicRating.trim();
      }
      if (fields.minAthleticsRating.trim()) {
        userPreferencesPayload.min_athletics_rating = fields.minAthleticsRating.trim();
      }
      const maxBudget = numberIfPresent(fields.maxBudget);
      if (maxBudget !== undefined) {
        userPreferencesPayload.max_budget = maxBudget;
      }

      const preferencesPayload: Record<string, unknown> = {
        user_preferences: userPreferencesPayload,
        player_info: buildPlayerInfoForPreferences(identity.primaryPosition, playerRegion),
        limit: 25,
      };
      const preferencesInput: Record<string, unknown> = {};
      if (multiSelectValues.preferredRegion.length > 0) {
        preferencesInput.preferred_regions = multiSelectValues.preferredRegion;
      }
      if (multiSelectValues.preferredSchoolSize.length > 0) {
        preferencesInput.preferred_school_size = multiSelectValues.preferredSchoolSize;
      }
      if (multiSelectValues.partyScenePreference.length > 0) {
        preferencesInput.party_scene_preference = multiSelectValues.partyScenePreference;
      }
      if (fields.minAcademicRating.trim()) {
        preferencesInput.min_academic_rating = fields.minAcademicRating.trim();
      }
      if (fields.minAthleticsRating.trim()) {
        preferencesInput.min_athletics_rating = fields.minAthleticsRating.trim();
      }
      if (maxBudget !== undefined) {
        preferencesInput.max_budget = maxBudget;
      }

      const evaluationResponse = await fetch(`${API_BASE_URL}/evaluations/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          position_endpoint: positionEndpoint,
          identity_input: {
            name: identity.name,
            state: identity.state,
            primary_position: identity.primaryPosition,
            graduating_class: identity.graduatingClass,
          },
          stats_input: statsFields.reduce<Record<string, string>>((acc, field) => {
            acc[field.id] = fields[field.id];
            return acc;
          }, {}),
          preferences_input: preferencesInput,
          prediction_payload: predictionPayload,
          preferences_payload: preferencesPayload,
          use_llm_reasoning: false,
        }),
      });

      const evaluationData = (await evaluationResponse.json()) as
        | EvaluationRunApiResponse
        | { detail?: string | { error?: string; plan_tier?: string; monthly_limit?: number } };
      if (!evaluationResponse.ok) {
        const rawDetail =
          typeof evaluationData === "object" && evaluationData && "detail" in evaluationData
            ? evaluationData.detail
            : "Evaluation request failed.";

        if (typeof rawDetail === "string") {
          throw new Error(rawDetail);
        }

        if (rawDetail && typeof rawDetail === "object" && rawDetail.error === "evaluation_quota_exceeded") {
          const tier = rawDetail.plan_tier ?? "current";
          const limit = rawDetail.monthly_limit ?? "?";
          throw new Error(`Monthly evaluation limit reached for ${tier} plan (${limit}/month).`);
        }

        throw new Error("Evaluation request failed.");
      }

      const typedEvaluation = evaluationData as EvaluationRunApiResponse;
      router.push(`/evaluations/${typedEvaluation.run_id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to run evaluation.";
      setSubmissionError(message);
    } finally {
      setSubmitting(false);
    }
  }

  function renderField(field: FieldConfig) {
    if (field.type === "select") {
      if (field.multiple) {
        const selectedValues = multiSelectValues[field.id] || [];
        const selectedLabels = (field.options || [])
          .filter((option) => selectedValues.includes(option.value))
          .map((option) => option.label);
        const displayValue =
          selectedLabels.length === 0
            ? "Select option"
            : selectedLabels.length === 1
            ? selectedLabels[0]
            : "Multiple Selected";

        return (
          <div
            key={field.id}
            className="relative grid gap-2 text-sm font-medium"
            ref={(node) => {
              multiDropdownRefs.current[field.id] = node;
            }}
          >
            <label>{field.label}</label>
            <button
              type="button"
              className="form-control relative flex items-center justify-between pr-11 text-left"
              onClick={() =>
                setOpenMultiSelectId((current) => (current === field.id ? null : field.id))
              }
            >
              <span>{displayValue}</span>
              <span className="pointer-events-none absolute right-[0.95rem] top-1/2 -translate-y-1/2 text-[var(--foreground)]">
                <svg
                  viewBox="0 0 20 20"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path
                    d="M5 7.5L10 12.5L15 7.5"
                    stroke="currentColor"
                    strokeWidth="2.1"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
            {openMultiSelectId === field.id && (
              <div className="absolute left-0 right-0 top-[calc(100%+0.35rem)] z-30 max-h-64 overflow-auto rounded-2xl border border-[var(--stroke)] bg-white shadow-soft">
                {(field.options || []).map((option) => {
                  const selected = selectedValues.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-[var(--sand)]/55"
                      onClick={() => {
                        const nextValues = selected
                          ? selectedValues.filter((value) => value !== option.value)
                          : [...selectedValues, option.value];
                        setMultiSelectFieldValue(field.id, nextValues);
                      }}
                    >
                      <span>{option.label}</span>
                      <span
                        className={`inline-flex h-5 w-5 items-center justify-center rounded-full border text-xs ${
                          selected
                            ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                            : "border-[var(--stroke)] bg-white text-transparent"
                        }`}
                      >
                        ✓
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      }

      return (
        <label key={field.id} className="grid gap-2 text-sm font-medium">
          {field.label}
          <select
            value={fields[field.id]}
            onChange={(event) => setFieldValue(field.id, event.target.value)}
            className="form-control"
          >
            <option value="">Select option</option>
            {(field.options || []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      );
    }

    return (
      <label key={field.id} className="grid gap-2 text-sm font-medium">
        {field.label}
        <input
          type={field.type}
          value={fields[field.id]}
          min={field.min}
          max={field.max}
          step={field.step}
          onChange={(event) => setFieldValue(field.id, event.target.value)}
          placeholder={field.placeholder}
          className="form-control"
        />
      </label>
    );
  }

  if (authLoading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Checking your account session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}
      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
        <div className="mb-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.34em] text-[var(--muted)]">Prediction Pipeline</p>
            <h1 className="display-font mt-4 text-4xl leading-tight md:text-6xl">
              Backend-aligned evaluation flow for real model input.
            </h1>
            <p className="mt-3 max-w-2xl text-[var(--muted)]">
              Sequence is fixed: identity, positional metrics, then grouped preferences mapped directly to the
              prediction and filtering APIs.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="inline-flex w-fit items-center rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)]"
          >
            Back to Dashboard
          </Link>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.12fr_0.88fr]">
          <FadeOnScroll>
            <section className="glass rounded-[30px] p-6 shadow-soft md:p-8">
              <div className="mb-8 rounded-2xl border border-[var(--stroke)] bg-white/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs uppercase tracking-[0.28em] text-[var(--muted)]">Step {step} of 3</p>
                  <p className="text-sm font-semibold text-[var(--navy)]">{stepSummary[step - 1].title}</p>
                </div>
                <div className="mt-3 h-2 rounded-full bg-[var(--sand)]">
                  <div
                    className="h-2 rounded-full bg-[var(--primary)] transition-all duration-500"
                    style={{ width: `${(step / 3) * 100}%` }}
                  />
                </div>
              </div>

              {step === 1 && (
                <div className="space-y-5">
                  <h2 className="text-2xl font-semibold">Player identity</h2>
                  <p className="text-sm text-[var(--muted)]">
                    Required first stage: name, state, primary position, and graduating class.
                  </p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="grid gap-2 text-sm font-medium">
                      Name
                      <input
                        value={identity.name}
                        onChange={(event) => setIdentity((prev) => ({ ...prev, name: event.target.value }))}
                        type="text"
                        placeholder="First and last name"
                        className="form-control"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      State
                      <select
                        value={identity.state}
                        onChange={(event) => setIdentity((prev) => ({ ...prev, state: event.target.value }))}
                        className="form-control"
                      >
                        <option value="">Select state</option>
                        {states.map((state) => (
                          <option key={state} value={state}>
                            {state}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      Primary position
                      <select
                        value={identity.primaryPosition}
                        onChange={(event) =>
                          setIdentity((prev) => ({
                            ...prev,
                            primaryPosition: event.target.value as PositionCode,
                          }))
                        }
                        className="form-control"
                      >
                        <option value="">Select position</option>
                        {primaryPositionOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      Graduating class
                      <select
                        value={identity.graduatingClass}
                        onChange={(event) =>
                          setIdentity((prev) => ({ ...prev, graduatingClass: event.target.value }))
                        }
                        className="form-control"
                      >
                        <option value="">Select year</option>
                        {graduatingClasses.map((year) => (
                          <option key={year} value={year}>
                            {year}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-5">
                  <h2 className="text-2xl font-semibold">Positional stats</h2>
                  <p className="text-sm text-[var(--muted)]">
                    Position selected:{" "}
                    <span className="font-semibold text-[var(--navy)]">{identity.primaryPosition || "Not set"}</span>.
                    Inputs below follow backend router schemas.
                  </p>
                  {positionTrack === "Pitcher" ? (
                    <div className="space-y-6">
                      <div>
                        <p className="mb-3 text-sm font-semibold text-[var(--navy)]">Required</p>
                        <div className="grid gap-4 md:grid-cols-2">{pitcherRequiredFields.map(renderField)}</div>
                      </div>
                      <div className="rounded-2xl border border-[var(--stroke)] bg-white/60 p-4">
                        <p className="text-sm font-semibold text-[var(--navy)]">Optional pitch metrics</p>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          Fill in only the pitches and stats you have access to. If you do not have this information,
                          leave it blank.
                        </p>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">{pitcherOptionalFields.map(renderField)}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-2">{statsFields.map(renderField)}</div>
                  )}
                </div>
              )}

              {step === 3 && (
                <div className="space-y-5">
                  <h2 className="text-2xl font-semibold">Preferences</h2>
                  <p className="text-sm text-[var(--muted)]">
                    All preferences are optional. Add only what matters to you now and skip the rest. These are used
                    to explain and rank school fits in your evaluation report.
                  </p>
                  <div className="grid gap-4 md:grid-cols-2">{preferenceFields.map(renderField)}</div>
                </div>
              )}

              <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={prevStep}
                  disabled={step === 1 || submitting}
                  className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Back
                </button>

                {step < 3 ? (
                  <button
                    type="button"
                    onClick={nextStep}
                    disabled={!canMoveForward || submitting}
                    className="rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold text-white shadow-strong disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Continue
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={runEvaluation}
                    disabled={!canMoveForward || submitting || !accessToken}
                    className="rounded-full bg-[var(--accent)] px-6 py-2.5 text-sm font-semibold text-white shadow-strong disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? "Running..." : "Run Evaluation"}
                  </button>
                )}
              </div>
            </section>
          </FadeOnScroll>

          <div className="space-y-6">
            <FadeOnScroll delayMs={70}>
              <section className="rounded-[30px] bg-[var(--navy)] p-6 text-white shadow-strong">
                <p className="text-xs uppercase tracking-[0.3em] text-white/65">Pipeline map</p>
                <div className="mt-4 space-y-4">
                  {stepSummary.map((item) => (
                    <div
                      key={item.id}
                      className={`rounded-2xl border p-4 transition duration-300 ${
                        step === item.id ? "border-white/40 bg-white/16" : "border-white/15 bg-white/6"
                      }`}
                    >
                      <p className="text-xs uppercase tracking-[0.28em] text-white/65">Step {item.id}</p>
                      <p className="mt-1 font-semibold">{item.title}</p>
                      <p className="mt-1 text-sm text-white/75">{item.detail}</p>
                    </div>
                  ))}
                </div>
              </section>
            </FadeOnScroll>

            <FadeOnScroll delayMs={120}>
              <section className="glass rounded-[30px] p-6 shadow-soft">
                <p className="text-xs uppercase tracking-[0.28em] text-[var(--muted)]">What happens next</p>
                <h3 className="mt-2 text-xl font-semibold">Full evaluation opens on a dedicated page</h3>

                {submissionError && (
                  <div className="mt-4 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">
                    {submissionError}
                  </div>
                )}

                {!submissionError && (
                  <div className="mt-4 space-y-4 text-sm text-[var(--muted)]">
                    <p>After you run an evaluation, you will be routed to a full report page for that run ID.</p>
                    <p>The report includes predicted tier, school matches, playing-time analysis, and preference-hit explanations.</p>
                    <div className="flex flex-wrap gap-3">
                      <Link
                        href="/evaluations"
                        className="inline-flex rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-xs font-semibold text-[var(--navy)]"
                      >
                        View Past Evaluations
                      </Link>
                      <Link
                        href="/dashboard"
                        className="inline-flex rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-xs font-semibold text-[var(--navy)]"
                      >
                        Back to Dashboard
                      </Link>
                    </div>
                  </div>
                )}
              </section>
            </FadeOnScroll>
          </div>
        </div>
        </div>
      </main>
    </div>
  );
}
