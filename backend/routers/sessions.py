from fastapi import APIRouter, HTTPException

from services import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(limit: int = 20):
    sessions = session_service.list_sessions()
    return sessions[:limit]


@router.get("/{session_id}")
async def get_session(session_id: str):
    try:
        return session_service.load_session(session_id)
    except session_service.SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    try:
        sid = session_service.resume_session(session_id)
        return {"session_id": sid, "status": "resumed"}
    except session_service.SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
