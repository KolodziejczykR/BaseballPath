# Feature Spec: Interactive Player Card

## Overview

The Interactive Player Card is a shareable, Topps-style baseball card with holographic effects that players can customize, download, and share on social media with trackable links back to their BaseballPATH profile. Each user gets one auto-updating card that reflects their latest evaluation data.

## User Stories

1. **As a player**, I want to create a baseball card from my evaluation data so I can showcase my stats and prediction level visually.
2. **As a player**, I want to share my card on Instagram/Twitter with a unique link so coaches and friends can view my full profile.
3. **As a player**, I want to see how many people clicked my shared links so I know my card is getting views.
4. **As a player**, I want my card to auto-update when I run a new evaluation so it always shows my latest stats.
5. **As a coach or viewer**, I want to view a player's public card without logging in so I can quickly assess their profile.

## Access Control

- **Pro and Elite tiers**: Full access to create, customize, share, and download cards.
- **Starter tier**: See a locked/blurred preview of what a card would look like, with an upgrade CTA.
- **Public viewers**: Can view any card via share link without authentication.

## Card Design: One Card Per User

- Each user has at most **one active card** (enforced via `UNIQUE` constraint on `user_id`).
- Card creation is an upsert: if a card already exists, it updates rather than creating a second.
- The card auto-updates when the user runs a new evaluation or refreshes manually.
- No multi-card management, card selection, or card versioning needed.

## Card Content

### Front Face (Top to Bottom)
- **Holographic border**: 4px rainbow gradient border frame (CSS `conic-gradient`)
- **Player photo**: Hero image fills top ~60% of card
- **Position badge**: Rounded pill in top-left (e.g., "SS" in navy)
- **Class year**: Top-right corner (e.g., "'27")
- **Name bar**: Dark overlay at bottom of photo area with player name in white
- **Stats grid**: Bottom ~40%, 2-column layout
  - **Pitcher**: FB Velo, FB Max, FB Spin, CH Velo, CB Velo, SL Velo
  - **Hitter (Infielder)**: Exit Velo, Throw Velo (inf_velo), 60 Time, Height, Weight
  - **Hitter (Outfielder)**: Exit Velo, Throw Velo (of_velo), 60 Time, Height, Weight
  - **Hitter (Catcher)**: Exit Velo, Throw Velo (c_velo), Pop Time, 60 Time, Height, Weight
- **BaseballPATH watermark**: Small "BP" logo at card bottom edge

### Back Face (Top to Bottom)
- **Prediction badge**: Large centered badge ("D1 PROSPECT", "POWER 4 D1", or "NON-D1")
- **D1 probability gauge**: Horizontal bar showing D1 probability percentage
- **P4 probability gauge** (if applicable): Secondary horizontal bar
- **Video links section**: Icons + labels for YouTube/Hudl links
- **Selected preferences**: Compact list of visible preferences (e.g., "Region: Northeast")
- **"View Full Profile" button**: Links to their latest BP evaluation page
- **QR code**: Small QR linking to the card's public share URL (`/p/{slug}`)

### Holographic Effect (CSS)
- `conic-gradient` with HSL rainbow colors as `::after` pseudo-element
- `mix-blend-mode: color-dodge` at ~0.5 opacity
- `onMouseMove` updates `--holo-x` and `--holo-y` CSS custom properties for parallax shift
- Card tilts slightly with `rotateX`/`rotateY` transforms tracking mouse position
- `prefers-reduced-motion` media query disables all animations

### Color Integration
- Card background: navy (`#18365a`)
- Stats text: white on navy
- Positive indicators: primary green (`#0f8d63`)
- Attention/highlights: accent orange (`#ef6f2e`)
- Secondary text: sand (`#ece1c5`)

## Card Dimensions
- Display ratio: ~350x490px (portrait, similar to real trading cards)
- Export: 1080x1512px for Instagram Stories, 1200x675px for Twitter/landscape

## Database Schema

