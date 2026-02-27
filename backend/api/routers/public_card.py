"""
Public player-card endpoints.
"""

from __future__ import annotations

import hashlib
import io
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from PIL import Image, ImageDraw, ImageFont

from ..clients.supabase import require_supabase_admin_client
from utils.storage import signed_photo_url

router = APIRouter()
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
CARD_CLICK_SALT = os.getenv("CARD_CLICK_SALT", "baseballpath-card-click-salt")


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            return None
    return None


def _active_share_and_card(slug: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    supabase = require_supabase_admin_client()
    share_response = (
        supabase.table("card_share_links")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not share_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")

    share = share_response.data[0]
    expires_at = _parse_datetime(share.get("expires_at"))
    if expires_at and expires_at <= datetime.now(tz=UTC):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link expired")

    card_response = (
        supabase.table("player_cards")
        .select("*")
        .eq("id", share.get("card_id"))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not card_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card unavailable")

    return share, card_response.data[0]


def _visible_preferences(card: Dict[str, Any]) -> Dict[str, Any]:
    visibility = _as_dict(card.get("visible_preferences"))
    snapshot = _as_dict(card.get("preferences_snapshot"))
    visible: Dict[str, Any] = {}
    for key, value in snapshot.items():
        if visibility.get(key, True):
            visible[key] = value
    return visible


def _public_card_payload(slug: str, card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": slug,
        "id": card.get("id"),
        "display_name": card.get("display_name"),
        "high_school_name": card.get("high_school_name"),
        "class_year": card.get("class_year"),
        "primary_position": card.get("primary_position"),
        "state": card.get("state"),
        "stats_snapshot": card.get("stats_snapshot") or {},
        "prediction_level": card.get("prediction_level"),
        "d1_probability": card.get("d1_probability"),
        "p4_probability": card.get("p4_probability"),
        "video_links": card.get("video_links") or [],
        "preferences": _visible_preferences(card),
        "photo_url": signed_photo_url(card.get("photo_storage_path")),
        "bp_profile_link": card.get("bp_profile_link"),
    }


def _hash_ip(ip_address: str) -> str:
    return hashlib.sha256(f"{ip_address}{CARD_CLICK_SALT}".encode("utf-8")).hexdigest()


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _detect_platform(referer: str, user_agent: str) -> str:
    source = f"{referer} {user_agent}".lower()
    if "t.co" in source or "twitter" in source or "x.com" in source:
        return "twitter"
    if "l.instagram.com" in source or "instagram" in source:
        return "instagram"
    if "lm.facebook.com" in source or "facebook" in source:
        return "facebook"
    if "linkedin" in source:
        return "linkedin"
    return "general"


def _enforce_click_rate_limit(share_link_id: str, ip_hash: str) -> None:
    supabase = require_supabase_admin_client()
    one_minute_ago = (datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat()
    response = (
        supabase.table("card_link_clicks")
        .select("id", count="exact")
        .eq("share_link_id", share_link_id)
        .eq("ip_hash", ip_hash)
        .gte("clicked_at", one_minute_ago)
        .execute()
    )
    count = getattr(response, "count", None) or len(response.data or [])
    if count >= 100:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")


def _is_unique_click(share_link_id: str, ip_hash: str) -> bool:
    supabase = require_supabase_admin_client()
    day_ago = (datetime.now(tz=UTC) - timedelta(hours=24)).isoformat()
    response = (
        supabase.table("card_link_clicks")
        .select("id")
        .eq("share_link_id", share_link_id)
        .eq("ip_hash", ip_hash)
        .gte("clicked_at", day_ago)
        .limit(1)
        .execute()
    )
    return not bool(response.data)


def _record_click(slug: str, request: Request) -> None:
    """Shared click-recording logic used by both the redirect and POST endpoints."""
    share_link, card = _active_share_and_card(slug)

    referer = request.headers.get("referer", "")
    user_agent = request.headers.get("user-agent", "")
    platform = _detect_platform(referer, user_agent)
    ip_hash = _hash_ip(_extract_client_ip(request))

    _enforce_click_rate_limit(str(share_link.get("id")), ip_hash)
    unique = _is_unique_click(str(share_link.get("id")), ip_hash)

    supabase = require_supabase_admin_client()
    supabase.table("card_link_clicks").insert(
        {
            "share_link_id": share_link.get("id"),
            "card_id": card.get("id"),
            "user_id": share_link.get("user_id"),
            "referrer": referer or None,
            "user_agent": user_agent or None,
            "ip_hash": ip_hash,
            "platform_detected": platform,
            "is_unique": unique,
        }
    ).execute()


@router.post("/{slug}/click")
async def record_click(slug: str, request: Request) -> Dict[str, Any]:
    """Called by the frontend public card page to record a view/click."""
    _record_click(slug, request)
    return {"ok": True}


@router.get("/{slug}")
async def redirect_share_link(slug: str, request: Request) -> RedirectResponse:
    """Fallback redirect for direct backend URL visits. Also records a click."""
    _record_click(slug, request)
    redirect_url = f"{PUBLIC_APP_URL.rstrip('/')}/p/{slug}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/{slug}/data")
async def get_public_card_data(slug: str) -> Dict[str, Any]:
    _, card = _active_share_and_card(slug)
    return _public_card_payload(slug, card)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a TrueType font at the given size, falling back gracefully."""
    # Try common system font paths (Linux, macOS)
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Pillow 10.1+ supports sized default font
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _generate_og_image(card: Dict[str, Any]) -> bytes:
    width, height = 1200, 630
    navy = "#18365a"
    sand = "#ece1c5"
    primary = "#0f8d63"
    accent = "#ef6f2e"
    white = "#ffffff"

    canvas = Image.new("RGB", (width, height), navy)
    draw = ImageDraw.Draw(canvas)

    # Accent stripe at top
    draw.rectangle([(0, 0), (width, 8)], fill=primary)
    # Bottom bar
    draw.rectangle([(0, height - 60), (width, height)], fill="#0f1823")

    font_lg = _load_font(48)
    font_md = _load_font(30)
    font_sm = _load_font(22)
    font_brand = _load_font(26)

    display_name = str(card.get("display_name") or "BaseballPath Player")
    position = str(card.get("primary_position") or "Player")
    prediction_level = str(card.get("prediction_level") or "Prospect")
    class_year = card.get("class_year")
    d1_probability = card.get("d1_probability")
    p4_probability = card.get("p4_probability")

    # Position badge (pill shape)
    badge_x, badge_y = 72, 40
    badge_w = max(80, len(position) * 22 + 30)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + 44)],
        radius=22,
        fill=primary,
    )
    draw.text((badge_x + badge_w // 2, badge_y + 22), position, fill=white, font=font_sm, anchor="mm")

    # Class year
    if class_year:
        year_text = f"'{str(class_year)[-2:]}"
        draw.text((width - 80, badge_y + 22), year_text, fill=sand, font=font_md, anchor="mm")

    # Player name
    draw.text((72, 120), display_name, fill=white, font=font_lg)

    # Prediction level
    draw.text((72, 190), prediction_level, fill=sand, font=font_md)

    # Probability bars
    bar_y = 260
    if d1_probability is not None:
        try:
            prob = float(d1_probability)
            label = f"D1 Probability: {prob * 100:.1f}%"
            draw.text((72, bar_y), label, fill=white, font=font_sm)
            bar_y += 34
            # Draw progress bar
            bar_bg = [(72, bar_y), (72 + 500, bar_y + 20)]
            draw.rounded_rectangle(bar_bg, radius=10, fill="#2a4a6e")
            bar_fill_w = max(10, int(500 * min(prob, 1.0)))
            draw.rounded_rectangle([(72, bar_y), (72 + bar_fill_w, bar_y + 20)], radius=10, fill=primary)
            bar_y += 44
        except (ValueError, TypeError):
            pass

    if p4_probability is not None:
        try:
            prob = float(p4_probability)
            label = f"P4 Probability: {prob * 100:.1f}%"
            draw.text((72, bar_y), label, fill=white, font=font_sm)
            bar_y += 34
            bar_bg = [(72, bar_y), (72 + 500, bar_y + 20)]
            draw.rounded_rectangle(bar_bg, radius=10, fill="#2a4a6e")
            bar_fill_w = max(10, int(500 * min(prob, 1.0)))
            draw.rounded_rectangle([(72, bar_y), (72 + bar_fill_w, bar_y + 20)], radius=10, fill=accent)
            bar_y += 44
        except (ValueError, TypeError):
            pass

    # Stats preview (right column)
    stats = card.get("stats_snapshot") or {}
    stat_x = 700
    stat_y = 120
    stat_keys = [
        ("Exit Velo", "exit_velo_max", "mph"),
        ("FB Max", "fastball_velo_max", "mph"),
        ("60 Time", "sixty_time", "sec"),
        ("Pop Time", "pop_time", "sec"),
    ]
    for label, key, unit in stat_keys:
        val = stats.get(key)
        if val is not None:
            try:
                draw.text((stat_x, stat_y), label, fill=sand, font=font_sm)
                draw.text((stat_x + 250, stat_y), f"{float(val)} {unit}", fill=white, font=font_sm)
                stat_y += 38
            except (ValueError, TypeError):
                continue

    # Brand bar at bottom
    draw.text((72, height - 42), "BaseballPATH", fill=accent, font=font_brand)
    draw.text((width - 72, height - 42), "baseballpath.com", fill=sand, font=font_sm, anchor="ra")

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

@router.get("/{slug}/og-image")
async def get_og_image(slug: str) -> Response:
    _, card = _active_share_and_card(slug)
    image_bytes = _generate_og_image(card)
    return Response(content=image_bytes, media_type="image/png")
