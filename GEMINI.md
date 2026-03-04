# BaseballPATH — Landing Page & Marketing Pages Builder

## Role

Act as a World-Class Senior Creative Technologist and Lead Frontend Engineer. You build high-fidelity, cinematic "1:1 Pixel Perfect" landing pages. Every site you produce should feel like a digital instrument — every scroll intentional, every animation weighted and professional. Eradicate all generic AI patterns.

---

## Brand Identity

**BaseballPATH** — AI-powered recruiting projections that show high school baseball players exactly where they fit at the college level.

- **Tagline:** "Stop guessing. Know your best-fit schools."
- **Voice:** Confident, honest, no fluff. Not opinions — outcomes.
- **Audience:** High school baseball players (and their parents) navigating the recruiting process.
- **Vibe:** Premium & Confident meets Energetic & Bold. Think high-end sports agency with data-forward boldness and real human stories. NOT another navy-and-white "scouting" site. NOT pitch-black "tech bro" energy.

---

## Design System — "Desert Diamond"

### Color Palette

| Token | Name | Hex | Usage |
|---|---|---|---|
| `--burnt-sienna` | Burnt Sienna | `#A0522D` | Primary accent, CTA buttons, active states |
| `--golden-sand` | Golden Sand | `#D4A843` | Secondary accent, highlights, badges, hover states |
| `--walnut` | Walnut | `#3B2718` | Dark backgrounds, hero overlays, section contrast |
| `--warm-cream` | Warm Cream | `#F5EFE0` | Page background, light surfaces |
| `--espresso` | Espresso | `#2C1810` | Deepest dark, text on light, footer backgrounds |
| `--sage-green` | Sage Green | `#6B8F5E` | Success states, positive metrics, trust signals |
| `--copper` | Copper | `#B87333` | Tertiary accent, icon tints, decorative elements |
| `--parchment` | Parchment | `#FAF6EE` | Card backgrounds, elevated surfaces |
| `--clay-mist` | Clay Mist | `#E8DCC8` | Borders, dividers, muted surfaces |

### Mapping to Existing CSS Variables

When building pages, map Desert Diamond tokens to the project's existing CSS custom properties in `globals.css`:

```css
:root {
  --background:   #F5EFE0;   /* Warm Cream */
  --foreground:   #2C1810;   /* Espresso */
  --primary:      #A0522D;   /* Burnt Sienna */
  --primary-dark: #7A3E22;   /* Burnt Sienna darkened */
  --accent:       #D4A843;   /* Golden Sand */
  --navy:         #3B2718;   /* Walnut (replaces navy everywhere) */
  --sand:         #E8DCC8;   /* Clay Mist */
  --muted:        #7A6B5D;   /* Warm grey-brown */
  --card:         #FAF6EE;   /* Parchment */
  --stroke:       #D4C4A8;   /* Warm tan border */
  --surface:      rgba(250,246,238,0.78); /* Semi-transparent parchment */
}
```

### Page Background Gradient

Replace cool-toned radial gradients with warm Desert Diamond version:

```css
--page-bg:
  radial-gradient(980px 620px at 8% -8%, rgba(160,82,45,0.18) 0%, transparent 70%),
  radial-gradient(860px 540px at 96% 0%, rgba(212,168,67,0.14) 0%, transparent 70%),
  radial-gradient(600px 600px at 50% 80%, rgba(107,143,94,0.08) 0%, transparent 70%),
  linear-gradient(180deg, #FAF6EE 0%, #F5EFE0 100%);
```

### Typography

Use the project's existing font variables — do NOT import new fonts:

| Role | Font | Variable | Usage |
|---|---|---|---|
| Display / Headlines | Fraunces (variable serif) | `--font-fraunces` / `.display-font` | Hero headlines, section titles, manifesto quotes |
| Body / UI | Sora (geometric sans) | `--font-sora` / `font-sans` | Body text, nav, buttons, cards |
| Data / Mono | System monospace | `font-mono` | Stats, numbers, code-style labels |

**Typographic Rules:**
- Hero headline: `display-font text-5xl md:text-7xl font-bold` — Fraunces serif for gravitas
- Section headings: `display-font text-3xl md:text-4xl` — Fraunces
- Card headings: `text-lg font-semibold` — Sora sans
- Body text: `text-base text-[var(--muted)]` — Sora sans
- Eyebrow labels: `text-xs uppercase tracking-[0.2em] text-[var(--burnt-sienna)]` — Sora sans
- Stat numbers: `font-mono text-2xl font-bold text-[var(--walnut)]`

### Glass Morphism — Warm Variant

The existing `.glass` utility rethemed for warm tones:

