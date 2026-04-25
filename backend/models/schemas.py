from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    version: str


class WorkspaceInitRequest(BaseModel):
    """Workspace creation request. No API key — keys live in the browser."""


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
    # Step 28b — document grouping fields from frontmatter
    document_type: Optional[str] = None
    parent: Optional[str] = None
    section_index: Optional[int] = None
    section_type: Optional[str] = None


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
    system_prompt: str = ""
    sources: list[str] = []
    style: dict[str, str] = {}
    rules: list[str] = []
    tools: list[str] = []
    examples: list[dict[str, str]] = []
    icon: str = "\U0001f916"
    default_model: Optional[SpecialistDefaultModel] = None


# JARVIS self-config: only two user-editable fields. Length caps prevent
# accidental prompt-bombing of the model context window. The default Jarvis
# system prompt is intentionally NOT exposed to the client — users see only
# their own override (or empty) in `system_prompt`.
JARVIS_PROMPT_MAX_CHARS = 16000


class JarvisSelfConfigRequest(BaseModel):
    system_prompt: Optional[str] = None
    behavior_extension: Optional[str] = None

    @field_validator("system_prompt", "behavior_extension")
    @classmethod
    def _cap_length(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if len(value) > JARVIS_PROMPT_MAX_CHARS:
            raise ValueError(
                f"Field exceeds {JARVIS_PROMPT_MAX_CHARS} characters",
            )
        return value


class JarvisSelfConfigResponse(BaseModel):
    system_prompt: str = ""
    behavior_extension: str = ""


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
    system_prompt: str = ""
    behavior_extension: str = ""
    sources: list[str] = []
    style: dict[str, str] = {}
    rules: list[str] = []
    tools: list[str] = []
    examples: list[dict[str, str]] = []
    icon: str = "\U0001f916"
    default_model: Optional[dict] = None
    builtin: bool = False
    created_at: str = ""
    updated_at: str = ""


class SpecialistFileInfoResponse(BaseModel):
    filename: str
    path: str
    title: str
    size: int
    created_at: str


# Step 22f: Retrieval search
class FacetFilterRequest(BaseModel):
    status_category: Optional[list[str]] = None
    sprint_state: Optional[list[str]] = None
    sprint_name: Optional[list[str]] = None
    assignee: Optional[list[str]] = None
    project_key: Optional[list[str]] = None
    business_area: Optional[list[str]] = None
    risk_level: Optional[list[str]] = None
    ambiguity_level: Optional[list[str]] = None
    work_type: Optional[list[str]] = None


class RetrievalSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    facets: Optional[FacetFilterRequest] = None


class IntentResponse(BaseModel):
    text: str
    wants_issues_only: bool = False
    wants_open_only: bool = False
    sprint_filter: Optional[str] = None
    assignee_filter: Optional[str] = None
    business_area_hint: Optional[str] = None
    risk_hint: Optional[str] = None
    keys_in_query: list[str] = []
    has_jira_signals: bool = False


class RetrievalSearchResponse(BaseModel):
    results: list[dict]
    intent: IntentResponse
    result_count: int


# --- Smart Connect Backfill (Step 26a) ---

class BackfillRequest(BaseModel):
    mode: Literal["fast", "aggressive"] = "fast"
    batch_size: int = Field(50, ge=1, le=500)
    only_orphans: bool = False
    dry_run: bool = False
    force: bool = False
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class BackfillProgress(BaseModel):
    done: int
    total: int
    suggestions_added: int
    notes_changed: int
    skipped: int
    orphans_found: int
    dry_run: bool