### Table: `player_cards`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | `gen_random_uuid()` |
| user_id | UUID UNIQUE FK → profiles(id) | One card per user, CASCADE delete |
| latest_evaluation_run_id | UUID FK → prediction_runs(id) | SET NULL on delete |
| display_name | TEXT NOT NULL | Player's display name on card |
| high_school_name | TEXT | Optional |
| class_year | INT | Graduation year |
| primary_position | TEXT | e.g., "SS", "OF", "RHP" |
| state | TEXT | Player's state |
| stats_snapshot | JSONB NOT NULL | Position-specific stats, refreshed on new eval |
| prediction_level | TEXT | "Power 4 D1", "Non-P4 D1", "Non-D1" |
| d1_probability | FLOAT | |
| p4_probability | FLOAT | Null if not D1 |
| photo_storage_path | TEXT | Supabase Storage path |
| video_links | JSONB DEFAULT '[]' | `[{url, label, platform}]` |
| bp_profile_link | TEXT | Link to latest evaluation page |
| visible_preferences | JSONB DEFAULT '{}' | `{region: true, budget: false, ...}` |
| preferences_snapshot | JSONB DEFAULT '{}' | Actual preference values |
| card_theme | TEXT DEFAULT 'classic' | Future: "classic", "holographic", "dark" |
| is_active | BOOLEAN DEFAULT true | Soft delete flag |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated via trigger |

### Table: `card_share_links`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| card_id | UUID FK → player_cards(id) | CASCADE delete |
| user_id | UUID FK → profiles(id) | CASCADE delete |
| slug | TEXT UNIQUE NOT NULL | nanoid 10-char, e.g., "bp_Xk9mQ2vR" |
| platform | TEXT | "instagram", "twitter", "general" |
| label | TEXT | User-provided label for tracking |
| is_active | BOOLEAN DEFAULT true | |
| expires_at | TIMESTAMPTZ | Optional expiration |
| created_at | TIMESTAMPTZ | |

### Table: `card_link_clicks`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| share_link_id | UUID FK → card_share_links(id) | CASCADE delete |
| card_id | UUID NOT NULL | Denormalized for query perf |
| user_id | UUID NOT NULL | Card owner, denormalized |
| clicked_at | TIMESTAMPTZ | |
| referrer | TEXT | HTTP Referer header |
| user_agent | TEXT | |
| ip_hash | TEXT | SHA-256 hashed, never raw |
| platform_detected | TEXT | Parsed from referrer/UA |
| is_unique | BOOLEAN DEFAULT true | |

### Profile Alterations
```sql
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS high_school_name TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS video_links JSONB DEFAULT '[]'::jsonb;
```

### Supabase Storage
- Bucket: `player-photos`
- Max file size: 5MB
- Allowed MIME types: image/jpeg, image/png, image/webp

### RLS Policies
- Users can SELECT/INSERT/UPDATE/DELETE only their own `player_cards` rows
- Users can SELECT/INSERT/DELETE only their own `card_share_links` rows
- `card_link_clicks` INSERT via service role only (backend records clicks)
- `card_link_clicks` SELECT only by card owner (`auth.uid() = user_id`)

## API Endpoints

### Authenticated Card Management (`/cards`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/cards` | Create or upsert the user's card |
| GET | `/cards/me` | Get the user's card + analytics summary |
| PATCH | `/cards/me` | Update card fields |
| DELETE | `/cards/me` | Soft-delete (set `is_active = false`) |
| POST | `/cards/me/photo` | Upload photo (multipart/form-data) |
| POST | `/cards/me/share` | Generate a new share link with slug |
| GET | `/cards/me/analytics` | Click analytics (total, unique, by platform, by date) |
| POST | `/cards/me/refresh` | Refresh card from latest evaluation run |

### Public Card Access (`/p`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/p/{slug}` | No | Record click + redirect to public card page |
| GET | `/p/{slug}/data` | No | Return card data (visible prefs only) for rendering |
| GET | `/p/{slug}/og-image` | No | Return OG image for social preview |

## Photo Upload Flow

1. Client sends `multipart/form-data` to `POST /cards/me/photo`
2. Backend validates MIME type (jpeg/png/webp) and file size (≤5MB) server-side
3. Strip EXIF metadata using `Pillow`
4. Upload to Supabase Storage at `player-photos/{user_id}/{card_id}.{ext}`
5. Store path in `player_cards.photo_storage_path`
6. Generate signed URL for frontend rendering

## Share Link System

### Slug Generation
- Library: Python `nanoid` (10 chars, URL-safe alphabet)
- Full URL format: `https://baseballpath.com/p/{slug}`
- Prefix convention: `bp_` + 7 random chars (or just 10 random chars)

