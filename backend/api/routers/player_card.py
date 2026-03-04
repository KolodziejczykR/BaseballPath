"""
Authenticated player-card management endpoints.
"""

from __future__ import annotations

import io
import os
import secrets
import string
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.plan_service import get_profile
from utils.storage import signed_photo_url

router = APIRouter()

PHOTO_MAX_BYTES = 5 * 1024 * 1024
PHOTO_TYPES: Dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
DEFAULT_PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "https://baseballpath.com")

try:
    from nanoid import generate as nanoid_generate
except Exception:  # pragma: no cover - fallback when optional dependency is missing
    _ALPHABET = string.ascii_letters + string.digits

    def nanoid_generate(size: int = 21) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(size))


class CardCreateRequest(BaseModel):
    evaluation_run_id: str
    display_name: str = Field(min_length=1, max_length=120)
    high_school_name: Optional[str] = Field(default=None, max_length=200)
    class_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    video_links: Optional[List[Dict[str, str]]] = None
    visible_preferences: Optional[Dict[str, bool]] = None


class CardUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    high_school_name: Optional[str] = Field(default=None, max_length=200)
    class_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    video_links: Optional[List[Dict[str, str]]] = None
    visible_preferences: Optional[Dict[str, bool]] = None
    card_theme: Optional[str] = Field(default=None, max_length=60)


class ShareLinkRequest(BaseModel):
    platform: Optional[str] = Field(default=None, max_length=40)
    label: Optional[str] = Field(default=None, max_length=120)


