# BaseballPath — Authenticated App Pages Builder

## Role

Act as a World-Class Senior Creative Technologist and Lead Frontend Engineer specializing in **application UI**. You build high-fidelity, polished app interfaces that feel like premium SaaS — dense with information but never cluttered, responsive and snappy, with micro-interactions that reward usage. Every page should feel like a well-tuned instrument panel.

---

## Design System Reference

This file extends the BaseballPath design system defined in `GEMINI.md`. All color tokens, typography, glass morphism, and animation patterns from that file apply here.

### Quick Reference — Desert Diamond Palette

| Token | Hex | App Usage |
|---|---|---|
| `--burnt-sienna` / `--primary` | `#A0522D` | Primary buttons, active nav, progress fills |
| `--golden-sand` / `--accent` | `#D4A843` | Badges, highlights, secondary CTAs, hover accents |
| `--walnut` / `--navy` | `#3B2718` | Dark UI elements, logo pill, stat circles |
| `--warm-cream` / `--background` | `#F5EFE0` | Page background |
| `--espresso` / `--foreground` | `#2C1810` | Primary text |
| `--sage-green` | `#6B8F5E` | Success states, "on track" indicators, positive deltas |
| `--parchment` / `--card` | `#FAF6EE` | Card backgrounds, elevated surfaces |
| `--clay-mist` / `--sand` | `#E8DCC8` | Borders, muted backgrounds, pill fills |
| `--muted` | `#7A6B5D` | Secondary text, descriptions, inactive states |
| `--stroke` | `#D4C4A8` | Borders, dividers |

### Typography in App Context

- **Page titles:** `display-font text-4xl md:text-5xl font-bold` (Fraunces serif)
- **Section headings:** `text-xl font-semibold` (Sora sans)
- **Card titles:** `text-lg font-semibold` (Sora sans)
- **Body / descriptions:** `text-sm text-[var(--muted)]` (Sora sans)
- **Stat values:** `text-2xl font-bold text-[var(--foreground)]` (Sora sans)
- **Stat labels:** `text-xs uppercase tracking-[0.14em] text-[var(--muted)]` (Sora sans)
- **Eyebrow tags:** `text-xs uppercase tracking-[0.2em] text-[var(--primary)]` (Sora sans)
- **Monospace data:** `font-mono text-sm` for raw numbers, IDs, timestamps

---

## App Shell

### Authenticated TopBar

The app uses a sticky top navigation bar (`frontend/src/components/ui/authenticated-topbar.tsx`). Key specs:

- **Position:** `sticky top-0 z-40` with `backdrop-blur-xl` and `border-b border-[var(--stroke)]/30`
- **Logo:** `h-11 w-11 rounded-2xl bg-[var(--navy)]` pill with "BP" initials in warm cream
- **Brand text:** "BaseballPath" in `text-xs uppercase tracking-[0.34em] text-[var(--muted)]`, subtitle "Recruiting Console"
- **Nav items:** Dashboard, Predict, Evaluations, Player Card, Goals, Plans, Account
- **Active state:** `text-[var(--foreground)]` with `border-b-2 border-[var(--primary)]`
- **Inactive state:** `text-[var(--muted)]` with hover `text-[var(--foreground)]`
- **Avatar dropdown:** User initials in `bg-[var(--primary)]` circle, dropdown shows name, plan tier, eval quota

### Content Area

- Max width: `max-w-6xl mx-auto` (consistent with landing page)
- Padding: `px-4 md:px-8 py-8 md:py-12`
- Background: `var(--background)` with the warm radial gradient `var(--page-bg)`

### Consistent Spacing & Layout

- Section gaps: `space-y-8` between major sections
- Card gaps: `gap-5` or `gap-6` in grids
- Inner card padding: `p-5` or `p-6`
- All cards: `glass rounded-2xl shadow-soft` unless specified otherwise
- Hover on clickable cards: `transition hover:-translate-y-0.5 hover:shadow-strong`

---

## Shared UI Patterns

### Data Cards

The primary building block. Used everywhere for stats, summaries, quick info.

