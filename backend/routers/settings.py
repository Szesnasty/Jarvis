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
        "key_storage": workspace_service.get_key_storage_method(ws),
        "voice": voice_prefs,
    }


@router.patch("/api-key")
async def update_api_key(body: dict):
    key = body.get("api_key", "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key must not be empty")
    ws = get_settings().workspace_path
    workspace_service._store_api_key(key, ws)
    return {"api_key_set": True}


@router.patch("/voice")
async def update_voice_prefs(body: dict):
    ws = get_settings().workspace_path
    valid_keys = {"auto_speak", "tts_voice"}
    for k, v in body.items():
        if k not in valid_keys:
            raise HTTPException(status_code=422, detail=f"Invalid voice setting: {k}")
        preference_service.save_preference(f"voice_{k}", str(v), workspace_path=ws)
    prefs = preference_service.load_preferences(workspace_path=ws)
    return {
        "auto_speak": prefs.get("voice_auto_speak", "false"),
        "tts_voice": prefs.get("voice_tts_voice", "default"),
    }


@router.get("/usage")
async def get_usage():
    return token_tracking.get_usage_summary()


@router.get("/usage/today")
async def get_usage_today():
    return token_tracking.get_usage_today()


@router.get("/usage/history")
async def get_usage_by_day():
    return token_tracking.get_usage_by_day()