```css
.glass {
  background: linear-gradient(
    135deg,
    rgba(250, 246, 238, 0.72) 0%,
    rgba(245, 239, 224, 0.48) 100%
  );
  border: 1px solid rgba(212, 168, 67, 0.18);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
```

### Visual Texture

- **Noise overlay:** Global CSS noise using inline SVG `<feTurbulence>` filter at **0.04 opacity**, warm-tinted. Eliminates flat digital gradients.
- **Radius system:** `rounded-[2rem]` to `rounded-[3rem]` for all containers. No sharp corners anywhere.

### Micro-Interactions

- All buttons: **"magnetic" feel** — `scale(1.03)` on hover with `cubic-bezier(0.25, 0.46, 0.45, 0.94)`.
- Buttons use `overflow-hidden` with a sliding `<span>` background layer for color transitions on hover.
- Links and interactive elements: `translateY(-1px)` lift on hover.
- CTA buttons: `bg-[var(--primary)] text-white rounded-full px-8 py-3` with golden sand shimmer on hover.

### Animation Lifecycle

- Use `gsap.context()` within `useEffect`. Return `ctx.revert()` in cleanup.
- Default easing: `power3.out` for entrances, `power2.inOut` for morphs.
- Stagger: `0.08` for text, `0.15` for cards/containers.
- All scroll animations use `ScrollTrigger` or the existing `FadeOnScroll` component.

---

## Component Architecture — BaseballPATH Landing Page

### A. NAVBAR — "The Floating Island"

A `fixed` pill-shaped container, horizontally centered.

**Morphing Logic:** Transparent with warm cream text at hero top. Transitions to `bg-[var(--warm-cream)]/60 backdrop-blur-xl` with espresso-colored text and a subtle `border border-[var(--clay-mist)]` when scrolled past the hero. Use `IntersectionObserver` or `ScrollTrigger`.

**Contents:**
- Logo: BaseballPATH wordmark (Sora, `text-sm uppercase tracking-[0.3em]`)
- Nav links: How It Works, Features, Pricing
- CTA button: "Get Your Projection" — `bg-[var(--burnt-sienna)] text-white rounded-full`

**Auth-aware behavior:**
- If user is logged in, replace CTA with "Dashboard →" link
- Mobile: Collapse into minimal pill with hamburger

### B. HERO SECTION — "The Opening Shot"

`min-h-[100dvh]` with warm radial gradient background (no stock photo — use pure gradient + geometric accent shapes).

**Layout:** Two-column grid on desktop (`grid md:grid-cols-[1.1fr_0.9fr] max-w-6xl mx-auto`). Content left, visual right.

**Left Column:**
- Eyebrow: `text-xs uppercase tracking-[0.2em] text-[var(--burnt-sienna)]` — "AI-Powered Recruiting Projections"
- Headline (Fraunces serif, `text-5xl md:text-7xl font-bold text-[var(--espresso)]`):
  > "Stop guessing. Know your best-fit schools."
- Subheadline (`text-lg text-[var(--muted)] max-w-md mt-4`):
  > "BaseballPATH uses real D1–D3 player data to project where you'd compete — and what to improve to get there."
- Three bullet proof points (`mt-6 space-y-3`), each with a sage green checkmark icon:
  > - "Division-level projections grounded in 49,000+ college profiles"
  > - "Personalized improvement goals based on your biggest leverage stats"
  > - "A shareable Player Card that puts your projection in coaches' hands"
- CTA cluster (`mt-8 flex gap-4`):
  - Primary: "Check my projection →" — `bg-[var(--burnt-sienna)] text-white rounded-full px-8 py-3.5 text-base font-semibold`
  - Secondary: "See how it works" — `rounded-full border border-[var(--stroke)] px-6 py-3.5 text-[var(--walnut)]`

**Right Column:**
- A warm-toned glass card showing a **mini sample projection** — mock UI showing a school name, division badge, probability bar, and "Top Leverage Stat" callout. This is a static visual artifact, not functional.

**Animation:** GSAP staggered `fade-up` (y: 40 → 0, opacity: 0 → 1) for headline, subhead, bullets, CTAs. Right column fades in with slight delay.

### C. HOW IT WORKS — "The Four-Step Flow"

Section heading: `display-font text-3xl md:text-4xl text-center` — "From first stat to first call — in four steps."

Four cards in a horizontal row (`grid md:grid-cols-4 gap-6`). Each card:
- Step number: `font-mono text-sm text-[var(--burnt-sienna)]` — "01", "02", "03", "04"
- Icon: Simple Lucide icon in `text-[var(--golden-sand)]`
- Title: `text-lg font-semibold text-[var(--espresso)]`
- Description: `text-sm text-[var(--muted)]`

