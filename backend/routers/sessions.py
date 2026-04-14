from fastapi import APIRouter, HTTPException

from services import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(limit: int = 20):
    return await session_service.list_sessions(limit=limit)


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


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    try:
        session_service.delete_session(session_id)
        session_service.delete_session_file(session_id)
    except session_service.SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    # Invalidate graph cache so stale session-derived data is cleared on next access
    from services.graph_service import invalidate_cache
    invalidate_cache()

    return {"status": "deleted", "session_id": session_id}