### Platform Detection
- From HTTP `Referer` header:
  - `t.co` → twitter
  - `l.instagram.com` → instagram
  - `lm.facebook.com` → facebook
- Falls back to "general" if unrecognizable

### Click Tracking
- Every `GET /p/{slug}` records a click row
- IP is SHA-256 hashed with a server-side salt (never stored raw)
- `is_unique` is determined by checking if the same `ip_hash + share_link_id` combo exists within 24h
- Rate limit: 100 clicks/IP/minute per link

## Image Export

### Client-Side (User Download)
- Library: `html-to-image` (npm)
- Renders the card DOM to PNG at 3x resolution
- Sizes: 1080x1512px (portrait/Instagram), 1200x675px (landscape/Twitter)
- Holographic effect captured as static gradient (no animation)
- Includes BaseballPATH watermark

### Server-Side (OG Images)
- Generated when a share link is created
- Uses Python `Pillow` for template-based composition:
  - Navy background template
  - Player photo overlay
  - Text overlays (name, position, stats, prediction)
- Stored in Supabase Storage at `og-images/{card_id}/{slug}.png`
- Served via `GET /p/{slug}/og-image`
- Dimensions: 1200x630px (Open Graph standard)

## Frontend Pages

### `/card` — Player Card Page (Authenticated)
- **No card yet**: Creation wizard
  - Step 1: Select evaluation to base card on
  - Step 2: Upload photo, set display name, high school
  - Step 3: Add video links (YouTube/Hudl)
  - Step 4: Toggle preference visibility
  - Step 5: Preview front/back with live flip → Confirm
- **Has card**: Single-page management view
  - Full-size card preview with flip animation
  - Edit panel for video links, preferences visibility, photo
  - "Refresh from Latest Evaluation" button
  - Share panel: generate links per platform, copy-to-clipboard
  - Analytics panel: click counts, platform breakdown
  - Download button: export as PNG
- **Starter tier**: Blurred card preview + upgrade CTA

### `/p/[slug]` — Public Profile (No Auth)
- Server-side fetch via `GET /p/{slug}/data`
- Renders the player card (front view, tap/click to flip)
- Open Graph metadata via `generateMetadata()`:
  - Title: `"{Player Name} - {Position} | BaseballPath"`
  - Image: OG image URL
  - Twitter card: `summary_large_image`
- CTA below card: "Build your own Player Card on BaseballPath — Free to start"

## Frontend Components

| Component | File | Purpose |
|-----------|------|---------|
| PlayerCardFront | `player-card-front.tsx` | Front face rendering |
| PlayerCardBack | `player-card-back.tsx` | Back face rendering |
| PlayerCardContainer | `player-card-container.tsx` | 3D flip wrapper (CSS perspective + backface-visibility) |
| HolographicEffect | `holographic-effect.tsx` | Mouse-tracking rainbow gradient overlay |
| CardStatRow | `card-stat-row.tsx` | Individual stat display with position-aware formatting |
| PreferenceVisibilityToggles | `preference-visibility-toggles.tsx` | Toggle switches for each pref field |
| CardExportButton | `card-export-button.tsx` | Captures card to PNG via `html-to-image` |
| ShareLinkGenerator | `share-link-generator.tsx` | Platform selector, link copy, existing links list |
| CardAnalyticsPanel | `card-analytics-panel.tsx` | Clicks chart, platform breakdown |
| PhotoUpload | `photo-upload.tsx` | Drag-and-drop with client-side crop/preview |

## Security Considerations

1. **Photo uploads**: Validate MIME server-side (not just extension), strip EXIF, enforce 5MB limit
2. **Public card data**: Server-side filter — NEVER return hidden preferences via `/p/{slug}/data`
3. **IP hashing**: SHA-256 with server-side salt for click dedup (never store raw IPs)
4. **Rate limiting**: 100 clicks/IP/minute per link to prevent abuse
5. **Slugs**: Cryptographically random (nanoid) — prevents sequential enumeration
6. **CORS**: Public routes configured for no-auth access from any origin
7. **Storage**: Signed URLs for photo access (not public bucket URLs)

## Nav Integration

Add to `navItems` array in `frontend/src/components/ui/authenticated-topbar.tsx`:
```typescript
{ href: "/card", label: "Player Card" },
```

Add "Create Player Card" or "Share Your Card" CTA to dashboard page.