def _first_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_video_links(video_links: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    if not video_links:
        return []

    normalized: List[Dict[str, str]] = []
    for link in video_links:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url", "")).strip()
        if not url:
            continue
        normalized.append(
            {
                "url": url,
                "label": str(link.get("label", "")).strip() or "Video",
                "platform": str(link.get("platform", "")).strip() or "general",
            }
        )
    return normalized


def _normalize_visible_preferences(preferences: Optional[Dict[str, Any]], source: Dict[str, Any]) -> Dict[str, bool]:
    if preferences:
        return {str(key): bool(value) for key, value in preferences.items()}
    if source:
        return {str(key): True for key in source.keys()}
    return {}


def _extract_prediction_fields(run: Dict[str, Any]) -> Dict[str, Any]:
    prediction = _first_dict(run.get("prediction_response"))
    d1_details = _first_dict(prediction.get("d1_details"))
    p4_details = _first_dict(prediction.get("p4_details"))

    d1_probability = prediction.get("d1_probability")
    if d1_probability is None:
        d1_probability = d1_details.get("probability")

    p4_probability = prediction.get("p4_probability")
    if p4_probability is None:
        p4_probability = p4_details.get("probability")

    return {
        "prediction_level": prediction.get("final_prediction"),
        "d1_probability": d1_probability,
        "p4_probability": p4_probability,
    }


def _extract_primary_position(run: Dict[str, Any]) -> Optional[str]:
    identity = _first_dict(run.get("identity_input"))
    value = identity.get("primary_position") or identity.get("primaryPosition")
    if value is None:
        return None
    return str(value).upper()


def _extract_bp_profile_link(run_id: str) -> str:
    return f"{DEFAULT_PUBLIC_APP_URL.rstrip('/')}/evaluations/{run_id}"


def _build_card_payload(
    *,
    user_id: str,
    run: Dict[str, Any],
    profile: Dict[str, Any],
    display_name: str,
    high_school_name: Optional[str],
    class_year: Optional[int],
    video_links: Optional[List[Dict[str, Any]]],
    visible_preferences: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    stats_snapshot = _first_dict(run.get("stats_input"))
    preferences_snapshot = _first_dict(run.get("preferences_input"))
    prediction_fields = _extract_prediction_fields(run)
    run_id = str(run.get("id"))

    return {
        "user_id": user_id,
        "latest_evaluation_run_id": run_id,
        "display_name": display_name,
        "high_school_name": high_school_name if high_school_name is not None else profile.get("high_school_name"),
        "class_year": class_year,
        "primary_position": _extract_primary_position(run),
        "state": profile.get("state"),
        "stats_snapshot": stats_snapshot,
        "prediction_level": prediction_fields.get("prediction_level"),
        "d1_probability": prediction_fields.get("d1_probability"),
        "p4_probability": prediction_fields.get("p4_probability"),
        "video_links": _normalize_video_links(video_links) if video_links is not None else _first_list(profile.get("video_links")),
        "bp_profile_link": _extract_bp_profile_link(run_id),
        "visible_preferences": _normalize_visible_preferences(visible_preferences, preferences_snapshot),
        "preferences_snapshot": preferences_snapshot,
        "is_active": True,
    }


def _get_my_card_row(user_id: str) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("player_cards")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player card not found")
    return response.data[0]


def _decorate_card(card: Dict[str, Any]) -> Dict[str, Any]:
    decorated = dict(card)
    decorated["photo_url"] = signed_photo_url(decorated.get("photo_storage_path"))
    return decorated


def _get_evaluation_for_user(run_id: str, user_id: str) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", run_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return response.data[0]


def _latest_evaluation_for_user(user_id: str) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evaluation runs found")
    return response.data[0]


@router.post("")
async def create_or_update_card(
    payload: CardCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    run = _get_evaluation_for_user(payload.evaluation_run_id, current_user.user_id)
    profile = get_profile(current_user.user_id, current_user.email)

    upsert_payload = _build_card_payload(
        user_id=current_user.user_id,
        run=run,
        profile=profile,
        display_name=payload.display_name.strip(),
        high_school_name=payload.high_school_name.strip() if payload.high_school_name else None,
        class_year=payload.class_year,
        video_links=payload.video_links,
        visible_preferences=payload.visible_preferences,
    )

    response = supabase.table("player_cards").upsert(upsert_payload, on_conflict="user_id").execute()
    if response.data:
        return _decorate_card(response.data[0])
    return _decorate_card(_get_my_card_row(current_user.user_id))


@router.get("/me")
async def get_my_card(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    card = _get_my_card_row(current_user.user_id)
    return _decorate_card(card)


@router.patch("/me")
async def update_my_card(
    payload: CardUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    card = _get_my_card_row(current_user.user_id)

    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if "display_name" in updates:
        updates["display_name"] = str(updates["display_name"]).strip()
    if "high_school_name" in updates and isinstance(updates["high_school_name"], str):
        updates["high_school_name"] = updates["high_school_name"].strip()
    if "video_links" in updates:
        updates["video_links"] = _normalize_video_links(updates.get("video_links"))
    if "visible_preferences" in updates:
        updates["visible_preferences"] = _normalize_visible_preferences(
            updates.get("visible_preferences"), _first_dict(card.get("preferences_snapshot"))
        )

    if updates:
        response = (
            supabase.table("player_cards")
            .update(updates)
            .eq("id", card.get("id"))
            .eq("user_id", current_user.user_id)
            .execute()
        )
        if response.data:
            return _decorate_card(response.data[0])

    return _decorate_card(_get_my_card_row(current_user.user_id))


@router.delete("/me")
async def delete_my_card(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    card = _get_my_card_row(current_user.user_id)
    response = (
        supabase.table("player_cards")
        .update({"is_active": False})
        .eq("id", card.get("id"))
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive card")
    return {"ok": True}


def _sanitize_image(raw_bytes: bytes, content_type: str) -> tuple[bytes, str]:
    file_format = PHOTO_TYPES.get(content_type)
    if not file_format:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            cleaned = image.convert("RGBA") if image.mode not in {"RGB", "RGBA"} else image.copy()

            if file_format == "JPEG":
                cleaned = cleaned.convert("RGB")

            output = io.BytesIO()
            save_kwargs: Dict[str, Any] = {"format": file_format}
            if file_format in {"JPEG", "WEBP"}:
                save_kwargs["quality"] = 92
            cleaned.save(output, **save_kwargs)
            return output.getvalue(), file_format.lower()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid image file: {exc}") from exc


@router.post("/me/photo")
async def upload_card_photo(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    card = _get_my_card_row(current_user.user_id)

    content_type = file.content_type or ""
    if content_type not in PHOTO_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, and WEBP are supported")

    file_bytes = await file.read()
    if len(file_bytes) > PHOTO_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photo must be 5MB or smaller")

    cleaned_bytes, ext = _sanitize_image(file_bytes, content_type)
    storage_path = f"{current_user.user_id}/{card.get('id')}.{ext}"

    supabase = require_supabase_admin_client()
    try:
        supabase.storage.from_(PHOTO_BUCKET).upload(
            path=storage_path,
            file=cleaned_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Photo upload failed: {exc}") from exc

    response = (
        supabase.table("player_cards")
        .update({"photo_storage_path": storage_path})
        .eq("id", card.get("id"))
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist photo path")

    updated = response.data[0]
    return {
        "photo_storage_path": storage_path,
        "photo_url": signed_photo_url(storage_path),
        "card": _decorate_card(updated),
    }


def _share_slug() -> str:
    return f"bp_{nanoid_generate(size=7)}"


def _public_share_url(slug: str) -> str:
    return f"{DEFAULT_PUBLIC_APP_URL.rstrip('/')}/p/{slug}"


@router.post("/me/share")
async def create_share_link(
    payload: ShareLinkRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    card = _get_my_card_row(current_user.user_id)

    last_error: Optional[Exception] = None
    inserted_row: Optional[Dict[str, Any]] = None
    for _ in range(8):
        slug = _share_slug()
        try:
            response = (
                supabase.table("card_share_links")
                .insert(
                    {
                        "card_id": card.get("id"),
                        "user_id": current_user.user_id,
                        "slug": slug,
                        "platform": payload.platform,
                        "label": payload.label,
                        "is_active": True,
                    }
                )
                .execute()
            )
            if response.data:
                inserted_row = response.data[0]
                break
        except Exception as exc:
            last_error = exc
            continue

    if inserted_row is None:
        detail = "Failed to create unique share link"
        if last_error:
            detail = f"{detail}: {last_error}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

    inserted_row["share_url"] = _public_share_url(str(inserted_row.get("slug")))
    return inserted_row


@router.get("/me/analytics")
async def get_card_analytics(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    card = _get_my_card_row(current_user.user_id)
    card_id = card.get("id")

    links_response = (
        supabase.table("card_share_links")
        .select("*")
        .eq("card_id", card_id)
        .eq("user_id", current_user.user_id)
        .order("created_at", desc=True)
        .execute()
    )
    links = links_response.data or []
    link_ids = [item.get("id") for item in links if item.get("id")]

    clicks = []
    if link_ids:
        clicks_response = (
            supabase.table("card_link_clicks")
            .select("*")
            .eq("card_id", card_id)
            .order("clicked_at", desc=True)
            .limit(1000)
            .execute()
        )
        clicks = clicks_response.data or []

    total_clicks = len(clicks)
    unique_clicks = sum(1 for click in clicks if click.get("is_unique"))
    by_platform: Dict[str, int] = {}
    by_link: Dict[str, Dict[str, int]] = {}
    for click in clicks:
        platform = str(click.get("platform_detected") or "general")
        by_platform[platform] = by_platform.get(platform, 0) + 1
        link_id = str(click.get("share_link_id"))
        link_counter = by_link.setdefault(link_id, {"total": 0, "unique": 0})
        link_counter["total"] += 1
        if click.get("is_unique"):
            link_counter["unique"] += 1

    link_summaries = []
    for link in links:
        link_id = str(link.get("id"))
        totals = by_link.get(link_id, {"total": 0, "unique": 0})
        link_summaries.append(
            {
                **link,
                "share_url": _public_share_url(str(link.get("slug"))),
                "clicks_total": totals["total"],
                "clicks_unique": totals["unique"],
            }
        )

    return {
        "card_id": card_id,
        "total_clicks": total_clicks,
        "unique_clicks": unique_clicks,
        "platform_breakdown": by_platform,
        "recent_clicks": clicks[:10],
        "share_links": link_summaries,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


@router.post("/me/refresh")
async def refresh_card_from_eval(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    card = _get_my_card_row(current_user.user_id)
    run = _latest_evaluation_for_user(current_user.user_id)

    prediction_fields = _extract_prediction_fields(run)
    updates = {
        "latest_evaluation_run_id": run.get("id"),
        "stats_snapshot": _first_dict(run.get("stats_input")),
        "prediction_level": prediction_fields.get("prediction_level"),
        "d1_probability": prediction_fields.get("d1_probability"),
        "p4_probability": prediction_fields.get("p4_probability"),
        "primary_position": _extract_primary_position(run),
        "bp_profile_link": _extract_bp_profile_link(str(run.get("id"))),
        "preferences_snapshot": _first_dict(run.get("preferences_input")),
    }
    response = (
        supabase.table("player_cards")
        .update(updates)
        .eq("id", card.get("id"))
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Card refresh failed")

    return _decorate_card(response.data[0])
