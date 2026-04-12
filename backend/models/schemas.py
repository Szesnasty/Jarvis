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


# --- Memory ---

class NoteContentRequest(BaseModel):
    content: str


class NoteAppendRequest(BaseModel):
    append: str


class NoteMetadataResponse(BaseModel):
    path: str
    title: str
    folder: str
    tags: list
    updated_at: str
    word_count: int


class NoteDetailResponse(BaseModel):
    path: str
    title: str
    content: str
    frontmatter: dict
    updated_at: str


class ReindexResponse(BaseModel):
    indexed: int


# --- Chat ---

class ChatMessage(BaseModel):
    type: str = "message"
    content: str
    session_id: Optional[str] = None


class ChatEvent(BaseModel):
    type: str
    content: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict] = None
    session_id: Optional[str] = None


# --- Sessions ---

class SessionMetadataResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    message_count: int


class SessionDetailResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    ended_at: Optional[str] = None
    message_count: int
    messages: list
    tools_used: list = []


# --- Preferences ---

class PreferenceSetRequest(BaseModel):
    key: str
    value: str


# --- Graph ---

class GraphNodeResponse(BaseModel):
    id: str
    type: str
    label: str
    folder: str = ""


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list
    edges: list


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    top_connected: list = []