**Steps:**
1. **Add your metrics** — "Enter your measurables, grades, and stats. Takes under two minutes."
2. **Get your projection** — "Our model compares you against 49K+ college players and projects your division fit."
3. **Follow your goals** — "See which stats give you the most leverage — and track your progress toward them."
4. **Share your card** — "Generate a Player Card with your projection, stats, and video links. Send it to coaches."

Cards use `glass rounded-[2rem]` with warm shadow. Animated with `FadeOnScroll` stagger.

### D. FEATURES — "Know → Improve → Get Seen"

Section heading: `display-font text-3xl md:text-4xl text-center` — "Everything a recruit actually needs."

Three interactive feature cards (`grid md:grid-cols-3 gap-6`). Each card is a **functional micro-UI**, not a static marketing card.

**Card 1 — "Know Where You Fit" (Diagnostic Shuffler)**
Three overlapping cards that cycle vertically every 3 seconds with spring-bounce (`cubic-bezier(0.34, 1.56, 0.64, 1)`). Each sub-card shows a school name + division + probability. Labels:
- "Arizona State — D1 — 34%"
- "Cal Poly — D1 — 61%"
- "Sonoma State — D2 — 82%"

Heading: "Division-Level Projections"
Descriptor: "See exactly where your stats project — from D1 powerhouses to D3 programs. No guessing, no generic advice."

**Card 2 — "Improve What Matters" (Telemetry Typewriter)**
Monospace live-text feed typing out goal updates character-by-character with a blinking burnt-sienna cursor. Messages:
- `"→ 60yd: 6.92s → target 6.78s (D1 median)"`
- `"→ Exit velo +3mph unlocks 12% probability gain"`
- `"→ 3 of 5 leverage stats on track this month"`

Heading: "Leverage-Based Goals"
Descriptor: "Our model finds the stats that move your projection most — then tracks your progress week by week."

**Card 3 — "Get Seen by Coaches" (Cursor Protocol)**
Animated SVG cursor enters, moves to a "Share" button, clicks (scale press), card flips to reveal a mini Player Card preview, then a "Link copied!" toast appears.

Heading: "Shareable Player Cards"
Descriptor: "One link. Your projection, your stats, your video. Built to send to coaches — not sit in a spreadsheet."

All cards: `glass rounded-[2rem]` surface, warm border, drop shadow. Heading in Sora sans bold, descriptor in muted.

### E. PHILOSOPHY — "The Manifesto"

Full-width section with `bg-[var(--walnut)]` background. Warm noise texture overlay at low opacity.

**Typography — Two contrasting statements:**
1. "Most recruiting tools focus on: **exposure. Showcases. Hype.**" — `text-lg text-white/60`
2. "We focus on: **clarity.** A real projection. A plan that makes sense. A card that speaks for itself." — `display-font text-3xl md:text-5xl text-white` with "clarity" in `text-[var(--golden-sand)]`

**Manifesto line** below: `text-xl text-white/80 italic mt-8` —
> "Recruiting clarity shouldn't be a luxury — it should be the standard."

**Animation:** Word-by-word or line-by-line fade-up triggered by ScrollTrigger.

### F. TRUST BUILDERS — "Built by Recruits"

Two-column section on warm cream background.

**Left — Origin story snippet:**
> "BaseballPATH was built by a former recruit who went through the process — and saw how broken it was. No clear projections. No data. Just opinions."

**Right — Data credibility metrics** in a 2×2 grid, each in a `glass rounded-2xl` card:
- "49,000+" — "College player profiles in our dataset"
- "D1 → D3" — "Full division coverage, not just the top"
- "< 2 min" — "To get your first projection"
- "Real data" — "Not opinions. Not rankings. Outcomes."

### G. PRICING — "Find Your Tier"

Section heading: `display-font text-3xl md:text-4xl text-center` — "Start free. Upgrade when you're ready."

Three-tier pricing grid (`grid md:grid-cols-3 gap-6 max-w-4xl mx-auto`).

**Starter (Free)**
- 1 evaluation
- Division projection
- Basic school list
- CTA: "Start free" — outline button

**Pro ($X/mo)**
- Unlimited evaluations
- Full school rankings
- Leverage-based goals
- Player Card
- CTA: "Go Pro" — `bg-[var(--burnt-sienna)] text-white` solid button
- **This card pops:** Slightly larger, `ring-2 ring-[var(--golden-sand)]` border, "Most Popular" badge

**Elite ($X/mo)**
- Everything in Pro
- Priority model access
- Advanced analytics
- Coach outreach templates
- CTA: "Go Elite" — solid button

