from fastapi import APIRouter, HTTPException

from models.schemas import PreferenceSetRequest
from services import preference_service

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("")
async def get_preferences():
    return preference_service.load_preferences()


@router.patch("")
async def set_preference(req: PreferenceSetRequest):
    try:
        preference_service.save_preference(req.key, req.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return preference_service.load_preferences()


@router.delete("/{key}")
async def delete_preference(key: str):
    preference_service.delete_preference(key)
    return {"status": "deleted"}
