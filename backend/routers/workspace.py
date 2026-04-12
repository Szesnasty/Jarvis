from fastapi import APIRouter, HTTPException, status

from models.schemas import WorkspaceInitRequest, WorkspaceInitResponse, WorkspaceStatusResponse
from services.workspace_service import (
    WorkspaceExistsError,
    create_workspace,
    get_workspace_status,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@router.get("/status", response_model=WorkspaceStatusResponse)
async def workspace_status() -> WorkspaceStatusResponse:
    data = get_workspace_status()
    return WorkspaceStatusResponse(**data)


@router.post("/init", response_model=WorkspaceInitResponse, status_code=status.HTTP_201_CREATED)
async def workspace_init(body: WorkspaceInitRequest) -> WorkspaceInitResponse:
    try:
        result = create_workspace(api_key=body.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except WorkspaceExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace already exists")
    return WorkspaceInitResponse(**result)