```
glass rounded-2xl p-5 shadow-soft
├── Eyebrow label (text-xs uppercase tracking-wide text-[var(--primary)])
├── Value (text-2xl font-bold text-[var(--foreground)])
└── Descriptor (text-sm text-[var(--muted)])
```

### Stat Grids

For displaying multiple metrics side by side:
- `grid grid-cols-2 md:grid-cols-3 gap-4`
- Each cell: `glass rounded-xl p-4`
- Label: `text-xs uppercase tracking-[0.14em] text-[var(--muted)]`
- Value: `text-xl font-bold`
- Optional delta badge: `text-xs rounded-full px-2 py-0.5` — green for positive, burnt sienna for negative

### Probability Bars

Horizontal bars showing division-level probability:

```
rounded-full h-2.5 bg-[var(--sand)]        ← track
├── rounded-full h-2.5 bg-[var(--primary)]  ← fill (width = probability%)
└── text-sm font-semibold                   ← percentage label right-aligned
```

Color thresholds:
- ≥ 60%: `bg-[var(--sage-green)]` (strong fit)
- 30–59%: `bg-[var(--primary)]` (moderate fit)
- < 30%: `bg-[var(--accent)]` (stretch)

### Impact Bars (Goals)

Horizontal bars showing stat leverage:

```
rounded-full h-2 bg-[var(--sand)]/60        ← track
└── rounded-full h-2                         ← fill
```

Color by magnitude:
- ≥ 8% impact: `bg-[var(--primary)]` (high leverage)
- ≥ 3% impact: `bg-[var(--accent)]` (moderate leverage)
- < 3%: `bg-[var(--muted)]/40` (low leverage)

### Empty States

When a section has no data:

```
rounded-2xl border-2 border-dashed border-[var(--stroke)] p-8 text-center
├── Icon (Lucide, text-[var(--muted)]/40, size-12)
├── Heading (text-lg font-semibold text-[var(--foreground)])
├── Description (text-sm text-[var(--muted)] max-w-sm mx-auto)
└── CTA button (rounded-full bg-[var(--primary)] text-white)
```

### Loading States

- Skeleton shimmer: `animate-pulse bg-[var(--sand)]/60 rounded-xl`
- Match the shape and size of the content being loaded
- Use 2-3 skeleton blocks per card to suggest structure

### Wizards / Multi-Step Forms

Used in Predict and Goals Create:

- Step indicator: horizontal dots or numbered pills at top
- Active step: `bg-[var(--primary)] text-white rounded-full w-8 h-8`
- Completed step: `bg-[var(--sage-green)] text-white rounded-full w-8 h-8` with checkmark
- Future step: `bg-[var(--sand)] text-[var(--muted)] rounded-full w-8 h-8`
- Connector line: `h-0.5 bg-[var(--stroke)]` between steps, `bg-[var(--primary)]` when passed
- Navigation: "Back" (ghost button) + "Continue" (primary button) at bottom

### Form Controls

Use the existing `.form-control` class:
- `rounded-[0.9rem] border border-[var(--stroke)] bg-white px-4 py-3`
- Focus: `ring-2 ring-[var(--primary)]/30 border-[var(--primary)]`
- Labels: `text-sm font-medium text-[var(--foreground)]`
- Helper text: `text-xs text-[var(--muted)]`

### Toast / Flash Messages

- Success: `bg-[var(--sage-green)]/10 border border-[var(--sage-green)]/30 text-[var(--sage-green)]`
- Error: `bg-red-50 border border-red-200 text-red-700`
- Info: `bg-[var(--sand)]/50 border border-[var(--stroke)] text-[var(--foreground)]`
- All: `rounded-xl px-4 py-3 text-sm`

---

## Page Specifications

### 1. Dashboard (`/dashboard`)

The authenticated home. Dense but scannable overview of the user's recruiting state.

