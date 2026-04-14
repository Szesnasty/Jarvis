from typing import Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    version: str


class WorkspaceInitRequest(BaseModel):
    api_key: Optional[str] = None

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return v


class WorkspaceInitResponse(BaseModel):
    status: str
    workspace_path: str


class WorkspaceStatusResponse(BaseModel):
    initialized: bool
    workspace_path: Optional[str] = None
    api_key_set: Optional[bool] = None
    key_storage: Optional[str] = None


# --- Memory ---

class NoteContentRequest(BaseModel):
    content: str


class NoteAppendRequest(BaseModel):
    append: str


class NoteMetadataResponse(BaseModel):
    path: str
    title: str
    folder: str
    tags: list[str]
    updated_at: str
    word_count: int


class NoteDetailResponse(BaseModel):
    path: str
    title: str
    content: str
    frontmatter: dict[str, object]
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
    messages: list[dict[str, str]]
    tools_used: list[str] = []


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
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    top_connected: list[dict[str, object]] = []


# --- Specialists ---

class SpecialistDefaultModel(BaseModel):
    provider: str
    model: str


class SpecialistCreateRequest(BaseModel):
    name: str
    role: str = ""
    sources: list[str] = []
    style: dict[str, str] = {}
    rules: list[str] = []
    tools: list[str] = []
    examples: list[dict[str, str]] = []
    icon: str = "\U0001f916"
    default_model: Optional[SpecialistDefaultModel] = None


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


class SpecialistSummaryResponse(BaseModel):
    id: str
    name: str
    icon: str = "\U0001f916"
    source_count: int = 0
    rule_count: int = 0
    file_count: int = 0


class SpecialistDetailResponse(BaseModel):
    id: str
    name: str
    role: str = ""
    sources: list[str] = []
    style: dict[str, str] = {}
    rules: list[str] = []
    tools: list[str] = []
    examples: list[dict[str, str]] = []
    icon: str = "\U0001f916"
    default_model: Optional[dict] = None
    created_at: str = ""
    updated_at: str = ""


class SpecialistFileInfoResponse(BaseModel):
    filename: str
    path: str
    title: str
    size: int
    created_at: str
