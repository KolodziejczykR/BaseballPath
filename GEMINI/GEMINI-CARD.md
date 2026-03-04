# BaseballPath — Player Card Component Builder

## Role

Act as a World-Class Senior Creative Technologist specializing in **collectible card UI**. You build Player Cards that feel like physical artifacts — tactile, weighted, and worth sharing. The card is the most viral piece of BaseballPath: it's what gets texted to coaches, posted on Instagram, and pinned to Twitter bios. Every pixel must earn its place.

---

## Design System Reference

This file extends the BaseballPath design system defined in `GEMINI.md`. All color tokens and typography from that file apply here.

---

## Visual Direction — "Hybrid Matte + Holo"

The BaseballPath Player Card uses a **warm matte base** with a **subtle holographic shimmer on hover**. This is NOT a flashy rainbow card — it's a premium, confident artifact that catches light when you interact with it.

### Matte Base

- **Background:** Deep walnut-to-espresso gradient — `linear-gradient(145deg, #3B2718 0%, #2C1810 100%)`
- **NOT navy.** Not blue. Not black. Warm, rich brown tones.
- **Text:** Warm cream `#F5EFE0` for primary text, `#E8DCC8` at reduced opacity for secondary
- **Accents:** Golden Sand `#D4A843` for highlights, badges, stat labels
- **Borders:** Copper `#B87333` subtle border or `rgba(184,115,51,0.3)` for softer edges

### Holographic Shimmer (Hover Only)

The holographic effect activates **only on mouse hover** (or touch-hold on mobile). At rest, the card is pure matte.

- Uses `conic-gradient` rotating with mouse position via CSS custom properties `--holo-angle`, `--holo-x`, `--holo-y`
- `mix-blend-mode: color-dodge` at `opacity: 0` (rest) → `opacity: 0.35` (hover)
- Transition: `opacity 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)`
- Color stops: warm-biased — golds, coppers, ambers, with subtle sage green flashes (NOT rainbow)

```css
.holo-effect {
  background: conic-gradient(
    from calc(var(--holo-angle, 0) * 1deg),
    hsl(35, 80%, 65%) 0deg,
    hsl(45, 75%, 60%) 60deg,
    hsl(25, 70%, 55%) 120deg,
    hsl(100, 30%, 55%) 180deg,
    hsl(30, 85%, 60%) 240deg,
    hsl(40, 80%, 65%) 300deg,
    hsl(35, 80%, 65%) 360deg
  );
  mix-blend-mode: color-dodge;
  opacity: 0;
  transition: opacity 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  pointer-events: none;
}

.card-container:hover .holo-effect {
  opacity: 0.35;
}
```

### 3D Tilt

Active at all times on desktop (mouse tracking), disabled on mobile:

- Container: `perspective: 1000px`
- Card inner: `transform: rotateX(var(--tilt-x)) rotateY(var(--tilt-y))` — max ±10deg
- `transition: transform 0.15s ease-out` for smooth tracking
- On mouse leave: animate back to `rotateX(0) rotateY(0)` with `power2.out` easing

---

## Card Dimensions & Structure

### Fixed Size
- **Width:** 350px
- **Height:** 490px
- **Aspect ratio:** ~5:7 (standard trading card proportions)
- **Border radius:** `rounded-2xl` (1rem)

### Two-Face Structure

The card has a **front** and **back**, connected by a 3D flip animation.

```
[perspective: 1000px]
└── Card Inner (preserve-3d, transition: rotateY)
    ├── Card Front (backface-visibility: hidden)
    └── Card Back (backface-visibility: hidden, rotateY: 180deg)
```

**Flip trigger:** Click anywhere on the card. `rotateY(0deg)` ↔ `rotateY(180deg)` with `0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)`.

---

## Card Front Layout

The front is the "at a glance" face — photo, name, position, key stats.

