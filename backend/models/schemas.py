from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


# --- Specialists ---

class SpecialistCreateRequest(BaseModel):
    name: str
    role: str = ""
    sources: list = []


# --- URL Ingest ---

class UrlIngestRequest(BaseModel):
    url: str
    folder: str = Field(default="knowledge", pattern=r"^[a-zA-Z0-9-]+$")
    summarize: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value
    style: dict = {}
    rules: list = []
    tools: list = []
    examples: list = []
    icon: str = "\U0001f916"


class SpecialistSummaryResponse(BaseModel):
    id: str
    name: str
    icon: str = "\U0001f916"
    source_count: int = 0
    rule_count: int = 0


class SpecialistDetailResponse(BaseModel):
    id: str
    name: str
    role: str = ""
    sources: list = []
    style: dict = {}
    rules: list = []
    tools: list = []
    examples: list = []
    icon: str = "\U0001f916"
    created_at: str = ""
    updated_at: str = ""
