import json

from fastapi import APIRouter, HTTPException

from config import get_settings
from services import preference_service, token_tracking, workspace_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings_view():
    ws = get_settings().workspace_path
    status = workspace_service.get_workspace_status()
    prefs = preference_service.load_preferences(workspace_path=ws)
    voice_prefs = {
        "auto_speak": prefs.get("voice_auto_speak", "false"),
        "tts_voice": prefs.get("voice_tts_voice", "default"),
    }
    return {
        "workspace_path": str(ws),
        "api_key_set": status.get("api_key_set", False),
        "key_storage": "browser",
        "voice": voice_prefs,
    }


@router.patch("/api-key")
async def update_api_key(body: dict):
    key = body.get("api_key", "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key must not be empty")
    # Keys are managed in the browser (localStorage/sessionStorage).
    # This endpoint is a no-op kept for API compatibility.
    return {"api_key_set": True}


@router.patch("/voice")
async def update_voice_prefs(body: dict):
    ws = get_settings().workspace_path
    valid_keys = {"auto_speak", "tts_voice"}
    # Validate all keys first before writing any
    updates = {}
    for k, v in body.items():
        if k not in valid_keys:
            raise HTTPException(status_code=422, detail=f"Invalid voice setting: {k}")
        updates[f"voice_{k}"] = str(v)
    # Batch write atomically: load once, apply all, save once
    prefs = preference_service.load_preferences(workspace_path=ws)
    prefs.update(updates)
    path = preference_service._prefs_path(workspace_path=ws)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return {
        "auto_speak": prefs.get("voice_auto_speak", "false"),
        "tts_voice": prefs.get("voice_tts_voice", "default"),
    }


@router.get("/budget")
async def get_budget():
    budget = token_tracking.check_budget()
    return {
        "daily_budget": budget["budget"],
        "used_today": budget["used"],
        "percent": budget["percent"],
        "level": budget["level"],
    }


@router.patch("/budget")
async def update_budget(body: dict):
    value = body.get("daily_token_budget")
    if value is None:
        raise HTTPException(status_code=422, detail="daily_token_budget is required")
    try:
        budget_int = int(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="daily_token_budget must be an integer")
    if budget_int < 0:
        raise HTTPException(status_code=422, detail="daily_token_budget must be >= 0")
    ws = get_settings().workspace_path
    preference_service.save_preference("daily_token_budget", str(budget_int), workspace_path=ws)
    return {"daily_token_budget": budget_int}


@router.get("/usage")
async def get_usage():
    return token_tracking.get_usage_summary()


@router.get("/usage/today")
async def get_usage_today():
    return token_tracking.get_usage_today()


@router.get("/usage/history")
async def get_usage_by_day():
    return token_tracking.get_usage_by_day()


@router.get("/enrichment")
async def get_enrichment_settings():
    ws = get_settings().workspace_path
    prefs = preference_service.load_preferences(workspace_path=ws)
    from services.enrichment.runtime import is_on_battery_power
    return {
        "allow_on_battery": prefs.get("enrichment_allow_on_battery", "false") == "true",
        "on_battery": is_on_battery_power(),
    }


@router.patch("/enrichment")
async def update_enrichment_settings(body: dict):
    ws = get_settings().workspace_path
    allow = body.get("allow_on_battery")
    if allow is not None:
        preference_service.save_preference(
            "enrichment_allow_on_battery",
            "true" if allow else "false",
            workspace_path=ws,
        )
    prefs = preference_service.load_preferences(workspace_path=ws)
    return {
        "allow_on_battery": prefs.get("enrichment_allow_on_battery", "false") == "true",
    }
