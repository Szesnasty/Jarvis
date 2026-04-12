from fastapi import APIRouter, HTTPException, Query

from services import specialist_service

router = APIRouter(prefix="/api/specialists", tags=["specialists"])


@router.get("")
async def list_specialists():
    return specialist_service.list_specialists()


@router.get("/active")
async def get_active():
    active = specialist_service.get_active_specialist()
    return active if active else {"active": None}


@router.get("/suggest")
async def suggest_specialist(message: str = Query(...)):
    """Suggest a specialist based on the user's message content."""
    suggestion = specialist_service.suggest_specialist(message)
    if suggestion:
        return {"suggested": suggestion}
    return {"suggested": None}


@router.get("/{spec_id}")
async def get_specialist(spec_id: str):
    try:
        return specialist_service.get_specialist(spec_id)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.post("")
async def create_specialist(data: dict):
    try:
        spec = specialist_service.create_specialist(data)
        return spec
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/{spec_id}")
async def update_specialist(spec_id: str, data: dict):
    try:
        return specialist_service.update_specialist(spec_id, data)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.delete("/{spec_id}")
async def delete_specialist(spec_id: str):
    try:
        specialist_service.delete_specialist(spec_id)
        return {"status": "deleted"}
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.post("/activate/{spec_id}")
async def activate_specialist(spec_id: str):
    try:
        spec = specialist_service.activate_specialist(spec_id)
        return {"status": "activated", "specialist": spec}
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.post("/deactivate")
async def deactivate_specialist():
    specialist_service.deactivate_specialist()
    return {"status": "deactivated"}