```
┌─────────────────────────────────────┐
│  [Position Badge]    [Class Year]   │  ← Top bar (absolute, over photo)
│                                     │
│                                     │
│         PLAYER PHOTO                │  ← Top 60% of card
│         (or gradient placeholder)   │
│                                     │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← Bottom gradient overlay
│  PLAYER NAME                        │  ← Name over gradient
├─────────────────────────────────────┤
│                                     │
│  ┌──────────┐  ┌──────────┐        │  ← Bottom 40%: Stat pills
│  │ STAT  VAL│  │ STAT  VAL│        │     2-column grid
│  └──────────┘  └──────────┘        │     Up to 8 stats
│  ┌──────────┐  ┌──────────┐        │
│  │ STAT  VAL│  │ STAT  VAL│        │
│  └──────────┘  └──────────┘        │
│                                     │
│  ─── BaseballPath ───               │  ← Bottom branding
└─────────────────────────────────────┘
```

### Front — Detailed Specs

**Photo Area (top 60%):**
- If photo uploaded: `object-cover` filling the area, with bottom gradient overlay
- If no photo: Warm gradient placeholder — `linear-gradient(135deg, var(--walnut) 0%, var(--espresso) 100%)`
- Bottom gradient overlay: `linear-gradient(to top, var(--espresso) 0%, transparent 60%)` for name readability

**Position Badge (top-left):**
- `absolute top-3 left-3`
- `rounded-lg bg-[var(--golden-sand)] text-[var(--espresso)] px-2.5 py-1 text-xs font-bold uppercase tracking-wider`
- Shows primary position abbreviation (e.g., "RHP", "SS", "OF")

**Class Year (top-right):**
- `absolute top-3 right-3`
- `text-sm font-mono font-bold text-white/90`
- Format: `'YY` (e.g., `'26`)

**Player Name (over gradient):**
- `absolute bottom-[40%] left-4`
- `text-xl font-bold text-white tracking-wide`
- Optional: school/club name below in `text-xs text-white/70`

**Stat Pills (bottom 40%):**
- Container: `grid grid-cols-2 gap-2 p-3`
- Each pill: `rounded-lg border border-white/15 bg-white/8 px-3 py-2`
  - Label: `text-[10px] uppercase tracking-[0.14em] text-[var(--golden-sand)]/80`
  - Value: `text-sm font-semibold text-white`
- Up to 8 stats (4 rows × 2 columns)
- Stats are user-configurable — pulled from their evaluation data

**Branding Footer:**
- `text-[10px] uppercase tracking-[0.34em] text-[var(--golden-sand)]/50`
- Centered at bottom: "BaseballPath"

**Border Treatment:**
- Outer border: `border border-[var(--copper)]/25`
- Optional: Subtle inset shadow `shadow-[inset_0_1px_0_rgba(212,168,67,0.1)]` for embossed feel

---

## Card Back Layout

The back is the "deep dive" face — projection, video links, preferences, share URL.

```
┌─────────────────────────────────────┐
│                                     │
│  PROJECTION                         │  ← Division prediction section
│  ┌─────────────────────────────┐    │
│  │ D1  ████████░░  62%         │    │     Probability bar(s)
│  │ Power4  ██████░░░░  45%     │    │
│  └─────────────────────────────┘    │
│                                     │
│  VIDEO LINKS                        │  ← Up to 3 video URLs
│  ▸ Pitching highlights              │
│  ▸ Game film — Fall 2025            │
│  ▸ Batting practice                 │
│                                     │
│  PREFERENCES                        │  ← Visible recruiting prefs
│  Region: West Coast                 │     Up to 5 key:value pairs
│  Size: Medium (5K-15K)              │
│  Setting: Suburban                  │
│                                     │
│  ─────────────────────────────────  │
│  baseballpath.com/p/jsmith26        │  ← Share URL
│                                     │
│  ─── BaseballPath ───               │  ← Bottom branding
└─────────────────────────────────────┘
```

### Back — Detailed Specs

**Background:** Darker than front — `bg-[#1A0F08]` (deep espresso-black) or `linear-gradient(180deg, #2C1810 0%, #1A0F08 100%)`

**Projection Section:**
- Label: `text-xs uppercase tracking-[0.2em] text-[var(--golden-sand)] mb-3` — "Projection"
- Each division prediction:
  - Division label: `text-sm font-semibold text-white`
  - Probability bar: `rounded-full h-2.5 bg-white/10` track, fill colored by probability:
    - ≥ 60%: `bg-[var(--sage-green)]`
    - 30–59%: `bg-[var(--golden-sand)]`
    - < 30%: `bg-[var(--burnt-sienna)]`
  - Percentage: `text-sm font-mono font-bold text-white` right-aligned