**Layout:**
```
Hero greeting area
├── display-font text-4xl: "Hey, {firstName}."
├── Two CTA buttons: "Start New Evaluation" (primary), "Account & Plan" (outline)

Stat strip (grid md:grid-cols-3 gap-5)
├── Plan & Quota card: tier badge, "{used}/{total} evaluations"
├── Last Projection card: division + probability, or empty state
├── Saved Schools card: count, or "Run an eval" prompt

Two-column middle (lg:grid-cols-[0.85fr_1.15fr] gap-6)
├── Getting Started (3 step cards with checkmarks for completed)
│   ├── 1. Run your first evaluation → /predict
│   ├── 2. Set up improvement goals → /goals
│   └── 3. Build your Player Card → /card
└── Past Evaluations list (up to 10, each clickable → /evaluations/[runId])
    ├── Division badge + probability
    ├── Timestamp
    └── School count

Two-column bottom (md:grid-cols-2 gap-6)
├── Player Card preview widget
│   ├── Mini card thumbnail or "Build your card" empty state
│   └── "View full card →" link
└── Goals snapshot (up to 2 active goals)
    ├── Goal name + target division
    ├── Progress indicator (X of Y stats on track)
    └── "View all goals →" link
```

### 2. Predict (`/predict`)

Multi-step evaluation wizard. Steps vary based on existing implementation — preserve the current flow.

**Design Patterns:**
- Use the wizard step indicator at top
- Each step is a form section inside a `glass rounded-2xl p-6` card
- Input fields use `.form-control` styling
- Position selector (if present): grid of position pills, active = `bg-[var(--primary)] text-white`
- Stat inputs: labeled number inputs in a 2-column grid
- Review step: summary card showing all entered data before submission
- Submit CTA: "Get my projection →" — large primary button
- Loading state during model inference: pulsing animation with "Analyzing your profile..." text

### 3. Evaluations List (`/evaluations`)

**Layout:**
- Page title: `display-font text-4xl` — "Your Evaluations"
- Subtitle: `text-[var(--muted)]` — "Every projection you've run, in one place."

**List:**
- Each evaluation row: `glass rounded-2xl p-5 flex items-center justify-between`
- Left: Division badge (`rounded-full px-3 py-1 bg-[var(--primary)]/10 text-[var(--primary)] text-xs font-semibold`) + probability (`text-xl font-bold`) + date (`text-sm text-[var(--muted)]`)
- Right: School count + arrow icon → links to `/evaluations/[runId]`
- Hover: `-translate-y-0.5` lift + `shadow-strong`

**Empty state:** "No evaluations yet" + "Run your first projection →" CTA

### 4. Evaluation Detail (`/evaluations/[runId]`)

**Layout:**
- Back link: "← All Evaluations" at top
- Hero card: `glass rounded-2xl p-6` with:
  - Division prediction + probability bar
  - Date + position
  - Key input stats summary

- School list: `space-y-3`, each school in a `glass rounded-xl p-4`:
  - School name (`text-lg font-semibold`)
  - Division + conference badges
  - Probability bar
  - Expand/collapse for AI reasoning (if available)

- AI Analysis section (if available): `bg-[var(--navy)] text-white rounded-2xl p-6` with model reasoning text

### 5. Goals List (`/goals`)

**Layout:**
- Page title: `display-font text-4xl` — "Your Goals"
- Subtitle: "Track what matters most for your projection."
- CTA: "Create Goal Set +" — primary button

**Goal cards:** `glass rounded-2xl p-5`, clickable → `/goals/[goalId]`
- Goal name + target division
- Progress bar: `rounded-full h-2 bg-[var(--sand)]` track, `bg-[var(--sage-green)]` fill
- "X of Y stats on track" label
- Last updated timestamp

**Empty state:** "No goals yet" + illustration + "Create your first goal set →" CTA

### 6. Goal Detail (`/goals/[goalId]`)

Tabbed interface with three views:

**Tab 1 — Leverage Rankings**
- Disclaimer banner at top (existing component)
- Sensitivity summary card: base probability + top 3 leverage stats
- Ranked stat cards (existing `LeverageRankCard` component):
  - Rank circle: `bg-[var(--navy)]` with `#N`
  - Stat name + current value
  - Impact bar (color by magnitude)
  - "Best step" recommendation

**Tab 2 — Gap to Range**
- Per-stat range visualization (existing `GapToRangeChart` component):
  - Full-width track
  - IQR fill + percentile markers
  - Current value marker (color-coded vs. target range)

**Tab 3 — Progress**
- Timeline chart (existing `ProgressTimeline` component)
- Stat update form (existing `StatUpdateForm` component)
- Log entries below with timestamps