Cards: `glass rounded-[2rem]`, warm shadows. Middle card elevated.

### H. FINAL CTA — "The Close"

Full-width warm section with subtle radial gradient.

- Headline (Fraunces): "Your projection is waiting."
- Subtext: "Two minutes. Real data. No credit card."
- CTA: "Check my projection →" — large `bg-[var(--burnt-sienna)] text-white rounded-full` button
- Below CTA: "Join 200+ recruits already using BaseballPATH" in muted text

### I. FOOTER

`bg-[var(--espresso)] rounded-t-[4rem]` with warm cream text.

**Grid layout:**
- Column 1: BaseballPATH wordmark + tagline "AI-powered recruiting clarity."
- Column 2: Product links — How It Works, Features, Pricing, Player Card
- Column 3: Company — About, Privacy, Terms
- Column 4: Connect — Twitter/X, Instagram

**Bottom bar:** "© 2026 BaseballPATH. All rights reserved." + "System Operational" status indicator with pulsing sage green dot and monospace label.

---

## Marketing Copy Bank

Use these plug-and-play statements throughout the landing page and marketing materials. Do not invent new copy — pull from this bank.

### Headlines
- "Stop guessing. Know your best-fit schools."
- "Your projection is waiting."
- "Recruiting clarity shouldn't be a luxury."
- "From first stat to first call — in four steps."
- "Everything a recruit actually needs."

### Subheadlines / Supporting
- "BaseballPATH uses real D1–D3 player data to project where you'd compete — and what to improve to get there."
- "Not opinions. Not rankings. Outcomes."
- "Built by a recruit who went through the process — and saw how broken it was."
- "Two minutes. Real data. No credit card."

### Value Propositions (The Three Pillars)
- **Know:** "See exactly where your stats project — from D1 powerhouses to D3 programs."
- **Improve:** "Find the stats that move your projection most — and track your progress."
- **Get Seen:** "One link. Your projection, your stats, your video. Built to send to coaches."

### Contrast Statements (Manifesto)
- "Most recruiting tools focus on exposure. Showcases. Hype."
- "We focus on clarity. A real projection. A plan that makes sense."
- "Other platforms sell you access. We give you answers."
- "This isn't about rankings. It's about fit."

### Trust / Proof
- "49,000+ college player profiles"
- "D1 through D3 — full coverage"
- "Under 2 minutes to your first projection"
- "Built by recruits, for recruits"

### CTAs
- "Check my projection →" (primary)
- "See how it works" (secondary)
- "Start free" (pricing)
- "Go Pro" / "Go Elite" (upgrade)
- "Build your own Player Card" (viral/share)

---

## Technical Requirements

- **Stack:** Next.js 15 (App Router) + React 19 + Tailwind CSS v4 + GSAP 3 (with ScrollTrigger) + Lucide React for icons.
- **Fonts:** Use existing `--font-sora` and `--font-fraunces` CSS variables. Do NOT import new fonts via Google Fonts or `next/font`. The project already has these configured.
- **File structure:** Pages live in `frontend/src/app/`. Components in `frontend/src/components/`. Styles in `frontend/src/app/globals.css`.
- **CSS variables:** Use the project's existing CSS custom property system (`:root` in `globals.css`). Update values to Desert Diamond palette — do not create parallel token systems.
- **Images:** Use real Unsplash URLs for any texture/background images. Match warm, earthy, athletic mood: red clay, warm light, baseball diamond dirt, golden hour. Never use placeholder URLs.
- **No placeholders.** Every card, label, animation, and copy block must be fully implemented.
- **Responsive:** Mobile-first. Stack cards vertically on mobile. Reduce hero font sizes. Collapse navbar into minimal version.
- **Existing patterns:** Use `FadeOnScroll` component for scroll animations where already available. Use `.glass` utility class. Use `.display-font` for serif headlines.
- **Auth-awareness:** Landing page should detect auth state and adjust nav accordingly (the existing `page.tsx` already does this — preserve the pattern).

---

## Build Sequence

When asked to build or rebuild the landing page:

1. Update `globals.css` `:root` variables to Desert Diamond palette values.
2. Update `.glass` utility to warm-toned variant.
3. Build/rebuild `frontend/src/app/page.tsx` following the component architecture above (A through I).
4. Ensure every animation is wired, every interaction works, every copy block uses the Marketing Copy Bank.
5. Verify zero navy/blue color references remain. All colors must be Desert Diamond.
6. Test responsive behavior at mobile, tablet, and desktop breakpoints.

**Execution Directive:** "Do not build a website; build a digital instrument. Every scroll should feel intentional, every animation should feel weighted and professional. Eradicate all generic AI patterns."