- Show D1 always. Show secondary division (Power 4, D2, D3) if available.

**Video Links:**
- Label: `text-xs uppercase tracking-[0.2em] text-[var(--golden-sand)] mb-2` — "Film"
- Each link: `text-sm text-white/80 hover:text-white` with play triangle icon
- Up to 3 links. Truncate long titles with ellipsis.
- On the static/export version, show as text. On the live card, these are clickable.

**Preferences:**
- Label: `text-xs uppercase tracking-[0.2em] text-[var(--golden-sand)] mb-2` — "Preferences"
- Each pref: `text-xs text-white/70` — "Key: Value" format
- Up to 5 visible preferences (controlled by toggle switches on the /card page)

**Share URL:**
- Divider line: `border-t border-white/10`
- URL: `text-xs font-mono text-white/50 text-center mt-2`
- Format: `baseballpath.com/p/{slug}`

**Branding Footer:**
- Same as front: `text-[10px] uppercase tracking-[0.34em] text-[var(--golden-sand)]/50` centered

---

## Holographic Effect Implementation

### CSS Custom Properties

The card container tracks mouse position and injects these CSS custom properties:

```typescript
const handleMouseMove = (e: React.MouseEvent) => {
  const rect = e.currentTarget.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;   // 0 to 1
  const y = (e.clientY - rect.top) / rect.height;    // 0 to 1
  const angle = Math.atan2(y - 0.5, x - 0.5) * (180 / Math.PI) + 180;

  e.currentTarget.style.setProperty('--holo-x', `${x * 100}%`);
  e.currentTarget.style.setProperty('--holo-y', `${y * 100}%`);
  e.currentTarget.style.setProperty('--holo-angle', `${angle}`);

  // 3D tilt
  const tiltX = (y - 0.5) * -20; // ±10deg
  const tiltY = (x - 0.5) * 20;  // ±10deg
  e.currentTarget.style.setProperty('--tilt-x', `${tiltX}deg`);
  e.currentTarget.style.setProperty('--tilt-y', `${tiltY}deg`);
};
```

### Holographic Layer

An absolutely positioned div inside each card face, above all content:

```tsx
<div
  className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-400 group-hover:opacity-35"
  style={{
    background: `conic-gradient(
      from calc(var(--holo-angle, 0) * 1deg) at var(--holo-x, 50%) var(--holo-y, 50%),
      hsl(35, 80%, 65%) 0deg,
      hsl(45, 75%, 60%) 60deg,
      hsl(25, 70%, 55%) 120deg,
      hsl(100, 30%, 55%) 180deg,
      hsl(30, 85%, 60%) 240deg,
      hsl(40, 80%, 65%) 300deg,
      hsl(35, 80%, 65%) 360deg
    )`,
    mixBlendMode: 'color-dodge',
  }}
/>
```

**Key details:**
- Warm-biased color stops: golds, coppers, ambers, with a single sage green pass at 180deg
- `color-dodge` blend mode creates the light-catching effect against the dark matte base
- Only visible on hover via `opacity-0 group-hover:opacity-35` (add `group` class to container)
- `pointer-events-none` so it doesn't block clicks on the card

---

## Export Specifications

### Image Export (via `html-to-image` / `toPng`)

The card can be exported as a static PNG for sharing on social media.

**Instagram Story format:**
- Output: 1080 × 1512px PNG
- Scale factor: ~3.1x from 350×490 base
- Background: `#2C1810` (espresso) bleed behind card
- Card centered with equal padding

**Twitter/X Post format:**
- Output: 1200 × 675px PNG
- Card rendered at ~60% height, vertically centered
- Background: `#2C1810` with subtle radial gradient warmth
- Optional: BaseballPath watermark in bottom-right corner (`text-[10px] text-white/20`)

**Export behavior:**
- Holographic effect is **OFF** in exports (static matte only)
- 3D tilt is **OFF** in exports (flat orientation)
- All text renders at high resolution (scale factor ensures crisp type)