**Tab styling:**
- Tab bar: `flex gap-1 bg-[var(--sand)]/40 rounded-xl p-1`
- Active tab: `bg-white rounded-lg px-4 py-2 text-[var(--foreground)] font-medium shadow-sm`
- Inactive tab: `px-4 py-2 text-[var(--muted)]`

### 7. Goals Create (`/goals/create`)

Five-step wizard:

1. **Select Evaluation** — Pick which evaluation to base goals on
2. **Choose Target Division** — Division selector pills
3. **Review Leverage Stats** — Show model's recommended stats to focus on
4. **Set Targets** — Adjust target values for each stat
5. **Confirm** — Review and create

Use wizard pattern from Shared UI Patterns. Each step in a `glass rounded-2xl p-6` card.

### 8. Player Card (`/card`)

**Layout:**
- Page title: `display-font text-4xl` — "Your Player Card"
- Two-column on desktop: Card preview (left) + Controls (right)

**Left — Card Preview:**
- Live-updating `PlayerCardContainer` component (see `GEMINI-CARD.md` for card specs)
- Click to flip between front and back
- Mouse tilt 3D effect active

**Right — Controls:**
- Photo upload section (drag-and-drop zone)
- Preference visibility toggles (iOS-style switches)
- Share link generator:
  - Platform selector pills (Instagram, Twitter, General)
  - "Generate link" button
  - List of existing links with click counts and copy button
- Export buttons: "Export for Instagram" / "Export for Twitter"
- Analytics panel: total clicks, unique clicks, platform breakdown

### 9. Public Card (`/p/[slug]`)

Public-facing, unauthenticated page showing a shared Player Card.

**Layout:**
- Full-screen centered, `bg-[var(--espresso)]` dark background
- `PlayerCardContainer` centered on screen
- "Build your own Player Card on BaseballPath" CTA below card — `rounded-full bg-[var(--primary)] text-white`
- BaseballPath wordmark at bottom in warm cream

### 10. Plans (`/plans`)

Pricing page (can be shown to both authed and unauthed users).

**Layout:**
- Page title: `display-font text-4xl` — "Choose Your Plan"
- Three-tier grid matching landing page pricing section specs (see `GEMINI.md` Section G)
- If user is authenticated, highlight their current plan with a badge
- Upgrade/downgrade CTAs adjust based on current tier

### 11. Account (`/account`)

**Layout:**
- Page title: `display-font text-4xl` — "Account"

**Sections (stacked `glass rounded-2xl p-6` cards):**
1. **Profile** — Name, email, position, class year, graduation year
2. **Plan & Billing** — Current tier badge, eval quota usage bar, upgrade CTA
3. **Preferences** — Notification settings, display preferences
4. **Danger Zone** — Delete account (red outline button, confirmation modal)

---

## Transitions & State

### Page Transitions
- Use `FadeOnScroll` or simple CSS transitions for section reveals
- No full-page transition animations (Next.js App Router handles routing)

### Data Fetching States
Every page that fetches data must handle three states:
1. **Loading:** Skeleton shimmer matching content layout
2. **Empty:** Illustrated empty state with actionable CTA
3. **Populated:** Full data display

### Error States
- API errors: Toast notification + inline error message
- Network errors: Full-page retry prompt with warm illustration
- 404: "Page not found" with link back to Dashboard

---

## Build Guidance

When building or modifying any authenticated app page:

1. **Read the existing page code first** — preserve working logic, data fetching, and state management.
2. **Apply Desert Diamond palette** — update any remaining navy/blue references to warm equivalents.
3. **Use existing components** — `glass` utility, `FadeOnScroll`, `display-font`, existing goal/card components.
4. **Match this spec for layout and spacing** — but defer to existing code for data flow and API integration.
5. **No new font imports.** Use `--font-sora` and `--font-fraunces` exclusively.
6. **No sharp corners.** Every container `rounded-xl` minimum, most `rounded-2xl`.
7. **Mobile-first.** All grids stack on mobile. Touch targets ≥ 44px.

**Execution Directive:** "Every page should feel like it belongs to the same product. Consistent spacing, consistent color, consistent interaction patterns. The app should feel as polished as the landing page."
