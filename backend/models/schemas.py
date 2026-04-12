from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class WorkspaceInitRequest(BaseModel):
    api_key: str


class WorkspaceInitResponse(BaseModel):
    status: str
    workspace_path: str


class WorkspaceStatusResponse(BaseModel):
    initialized: bool
    workspace_path: Optional[str] = None
    api_key_set: Optional[bool] = None