### OG Image Generation

For social media link previews when sharing `/p/[slug]` URLs:

- **Dimensions:** 1200 × 630px (standard OG image)
- **Layout:** Card front rendered at ~70% height on left, player name + division + "View on BaseballPath" text on right
- **Background:** Deep espresso with warm radial gradient
- **Format:** PNG, generated server-side or via edge function
- **Meta tags:** Set `og:image`, `og:title` (player name + position), `og:description` ("View {name}'s recruiting projection on BaseballPath")

---

## Public Card Page (`/p/[slug]`)

When a shared card link is opened:

**Layout:**
- Full viewport height, centered
- Background: `bg-[#1A0F08]` (deep espresso-black) with warm radial gradient:
  ```css
  background:
    radial-gradient(600px 400px at 50% 40%, rgba(160,82,45,0.15) 0%, transparent 70%),
    #1A0F08;
  ```
- Card: `PlayerCardContainer` centered, interactive (tilt + holo + flip all active)
- Below card: "Build your own Player Card on BaseballPath" CTA
  - `rounded-full bg-[var(--burnt-sienna)] text-white px-6 py-3 mt-8`
- Bottom: BaseballPath wordmark in `text-[var(--golden-sand)]/30`

**Click tracking:** Fire-and-forget `POST /p/{slug}/click` on page load with platform detection.

---

## Component File Map

All player card components live in `frontend/src/components/player-card/`:

| File | Purpose |
|---|---|
| `player-card-container.tsx` | Root wrapper — 3D tilt, flip, CSS variable injection |
| `player-card-front.tsx` | Front face — photo, name, position, stat pills |
| `player-card-back.tsx` | Back face — projection, videos, preferences, URL |
| `holographic-effect.tsx` | Holo overlay layer (conic-gradient + blend mode) |
| `card-stat-row.tsx` | Individual stat pill on the front |
| `card-analytics-panel.tsx` | Click analytics (used on /card page, not on card itself) |
| `card-export-button.tsx` | PNG export buttons (Instagram + Twitter formats) |
| `photo-upload.tsx` | Drag-and-drop photo upload |
| `preference-visibility-toggles.tsx` | iOS-style toggles for showing/hiding prefs |
| `share-link-generator.tsx` | Platform-specific share link creation |
| `public-card-client.tsx` | Client component for `/p/[slug]` public page |

---

## Build Guidance

When building or modifying the Player Card:

1. **Read all existing component files first** — preserve working 3D flip, tilt, and export logic.
2. **Update color scheme** — replace all `#18365a` (navy) references with `#3B2718` (walnut). Replace `#10233d` with `#1A0F08` (deep espresso). Replace `#ece1c5` with `#D4A843` (golden sand).
3. **Update holographic effect** — replace rainbow conic-gradient with warm-biased version (golds, coppers, ambers, sage green).
4. **Border treatment** — replace rainbow `conic-gradient` border with copper/gold subtle border: `border border-[#B87333]/25`.
5. **Stat pill styling** — update to warm palette: golden sand labels, white values, `bg-white/8` backgrounds.
6. **Test 3D tilt** — ensure `--tilt-x`, `--tilt-y` variables still drive `rotateX`/`rotateY` correctly.
7. **Test export** — ensure `toPng` still produces clean output at Instagram (1080×1512) and Twitter (1200×675) dimensions.
8. **Test public page** — ensure `/p/[slug]` renders correctly with warm dark background and CTA.

**Color Replacement Cheat Sheet:**
| Old (Navy/Blue) | New (Desert Diamond) |
|---|---|
| `#18365a` | `#3B2718` (Walnut) |
| `#10233d` | `#1A0F08` (Deep Espresso) |
| `#ece1c5` | `#D4A843` (Golden Sand) |
| `rgba(236,225,197,*)` | `rgba(212,168,67,*)` (Golden Sand rgba) |
| Any `hsl(0..360, 80%, 70%)` rainbow | Warm-biased hsl stops (see holo section) |

**Execution Directive:** "This card gets screenshotted, texted, posted, and pinned. It must look as good in a coach's iMessage preview as it does full-screen on a 4K monitor. Build it like a physical object that catches light."
