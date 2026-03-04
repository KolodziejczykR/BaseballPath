# Technical Design Document: Interactive Player Card & Goals Tracking

> This document is a comprehensive implementation guide (mega-prompt) for an LLM to implement both features end-to-end. It contains exact file paths, code patterns, SQL, API contracts, and component structures — everything needed to build both features from scratch within the existing BaseballPATH codebase.

---

## Table of Contents

1. [Codebase Context](#1-codebase-context)
2. [Phase 1: Database Migrations](#2-phase-1-database-migrations)
3. [Phase 2: Backend — Player Card](#3-phase-2-backend--player-card)
4. [Phase 3: Backend — Goals & Sensitivity](#4-phase-3-backend--goals--sensitivity)
5. [Phase 4: Backend — Registration & Wiring](#5-phase-4-backend--registration--wiring)
6. [Phase 5: Frontend — Player Card Components](#6-phase-5-frontend--player-card-components)
7. [Phase 6: Frontend — Player Card Pages](#7-phase-6-frontend--player-card-pages)
8. [Phase 7: Frontend — Goals Components](#8-phase-7-frontend--goals-components)
9. [Phase 8: Frontend — Goals Pages](#9-phase-8-frontend--goals-pages)
10. [Phase 9: Nav & Dashboard Integration](#10-phase-9-nav--dashboard-integration)
11. [Phase 10: Polish & Testing](#11-phase-10-polish--testing)
12. [Appendix: Existing Code Reference](#appendix-existing-code-reference)

---

## 1. Codebase Context

### Project Root
```
/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/
```

### Tech Stack
- **Backend**: FastAPI (Python 3.x), Pydantic v2, Supabase PostgreSQL, Supabase Storage
- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4
- **ML**: XGBoost/LightGBM/CatBoost/SVM ensemble, two-stage pipeline (D1 → P4)
- **Auth**: Supabase Auth, JWT Bearer tokens
- **Payments**: Stripe (existing)

### Key Architectural Patterns

**Backend Router Pattern** (from `backend/api/routers/evaluations.py`):
```python
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user

router = APIRouter()

@router.post("/endpoint")
async def endpoint_name(
    payload: SomeModel,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    # ... business logic using supabase.table("xxx").select/insert/update ...
```

**Frontend Page Pattern** (from `frontend/src/app/dashboard/page.tsx`):
```typescript
"use client";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PageName() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/page-path");
  // ... state, useEffect for API calls with Bearer token ...
  // ... loading state, error handling ...
  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}
      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          {/* content */}
        </div>
      </main>
    </div>
  );
}
```

**API Call Pattern** (frontend):
```typescript
const headers = {
  "Content-Type": "application/json",
  Authorization: `Bearer ${accessToken}`,
};
const response = await fetch(`${API_BASE_URL}/endpoint`, { headers });
const data = await response.json();
if (!response.ok) throw new Error(data.detail || "Request failed");
```

**CSS Design System** (from `frontend/src/app/globals.css`):
```css
:root {
  --background: #f3eee2;
  --foreground: #0f1823;
  --primary: #0f8d63;     /* green */
  --primary-dark: #0a6748;
  --accent: #ef6f2e;      /* orange */
  --navy: #18365a;
  --sand: #ece1c5;
  --muted: #516071;
  --card: #fff9ec;
  --stroke: #dccfb0;
  --surface: rgba(255, 250, 237, 0.78);
}
```

**Shared CSS Classes**: `.glass`, `.shadow-soft`, `.shadow-strong`, `.form-control`, `.display-font`

### Existing Files That Will Be Modified

| File | What Changes |
|------|-------------|
| `backend/api/main.py` | Register 3 new routers |
| `frontend/src/components/ui/authenticated-topbar.tsx` | Add nav items |
| `frontend/src/app/dashboard/page.tsx` | Add card preview + goals snapshot sections |
| `frontend/src/app/evaluations/[runId]/page.tsx` | Add "Create Card" + "Set Goals" buttons |

### Existing Files Referenced (Read-Only)

| File | What It Provides |
|------|-----------------|
| `backend/api/deps/auth.py` | `AuthenticatedUser`, `get_current_user` |
| `backend/api/clients/supabase.py` | `require_supabase_admin_client()` |
| `backend/utils/player_types.py` | `PlayerInfielder`, `PlayerOutfielder`, `PlayerCatcher`, `PlayerPitcher` |
| `backend/utils/prediction_types.py` | `MLPipelineResults`, `D1PredictionResult`, `P4PredictionResult` |
| `backend/ml/pipeline/infielder_pipeline.py` | `InfielderPredictionPipeline.predict()` |
| `backend/ml/pipeline/outfielder_pipeline.py` | `OutfielderPredictionPipeline.predict()` |
| `backend/ml/pipeline/catcher_pipeline.py` | `CatcherPredictionPipeline.predict()` |
| `backend/ml/pipeline/pitcher_pipeline.py` | `PitcherPredictionPipeline.predict()` |
| `backend/ml/router/infielder_router.py` | `pipeline` singleton instance, `InfielderInput` |
| `backend/ml/router/outfielder_router.py` | `pipeline` singleton instance, `OutfielderInput` |
| `backend/ml/router/pitcher_router.py` | `pipeline` singleton instance, `PitcherInput` |
| `backend/ml/router/catcher_router.py` | `pipeline` singleton instance, `CatcherInput` |
| `frontend/src/hooks/useRequireAuth.ts` | Auth guard hook |
| `frontend/src/lib/supabase-browser.ts` | `getSupabaseBrowserClient()` |

---

## 2. Phase 1: Database Migrations

### File: `backend/database/migrations/player_cards.sql`

```sql
-- Player Cards & Share Links schema
-- Run in Supabase SQL editor or via migration tooling.

-- ============================================================
-- Alter profiles table for new fields
-- ============================================================
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS high_school_name TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS video_links JSONB DEFAULT '[]'::jsonb;

-- ============================================================
-- player_cards: one card per user, auto-updates with new evals
-- ============================================================
CREATE TABLE IF NOT EXISTS public.player_cards (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES public.profiles(id) ON DELETE CASCADE,
  latest_evaluation_run_id UUID REFERENCES public.prediction_runs(id) ON DELETE SET NULL,
  display_name TEXT NOT NULL,
  high_school_name TEXT,
  class_year INT,
  primary_position TEXT,
  state TEXT,
  stats_snapshot JSONB NOT NULL,
  prediction_level TEXT,
  d1_probability FLOAT,
  p4_probability FLOAT,
  photo_storage_path TEXT,
  video_links JSONB DEFAULT '[]'::jsonb,
  bp_profile_link TEXT,
  visible_preferences JSONB DEFAULT '{}'::jsonb,
  preferences_snapshot JSONB DEFAULT '{}'::jsonb,
  card_theme TEXT DEFAULT 'classic',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_cards_user_id ON public.player_cards(user_id);

-- ============================================================
-- card_share_links: trackable share URLs
-- ============================================================
CREATE TABLE IF NOT EXISTS public.card_share_links (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  card_id UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  slug TEXT NOT NULL UNIQUE,
  platform TEXT,
  label TEXT,
  is_active BOOLEAN DEFAULT true,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_card_share_links_slug ON public.card_share_links(slug);
CREATE INDEX IF NOT EXISTS idx_card_share_links_card_id ON public.card_share_links(card_id);

-- ============================================================
-- card_link_clicks: analytics for share link engagement
-- ============================================================
CREATE TABLE IF NOT EXISTS public.card_link_clicks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  share_link_id UUID NOT NULL REFERENCES public.card_share_links(id) ON DELETE CASCADE,
  card_id UUID NOT NULL,
  user_id UUID NOT NULL,
  clicked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  referrer TEXT,
  user_agent TEXT,
  ip_hash TEXT,
  platform_detected TEXT,
  is_unique BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_card_link_clicks_share_link ON public.card_link_clicks(share_link_id, clicked_at DESC);
CREATE INDEX IF NOT EXISTS idx_card_link_clicks_card_id ON public.card_link_clicks(card_id);

-- ============================================================
-- Triggers: auto-update updated_at
-- ============================================================
DROP TRIGGER IF EXISTS player_cards_set_updated_at ON public.player_cards;
CREATE TRIGGER player_cards_set_updated_at
BEFORE UPDATE ON public.player_cards
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- RLS Policies
-- ============================================================
ALTER TABLE public.player_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.card_share_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.card_link_clicks ENABLE ROW LEVEL SECURITY;

-- player_cards: users manage own
DROP POLICY IF EXISTS "player_cards_select_own" ON public.player_cards;
CREATE POLICY "player_cards_select_own" ON public.player_cards
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_cards_insert_own" ON public.player_cards;
CREATE POLICY "player_cards_insert_own" ON public.player_cards
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_cards_update_own" ON public.player_cards;
CREATE POLICY "player_cards_update_own" ON public.player_cards
  FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_cards_delete_own" ON public.player_cards;
CREATE POLICY "player_cards_delete_own" ON public.player_cards
  FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- card_share_links: users manage own
DROP POLICY IF EXISTS "card_share_links_select_own" ON public.card_share_links;
CREATE POLICY "card_share_links_select_own" ON public.card_share_links
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "card_share_links_insert_own" ON public.card_share_links;
CREATE POLICY "card_share_links_insert_own" ON public.card_share_links
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "card_share_links_delete_own" ON public.card_share_links;
CREATE POLICY "card_share_links_delete_own" ON public.card_share_links
  FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- card_link_clicks: owner can read, service role inserts
DROP POLICY IF EXISTS "card_link_clicks_select_own" ON public.card_link_clicks;
CREATE POLICY "card_link_clicks_select_own" ON public.card_link_clicks
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- Note: INSERT for card_link_clicks is done via service role (backend),
-- so no authenticated INSERT policy needed. The service role bypasses RLS.
```

### File: `backend/database/migrations/goals_tracking.sql`

```sql
-- Goals Tracking schema
-- Run in Supabase SQL editor or via migration tooling.

-- ============================================================
-- player_goals: user goal sets with cached sensitivity
-- ============================================================
CREATE TABLE IF NOT EXISTS public.player_goals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  position_track TEXT NOT NULL CHECK (position_track IN ('pitcher', 'infielder', 'outfielder', 'catcher')),
  target_level TEXT NOT NULL DEFAULT 'D1' CHECK (target_level IN ('D1', 'Power 4 D1')),
  current_stats JSONB NOT NULL,
  target_stats JSONB,
  sensitivity_results JSONB,
  sensitivity_computed_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_goals_user_id ON public.player_goals(user_id);

-- ============================================================
-- stat_progress_entries: logged stat updates over time
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stat_progress_entries (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  goal_id UUID NOT NULL REFERENCES public.player_goals(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  stat_name TEXT NOT NULL,
  stat_value FLOAT NOT NULL,
  source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'evaluation', 'verified')),
  evaluation_run_id UUID REFERENCES public.prediction_runs(id) ON DELETE SET NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stat_progress_goal ON public.stat_progress_entries(goal_id, recorded_at DESC);

-- ============================================================
-- position_stat_ranges: reference data (not user-specific)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.position_stat_ranges (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  position_track TEXT NOT NULL,
  level TEXT NOT NULL,
  stat_name TEXT NOT NULL,
  p10 FLOAT,
  p25 FLOAT,
  median FLOAT,
  p75 FLOAT,
  p90 FLOAT,
  mean FLOAT,
  std_dev FLOAT,
  sample_count INT,
  data_version TEXT,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (position_track, level, stat_name, data_version)
);

-- ============================================================
-- Triggers
-- ============================================================
DROP TRIGGER IF EXISTS player_goals_set_updated_at ON public.player_goals;
CREATE TRIGGER player_goals_set_updated_at
BEFORE UPDATE ON public.player_goals
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- RLS Policies
-- ============================================================
ALTER TABLE public.player_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stat_progress_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.position_stat_ranges ENABLE ROW LEVEL SECURITY;

-- player_goals: users manage own
DROP POLICY IF EXISTS "player_goals_select_own" ON public.player_goals;
CREATE POLICY "player_goals_select_own" ON public.player_goals
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_goals_insert_own" ON public.player_goals;
CREATE POLICY "player_goals_insert_own" ON public.player_goals
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_goals_update_own" ON public.player_goals;
CREATE POLICY "player_goals_update_own" ON public.player_goals
  FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "player_goals_delete_own" ON public.player_goals;
CREATE POLICY "player_goals_delete_own" ON public.player_goals
  FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- stat_progress_entries: users manage own
DROP POLICY IF EXISTS "stat_progress_select_own" ON public.stat_progress_entries;
CREATE POLICY "stat_progress_select_own" ON public.stat_progress_entries
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "stat_progress_insert_own" ON public.stat_progress_entries;
CREATE POLICY "stat_progress_insert_own" ON public.stat_progress_entries
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- position_stat_ranges: all authenticated users can read (reference data)
DROP POLICY IF EXISTS "stat_ranges_select_all" ON public.position_stat_ranges;
CREATE POLICY "stat_ranges_select_all" ON public.position_stat_ranges
  FOR SELECT TO authenticated USING (true);
```

---

## 3. Phase 2: Backend — Player Card

### File: `backend/utils/perturbable_stats.py`

```python
"""
Configuration for perturbable stats used in sensitivity analysis.
Maps position tracks to their modifiable stats with display info, direction, and step sizes.
"""

PERTURBABLE_STATS = {
    "infielder": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "inf_velo": {"display": "Infield Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "outfielder": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "of_velo": {"display": "Outfield Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "catcher": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "c_velo": {"display": "Catcher Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "pop_time": {"display": "Pop Time", "unit": "sec", "dir": -1, "steps": [0.02, 0.05, 0.1, 0.15]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "pitcher": {
        "fastball_velo_max": {"display": "Fastball Max", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "fastball_velo_range": {"display": "Fastball Avg", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "fastball_spin": {"display": "Fastball Spin", "unit": "rpm", "dir": +1, "steps": [50, 100, 150, 200]},
        "changeup_velo": {"display": "Changeup Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
        "curveball_velo": {"display": "Curveball Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
        "slider_velo": {"display": "Slider Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
    },
}


def get_perturbable_stats(position_track: str) -> dict:
    """Get perturbable stats config for a position track."""
    if position_track not in PERTURBABLE_STATS:
        raise ValueError(f"Unknown position_track: {position_track}. Must be one of: {list(PERTURBABLE_STATS.keys())}")
    return PERTURBABLE_STATS[position_track]
```

### File: `backend/api/routers/player_card.py`

This file implements the authenticated card management endpoints.

**Key implementation details:**
- Follow the exact same patterns as `evaluations.py`: `router = APIRouter()`, `Depends(get_current_user)`, `require_supabase_admin_client()`
- Pydantic models for request/response validation
- Card is ONE per user: `POST /cards` does an upsert on `user_id`
- Photo upload uses `UploadFile` from FastAPI for multipart handling
- Share link slugs generated with `nanoid` (Python package)
- EXIF stripping with `Pillow` (`PIL.Image`)
- IP hashing for click tracking with `hashlib.sha256`

**Endpoint implementations:**

```
POST   /cards          → create_or_update_card()
GET    /cards/me       → get_my_card()
PATCH  /cards/me       → update_my_card()
DELETE /cards/me       → delete_my_card()  (soft delete)
POST   /cards/me/photo → upload_card_photo()
POST   /cards/me/share → create_share_link()
GET    /cards/me/analytics → get_card_analytics()
POST   /cards/me/refresh   → refresh_card_from_eval()
```

**Pydantic models to define:**
```python
class CardCreateRequest(BaseModel):
    evaluation_run_id: str
    display_name: str
    high_school_name: Optional[str] = None
    class_year: Optional[int] = None
    video_links: Optional[List[Dict[str, str]]] = None
    visible_preferences: Optional[Dict[str, bool]] = None

class CardUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    high_school_name: Optional[str] = None
    class_year: Optional[int] = None
    video_links: Optional[List[Dict[str, str]]] = None
    visible_preferences: Optional[Dict[str, bool]] = None
    card_theme: Optional[str] = None

class ShareLinkRequest(BaseModel):
    platform: Optional[str] = None  # "instagram", "twitter", "general"
    label: Optional[str] = None
```

**Card creation flow (POST /cards):**
1. Validate `evaluation_run_id` belongs to `current_user.user_id` via `prediction_runs` table
2. Extract stats from `prediction_response` in that run
3. Extract prediction level, d1_probability, p4_probability
4. Extract position from `position_track`
5. Build `stats_snapshot` JSONB from the evaluation's `stats_input`
6. Upsert into `player_cards` with `ON CONFLICT (user_id) DO UPDATE`
7. Return the card data

**Refresh flow (POST /cards/me/refresh):**
1. Find user's latest `prediction_runs` row (ORDER BY `created_at` DESC LIMIT 1)
2. Extract updated stats + prediction
3. Update card's `stats_snapshot`, `prediction_level`, `d1_probability`, `p4_probability`, `latest_evaluation_run_id`

### File: `backend/api/routers/public_card.py`

This file implements unauthenticated public card access endpoints.

**Endpoint implementations:**
```
GET /p/{slug}         → redirect_share_link()  (record click, redirect)
GET /p/{slug}/data    → get_public_card_data()  (return card JSON, filtered)
GET /p/{slug}/og-image → get_og_image()         (return image)
```

**Critical security**: The `get_public_card_data()` endpoint MUST:
1. Look up card via `card_share_links.slug`
2. Verify link `is_active` and not expired
3. Fetch the associated `player_cards` row
4. Filter out any preferences where `visible_preferences[key]` is `false`
5. Never return the full `preferences_snapshot` — only visible fields

**Click recording** (`redirect_share_link`):
1. Hash the IP: `hashlib.sha256((ip + SALT).encode()).hexdigest()`
2. Check uniqueness: query `card_link_clicks` for same `ip_hash + share_link_id` in last 24h
3. Insert click row with `is_unique` flag
4. Detect platform from `Referer` header: `t.co` → twitter, `l.instagram.com` → instagram, etc.
5. Return a redirect to the public card page URL

---

## 4. Phase 3: Backend — Goals & Sensitivity

### File: `backend/api/services/sensitivity_service.py`

This is the core sensitivity analysis engine.

**Key design:**
- Imports pipeline singletons from existing router modules (they're already loaded in memory)
- Creates `PlayerType` objects with perturbed stats
- Calls `pipeline.predict()` for each perturbation
- Ranks by marginal D1 probability delta per unit change

**Implementation skeleton:**

```python
"""
Sensitivity analysis service.
Re-runs the ML pipeline with perturbed inputs to rank stats by impact on D1/P4 probability.
"""

from typing import Any, Dict, List, Optional
import logging

from backend.utils.perturbable_stats import get_perturbable_stats
from backend.utils.player_types import (
    PlayerInfielder, PlayerOutfielder, PlayerCatcher, PlayerPitcher
)

# Import pipeline singletons (already loaded at module level in routers)
from backend.ml.router.infielder_router import pipeline as infielder_pipeline
from backend.ml.router.outfielder_router import pipeline as outfielder_pipeline
from backend.ml.router.catcher_router import pipeline as catcher_pipeline
from backend.ml.router.pitcher_router import pipeline as pitcher_pipeline

logger = logging.getLogger(__name__)

PIPELINE_MAP = {
    "infielder": infielder_pipeline,
    "outfielder": outfielder_pipeline,
    "catcher": catcher_pipeline,
    "pitcher": pitcher_pipeline,
}

PLAYER_CLASS_MAP = {
    "infielder": PlayerInfielder,
    "outfielder": PlayerOutfielder,
    "catcher": PlayerCatcher,
    "pitcher": PlayerPitcher,
}


def _build_player(position_track: str, stats: dict, identity: dict):
    """Build a PlayerType object from stats + identity fields."""
    PlayerClass = PLAYER_CLASS_MAP[position_track]
    # Merge identity fields (height, weight, position, region, handedness) with stats
    merged = {**identity, **stats}
    return PlayerClass(**merged)


def _get_probability(result, target_level: str) -> float:
    """Extract the relevant probability from MLPipelineResults."""
    if target_level == "Power 4 D1" and result.p4_results:
        return result.p4_results.p4_probability
    return result.d1_results.d1_probability


def compute_sensitivity(
    position_track: str,
    current_stats: dict,
    identity_fields: dict,
    target_level: str = "D1",
) -> Dict[str, Any]:
    """
    Run sensitivity analysis for a player.

    Args:
        position_track: "infielder", "outfielder", "catcher", "pitcher"
        current_stats: Dict of stat_name -> current_value (only perturbable stats)
        identity_fields: Dict with height, weight, primary_position, region,
                         and handedness fields (not perturbed)
        target_level: "D1" or "Power 4 D1"

    Returns:
        Dict with:
        - base_probability: float
        - rankings: List of dicts sorted by max impact, each with:
          - stat_name, display, unit, current_value, direction
          - steps: List of {delta, new_value, new_probability, probability_change}
          - max_impact: float (biggest probability change across steps)
    """
    pipeline = PIPELINE_MAP.get(position_track)
    if pipeline is None:
        raise ValueError(f"No pipeline available for {position_track}")

    perturbable = get_perturbable_stats(position_track)

    # 1. Get base prediction
    base_player = _build_player(position_track, current_stats, identity_fields)
    base_result = pipeline.predict(base_player)
    base_prob = _get_probability(base_result, target_level)

    # 2. Perturb each stat and record deltas
    rankings = []
    for stat_name, config in perturbable.items():
        current_value = current_stats.get(stat_name)
        if current_value is None:
            continue

        steps_results = []
        for step in config["steps"]:
            # Direction-aware: +1 means add step, -1 means subtract step
            new_value = current_value + (step * config["dir"])
            perturbed_stats = {**current_stats, stat_name: new_value}

            perturbed_player = _build_player(position_track, perturbed_stats, identity_fields)
            perturbed_result = pipeline.predict(perturbed_player)
            new_prob = _get_probability(perturbed_result, target_level)

            steps_results.append({
                "delta": step,
                "new_value": round(new_value, 3),
                "new_probability": round(new_prob, 4),
                "probability_change": round(new_prob - base_prob, 4),
            })

        max_impact = max(abs(s["probability_change"]) for s in steps_results) if steps_results else 0

        rankings.append({
            "stat_name": stat_name,
            "display": config["display"],
            "unit": config["unit"],
            "current_value": current_value,
            "direction": "increase" if config["dir"] == 1 else "decrease",
            "steps": steps_results,
            "max_impact": round(max_impact, 4),
        })

    # 3. Sort by max impact (descending)
    rankings.sort(key=lambda x: x["max_impact"], reverse=True)

    return {
        "base_probability": round(base_prob, 4),
        "target_level": target_level,
        "position_track": position_track,
        "rankings": rankings,
    }
```

### File: `backend/api/routers/goals.py`

**Endpoint implementations:**

```
POST   /goals                          → create_goal()
GET    /goals                          → list_goals()
GET    /goals/{goal_id}                → get_goal()
PATCH  /goals/{goal_id}                → update_goal()
POST   /goals/{goal_id}/progress       → log_progress()
GET    /goals/{goal_id}/sensitivity    → get_sensitivity()
GET    /goals/{goal_id}/gap-to-range   → get_gap_to_range()
GET    /goals/ranges/{position}/{level} → get_stat_ranges()
```

**Pydantic models:**

```python
class GoalCreateRequest(BaseModel):
    position_track: Literal["pitcher", "infielder", "outfielder", "catcher"]
    target_level: str = "D1"
    current_stats: Dict[str, float]
    identity_fields: Dict[str, Any]  # height, weight, position, region, handedness
    evaluation_run_id: Optional[str] = None  # If created from an eval

class GoalUpdateRequest(BaseModel):
    target_level: Optional[str] = None
    target_stats: Optional[Dict[str, float]] = None

class ProgressEntryRequest(BaseModel):
    stat_name: str
    stat_value: float
    source: str = "manual"
    evaluation_run_id: Optional[str] = None
```

**Sensitivity caching logic (GET /goals/{goal_id}/sensitivity):**
1. Check `sensitivity_computed_at` — if within 24 hours AND `sensitivity_results` is not null, return cached
2. Otherwise, call `compute_sensitivity()` from the sensitivity service
3. Store result in `sensitivity_results` JSONB and update `sensitivity_computed_at`
4. Return the result

**Gap-to-range logic (GET /goals/{goal_id}/gap-to-range):**
1. Read goal's `position_track`, `target_level`, and `current_stats`
2. Query `position_stat_ranges` for matching (position_track, level) rows
3. For each stat in `current_stats`, find the range row and compute:
   - Where the player's value falls relative to p10/p25/median/p75/p90
   - Whether they're below, within, or above the target band
4. Return structured comparison data

### File: `backend/scripts/compute_stat_ranges.py`

**One-time script** that reads training CSVs and populates `position_stat_ranges`.

**Implementation details:**
- Uses `pandas` for CSV reading and percentile computation
- Reads from:
  - `backend/data/hitters/inf_feat_eng.csv`
  - `backend/data/hitters/of_feat_eng_d1_or_not.csv`
  - `backend/data/hitters/c_d1_or_not_data.csv`
  - `backend/data/pitchers/pitchers_data_clean.csv`
- Groups by the D1/P4 label column in each CSV
- Computes: p10, p25, median (p50), p75, p90, mean, std, count for each stat
- Upserts into `position_stat_ranges` with `data_version` tag (e.g., "v1")
- Uses the Supabase admin client for database writes

**Note:** Before implementing, inspect the CSV headers to identify the label column names (e.g., `d1_or_not`, `is_d1`, `label`, etc.) and stat column names. The CSV column names may not match the `PlayerType` attribute names exactly — mapping may be needed.

---

## 5. Phase 4: Backend — Registration & Wiring

### Modify: `backend/api/main.py`

Add these imports and router registrations:

```python
# Add after existing imports:
from api.routers.player_card import router as player_card_router
from api.routers.public_card import router as public_card_router
from api.routers.goals import router as goals_router

# Add after existing app.include_router() calls:
app.include_router(player_card_router, prefix="/cards", tags=["player-cards"])
app.include_router(public_card_router, prefix="/p", tags=["public-cards"])
app.include_router(goals_router, prefix="/goals", tags=["goals"])
```

### New Dependencies

**Backend** (`requirements.txt` additions):
```
nanoid>=2.0.0
Pillow>=10.0.0
```

**Frontend** (`package.json` additions):
```
html-to-image
```

Install via:
```bash
cd backend && pip install nanoid Pillow
cd frontend && npm install html-to-image
```

---

## 6. Phase 5: Frontend — Player Card Components

All components go in `frontend/src/components/player-card/`.

### Component: `player-card-container.tsx`

The 3D flip container using CSS `perspective` and `backface-visibility`.

**Key CSS:**
```css
.card-container {
  perspective: 1000px;
  width: 350px;
  height: 490px;
}
.card-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.6s;
  transform-style: preserve-3d;
}
.card-inner.flipped {
  transform: rotateY(180deg);
}
.card-face {
  position: absolute;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  border-radius: 16px;
  overflow: hidden;
}
.card-back {
  transform: rotateY(180deg);
}
```

**Component structure:**
```typescript
"use client";
import { useState, useRef } from "react";

type Props = {
  front: React.ReactNode;
  back: React.ReactNode;
  onMouseMove?: (e: React.MouseEvent) => void;
};

export function PlayerCardContainer({ front, back, onMouseMove }: Props) {
  const [flipped, setFlipped] = useState(false);
  // ... perspective, flip toggle, mouse tracking for holographic ...
}
```

### Component: `holographic-effect.tsx`

Mouse-tracking rainbow gradient overlay.

**CSS approach:**
```css
.holo-overlay {
  position: absolute;
  inset: 0;
  background: conic-gradient(
    from calc(var(--holo-angle, 0) * 1deg),
    hsl(0, 80%, 70%),
    hsl(60, 80%, 70%),
    hsl(120, 80%, 70%),
    hsl(180, 80%, 70%),
    hsl(240, 80%, 70%),
    hsl(300, 80%, 70%),
    hsl(360, 80%, 70%)
  );
  mix-blend-mode: color-dodge;
  opacity: 0.5;
  pointer-events: none;
  transform: translate(
    calc((var(--holo-x, 0.5) - 0.5) * 20px),
    calc((var(--holo-y, 0.5) - 0.5) * 20px)
  );
  transition: transform 100ms ease;
}

@media (prefers-reduced-motion: reduce) {
  .holo-overlay {
    opacity: 0;
  }
}
```

**onMouseMove handler** (in container):
```typescript
function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
  const rect = e.currentTarget.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;
  const y = (e.clientY - rect.top) / rect.height;
  e.currentTarget.style.setProperty("--holo-x", String(x));
  e.currentTarget.style.setProperty("--holo-y", String(y));
  // Slight 3D tilt
  const rotateX = (y - 0.5) * -10;
  const rotateY = (x - 0.5) * 10;
  e.currentTarget.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
}
```

### Component: `player-card-front.tsx`

**Props:**
```typescript
type CardFrontProps = {
  displayName: string;
  position: string;
  classYear?: number;
  photoUrl?: string;
  stats: Array<{ label: string; value: string | number; unit: string }>;
};
```

**Layout (top to bottom):**
1. Holographic border (4px, rendered via border gradient or outer div)
2. Photo area (top 60%) — uses `<img>` with `object-fit: cover` or a placeholder
3. Position badge — absolute positioned top-left pill
4. Class year — absolute positioned top-right
5. Name bar — absolute positioned at bottom of photo with semi-transparent dark overlay
6. Stats grid — bottom 40%, 2-column grid of `CardStatRow` components
7. BP watermark — small text at bottom center

**Colors:** Background navy `#18365a`, text white, accents per design system.

### Component: `player-card-back.tsx`

**Props:**
```typescript
type CardBackProps = {
  predictionLevel: string;
  d1Probability: number;
  p4Probability?: number | null;
  videoLinks: Array<{ url: string; label: string; platform?: string }>;
  visiblePreferences: Record<string, string>;
  profileLink?: string;
  shareUrl?: string;
};
```

### Component: `card-stat-row.tsx`

Simple stat display row: label on left, value + unit on right.

### Component: `card-export-button.tsx`

Uses `html-to-image` library:
```typescript
import { toPng } from "html-to-image";

async function exportCard(cardRef: HTMLElement, size: "instagram" | "twitter") {
  const dimensions = size === "instagram"
    ? { width: 1080, height: 1512 }
    : { width: 1200, height: 675 };

  const dataUrl = await toPng(cardRef, {
    pixelRatio: 3,
    width: dimensions.width / 3,
    height: dimensions.height / 3,
  });

  const link = document.createElement("a");
  link.download = `baseballpath-card.png`;
  link.href = dataUrl;
  link.click();
}
```

### Component: `share-link-generator.tsx`

**Features:**
- Platform selector buttons (Instagram, Twitter, General)
- "Generate Link" button → calls `POST /cards/me/share`
- Copy-to-clipboard with visual feedback
- List of existing share links with click counts

### Component: `card-analytics-panel.tsx`

**Features:**
- Total clicks / unique clicks counters
- Platform breakdown (simple bar or pill display)
- Recent clicks list (last 10)

### Component: `photo-upload.tsx`

**Features:**
- Drag-and-drop zone with visual feedback
- File type validation (jpeg/png/webp) client-side
- Size validation (< 5MB) client-side
- Preview before upload
- Calls `POST /cards/me/photo` with `FormData`

### Component: `preference-visibility-toggles.tsx`

Toggle switches for each preference field. Maps preference keys to labels and renders a toggle for each.

---

## 7. Phase 6: Frontend — Player Card Pages

### File: `frontend/src/app/card/page.tsx`

**Authenticated page.** Uses `useRequireAuth("/card")`.

**State machine:**
1. Load card via `GET /cards/me` on mount
2. If 404 → show creation wizard
3. If card exists → show management view

**Creation wizard steps (stepper UI):**
- Step 1: Select evaluation (fetch `GET /evaluations?limit=20` to list)
- Step 2: Upload photo, set display name, high school
- Step 3: Add video links
- Step 4: Toggle preference visibility
- Step 5: Preview card with flip → Confirm (calls `POST /cards`)

**Management view layout:**
- Left column: Full-size card preview (flip on click)
- Right column: Tabbed panels
  - Edit tab: form fields for video links, preferences, photo
  - Share tab: `ShareLinkGenerator` component
  - Analytics tab: `CardAnalyticsPanel` component
- Action buttons: "Refresh from Latest Evaluation", "Download as PNG"

### File: `frontend/src/app/p/[slug]/page.tsx`

**Public page. NO auth required.** This uses server-side data fetching.

**Implementation:**
```typescript
// This should use generateMetadata for OG tags
import type { Metadata } from "next";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const res = await fetch(`${API_BASE_URL}/p/${slug}/data`);
  if (!res.ok) return { title: "BaseballPath" };
  const card = await res.json();
  return {
    title: `${card.display_name} - ${card.primary_position} | BaseballPath`,
    description: `${card.prediction_level} prospect. View stats and profile.`,
    openGraph: {
      title: `${card.display_name} - ${card.primary_position} | BaseballPath`,
      images: [`${API_BASE_URL}/p/${slug}/og-image`],
    },
    twitter: {
      card: "summary_large_image",
      title: `${card.display_name} - ${card.primary_position} | BaseballPath`,
      images: [`${API_BASE_URL}/p/${slug}/og-image`],
    },
  };
}

export default async function PublicCardPage({ params }: Props) {
  const { slug } = await params;
  // Fetch card data server-side
  // Render card (front view, click to flip)
  // CTA: "Build your own Player Card on BaseballPath"
}
```

**Note:** This page should be a server component for SEO. The interactive card flip can be a client component embedded within it.

---

## 8. Phase 7: Frontend — Goals Components

All components go in `frontend/src/components/goals/`.

### Component: `leverage-rank-card.tsx`

**Props:**
```typescript
type LeverageRankCardProps = {
  rank: number;
  statName: string;
  displayName: string;
  unit: string;
  currentValue: number;
  maxImpact: number;
  steps: Array<{
    delta: number;
    newValue: number;
    newProbability: number;
    probabilityChange: number;
  }>;
};
```

**Visual:**
- Rank number on the left
- Stat name + current value
- Horizontal bar showing probability delta (green for positive impact)
- Color coding: high impact = green, medium = primary, low = muted

### Component: `gap-to-range-chart.tsx`

**Props:**
```typescript
type GapToRangeChartProps = {
  stats: Array<{
    statName: string;
    displayName: string;
    unit: string;
    currentValue: number;
    p10: number;
    p25: number;
    median: number;
    p75: number;
    p90: number;
  }>;
};
```

**Visual per stat:**
- Horizontal bar showing the full range (p10 to p90)
- Shaded band for p25-p75 (the "typical" range)
- Vertical marker for the player's current value
- Color: green if within p25-p75, orange if below p25, sand if above p75

### Component: `sensitivity-summary.tsx`

Shows the top 3 leverage stats with headline framing. Uses the standard framing copy:
> "Based on our model's analysis..."

### Component: `progress-timeline.tsx`

Line chart showing probability over time as stats are updated. Can use a simple SVG-based chart or basic `<canvas>` — no heavy charting lib needed for MVP.

### Component: `stat-update-form.tsx`

Form with one input per perturbable stat for the goal's position. Submit calls `POST /goals/{goalId}/progress` for each changed stat.

### Component: `disclaimer-banner.tsx`

Reusable banner with the standard disclaimer text. Shown on every page/section that displays sensitivity or gap-to-range data.

```typescript
export function DisclaimerBanner() {
  return (
    <div className="rounded-xl border border-[var(--stroke)] bg-[var(--sand)]/30 p-4">
      <p className="text-xs text-[var(--muted)]">
        Model estimates are based on patterns in historical player data. They reflect statistical
        tendencies, not guarantees. Many factors beyond metrics — including academics, character,
        coaching relationships, and timing — affect recruiting outcomes. Use these insights as one
        tool in your development plan.
      </p>
    </div>
  );
}
```

---

## 9. Phase 8: Frontend — Goals Pages

### File: `frontend/src/app/goals/page.tsx`

**Goals overview page.** Authenticated via `useRequireAuth("/goals")`.

**On mount:** Fetch `GET /goals` to list active goals.

**Layout:**
- Page header: "Goals & Improvement"
- Grid of goal summary cards (each links to `/goals/{goalId}`)
- Each card shows: position badge, target level, current probability, top leverage stat name, last updated date
- Empty state: "Set Up Goals" CTA linking to `/goals/create`
- "Add New Goal Set" button

### File: `frontend/src/app/goals/[goalId]/page.tsx`

**Goal detail page.** Authenticated.

**On mount:**
1. Fetch `GET /goals/{goalId}` for goal data
2. Fetch `GET /goals/{goalId}/sensitivity` for leverage rankings
3. Fetch `GET /goals/{goalId}/gap-to-range` for range comparisons

**Layout — three sections (tabs or scrollable):**

1. **Leverage Rankings**
   - `DisclaimerBanner` at top
   - `SensitivitySummary` (top 3 headline)
   - List of `LeverageRankCard` components

2. **Gap-to-Range**
   - `DisclaimerBanner` at top
   - `GapToRangeChart` with all stats

3. **Progress**
   - `ProgressTimeline` chart
   - `StatUpdateForm` to log new values

### File: `frontend/src/app/goals/create/page.tsx`

**Goal creation page.** Authenticated.

**Stepper flow:**
- Step 1: Select position (dropdown, or auto-detect from profile's `primary_position`)
- Step 2: Enter stats manually OR "Import from Latest Evaluation" button
  - Import: Fetch `GET /evaluations?limit=1`, extract stats from `stats_input`
- Step 3: Select target level — "D1" or "Power 4 D1" radio buttons
- Step 4: Preview — call sensitivity analysis inline and show initial leverage rankings
- Step 5: Confirm → `POST /goals`

---

## 10. Phase 9: Nav & Dashboard Integration

### Modify: `frontend/src/components/ui/authenticated-topbar.tsx`

Update the `navItems` array:

```typescript
const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/predict", label: "Predict" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/card", label: "Player Card" },
  { href: "/goals", label: "Goals" },
  { href: "/plans", label: "Plans" },
  { href: "/account", label: "Account" },
];
```

### Modify: `frontend/src/app/dashboard/page.tsx`

Add two new sections after the existing "Past evaluations" section:

**Section: Player Card Preview**
- Fetch card status from `GET /cards/me` (handle 404 = no card)
- If card exists: show small card thumbnail + "Share Your Card" link to `/card`
- If no card: show "Create Your Player Card" CTA linking to `/card`

**Section: Goals Snapshot**
- Fetch goals from `GET /goals` (handle empty = no goals)
- If goals exist: show top leverage stat name + current D1 probability + "View Goals" link
- If no goals: show "Set Improvement Goals" CTA linking to `/goals/create`

### Modify: `frontend/src/app/evaluations/[runId]/page.tsx`

Add two action buttons in the header area (next to "All evaluations" and "Run new evaluation"):

```typescript
<Link
  href={`/card?from_eval=${runId}`}
  className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)]"
>
  Create Card
</Link>
<Link
  href={`/goals/create?from_eval=${runId}`}
  className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)]"
>
  Set Goals
</Link>
```

The `/card` and `/goals/create` pages should read the `from_eval` query param and auto-import data from that evaluation run.

---

## 11. Phase 10: Polish & Testing

### Verification Checklist

**Database:**
- [ ] Run both migration files in Supabase SQL editor
- [ ] Verify all 6 new tables exist with correct columns
- [ ] Test RLS: authenticated user can only see own cards/goals
- [ ] Test RLS: `position_stat_ranges` readable by all authenticated users
- [ ] Test that `set_updated_at` trigger fires on updates

**Backend:**
- [ ] `POST /cards` creates card from evaluation data
- [ ] `GET /cards/me` returns card or 404
- [ ] `PATCH /cards/me` updates card fields
- [ ] `POST /cards/me/photo` accepts multipart upload, strips EXIF, stores in Supabase Storage
- [ ] `POST /cards/me/share` generates unique slug
- [ ] `GET /p/{slug}` records click and returns card data (filtered)
- [ ] `GET /p/{slug}/data` never returns hidden preferences
- [ ] `POST /goals` creates goal set
- [ ] `GET /goals/{id}/sensitivity` returns ranked stats with probability deltas
- [ ] `GET /goals/{id}/gap-to-range` returns correct percentile comparisons
- [ ] `POST /goals/{id}/progress` logs stat update
- [ ] Sensitivity cache invalidation works (new progress entry clears cache)

**Sensitivity Accuracy:**
- [ ] Run sensitivity on a known infielder (e.g., height=75, weight=210, SS, R/R, West, exit_velo=90, inf_velo=82, sixty=7.0)
- [ ] Verify increasing exit_velo increases D1 probability (positive delta)
- [ ] Verify decreasing sixty_time increases D1 probability (positive delta)
- [ ] Verify no negative deltas for "improvement" direction
- [ ] Verify magnitude is reasonable (not >50% change for 1 unit)

**Frontend:**
- [ ] Card creation wizard completes end-to-end
- [ ] Card flip animation works (perspective, backface-visibility)
- [ ] Holographic effect tracks mouse position
- [ ] Card export produces PNG image
- [ ] Share link copy-to-clipboard works
- [ ] Public card page renders without auth
- [ ] OG meta tags render correctly
- [ ] Goals creation from evaluation import works
- [ ] Leverage rankings display in correct order
- [ ] Gap-to-range chart shows player marker and bands
- [ ] Progress timeline updates after logging new stats
- [ ] Disclaimer banner appears on all sensitivity views
- [ ] Nav items appear in topbar
- [ ] Dashboard sections show card preview and goals snapshot

**Security:**
- [ ] Public card endpoint never exposes hidden preferences
- [ ] Photo EXIF data is stripped
- [ ] IP addresses are hashed (never stored raw)
- [ ] Rate limiting on click endpoint prevents abuse

---

## Appendix: Existing Code Reference

### PlayerType Constructor Signatures

**PlayerInfielder:**
```python
PlayerInfielder(
    height: int, weight: int, primary_position: str,
    hitting_handedness: str, throwing_hand: str, region: str,
    exit_velo_max: float, inf_velo: float, sixty_time: float
)
```

**PlayerOutfielder:**
```python
PlayerOutfielder(
    height: int, weight: int, primary_position: str,
    hitting_handedness: str, throwing_hand: str, region: str,
    exit_velo_max: float, of_velo: float, sixty_time: float
)
```

**PlayerCatcher:**
```python
PlayerCatcher(
    height: int, weight: int, primary_position: str,
    hitting_handedness: str, throwing_hand: str, region: str,
    exit_velo_max: float, c_velo: float, pop_time: float, sixty_time: float
)
```

**PlayerPitcher:**
```python
PlayerPitcher(
    height: int, weight: int, primary_position: str,
    throwing_hand: str, region: str,
    fastball_velo_range: float = None, fastball_velo_max: float = None,
    fastball_spin: float = None, changeup_velo: float = None,
    changeup_spin: float = None, curveball_velo: float = None,
    curveball_spin: float = None, slider_velo: float = None,
    slider_spin: float = None
)
```

### Pipeline Predict Signatures

All pipelines follow the same pattern:
```python
pipeline.predict(player: PlayerType) -> MLPipelineResults
```

Where `MLPipelineResults` has:
- `d1_results: D1PredictionResult` (always present)
  - `.d1_probability: float` (0.0-1.0)
  - `.d1_prediction: bool`
  - `.confidence: str`
- `p4_results: Optional[P4PredictionResult]` (only if D1 predicted)
  - `.p4_probability: float` (0.0-1.0)
  - `.p4_prediction: bool`
  - `.confidence: str`
  - `.is_elite: bool`

### Evaluation Run Data Shape

From `prediction_runs` table:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "position_track": "infielder",
  "identity_input": {"name": "...", "primary_position": "SS", ...},
  "stats_input": {"exit_velo_max": 90, "inf_velo": 82, "sixty_time": 7.0, ...},
  "preferences_input": {"preferred_regions": ["Northeast"], ...},
  "prediction_response": {
    "final_prediction": "Non-P4 D1",
    "d1_probability": 0.72,
    "p4_probability": 0.31,
    "d1_details": {...},
    "p4_details": {...},
    "player_info": {...}
  },
  "preferences_response": {...},
  "created_at": "2026-02-25T..."
}
```

This is the data source for card creation and goal creation from evaluations.

### Supabase Client Usage Pattern

```python
supabase = require_supabase_admin_client()

# Select
response = supabase.table("table_name").select("*").eq("user_id", user_id).execute()
rows = response.data  # List[Dict]

# Insert
response = supabase.table("table_name").insert({"key": "value"}).execute()
new_row = response.data[0]

# Update
response = supabase.table("table_name").update({"key": "value"}).eq("id", row_id).execute()

# Upsert
response = supabase.table("table_name").upsert(
    {"user_id": user_id, "key": "value"},
    on_conflict="user_id"
).execute()

# Delete
response = supabase.table("table_name").delete().eq("id", row_id).execute()
```

### Frontend API Headers Pattern

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const headers = {
  "Content-Type": "application/json",
  Authorization: `Bearer ${accessToken}`,
};

// For file uploads (no Content-Type — browser sets multipart boundary):
const formData = new FormData();
formData.append("file", file);
const response = await fetch(`${API_BASE_URL}/cards/me/photo`, {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: formData,
});
```

---

## Summary of All New Files

### Backend (8 files)
1. `backend/database/migrations/player_cards.sql`
2. `backend/database/migrations/goals_tracking.sql`
3. `backend/utils/perturbable_stats.py`
4. `backend/api/routers/player_card.py`
5. `backend/api/routers/public_card.py`
6. `backend/api/routers/goals.py`
7. `backend/api/services/sensitivity_service.py`
8. `backend/scripts/compute_stat_ranges.py`

### Frontend (20 files)
1. `frontend/src/app/card/page.tsx`
2. `frontend/src/app/p/[slug]/page.tsx`
3. `frontend/src/app/goals/page.tsx`
4. `frontend/src/app/goals/[goalId]/page.tsx`
5. `frontend/src/app/goals/create/page.tsx`
6. `frontend/src/components/player-card/player-card-front.tsx`
7. `frontend/src/components/player-card/player-card-back.tsx`
8. `frontend/src/components/player-card/player-card-container.tsx`
9. `frontend/src/components/player-card/holographic-effect.tsx`
10. `frontend/src/components/player-card/card-stat-row.tsx`
11. `frontend/src/components/player-card/preference-visibility-toggles.tsx`
12. `frontend/src/components/player-card/card-export-button.tsx`
13. `frontend/src/components/player-card/share-link-generator.tsx`
14. `frontend/src/components/player-card/card-analytics-panel.tsx`
15. `frontend/src/components/player-card/photo-upload.tsx`
16. `frontend/src/components/goals/leverage-rank-card.tsx`
17. `frontend/src/components/goals/gap-to-range-chart.tsx`
18. `frontend/src/components/goals/sensitivity-summary.tsx`
19. `frontend/src/components/goals/progress-timeline.tsx`
20. `frontend/src/components/goals/stat-update-form.tsx`

### Files to Modify (4 files)
1. `backend/api/main.py` — register 3 new routers
2. `frontend/src/components/ui/authenticated-topbar.tsx` — add nav items
3. `frontend/src/app/dashboard/page.tsx` — add card preview + goals snapshot
4. `frontend/src/app/evaluations/[runId]/page.tsx` — add action buttons
