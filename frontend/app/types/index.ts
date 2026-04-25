export interface HealthResponse {
  status: string
  version: string
}

export type BackendStatus = 'unknown' | 'online' | 'offline'

export interface WorkspaceStatusResponse {
  initialized: boolean
  workspace_path?: string
  api_key_set?: boolean
}

export interface WorkspaceInitResponse {
  status: string
  workspace_path: string
}

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface NoteMetadata {
  path: string
  title: string
  folder: string
  tags: string[]
  updated_at: string
  word_count: number
  // Step 28b — document grouping fields. Index notes from PDF/etc section
  // split carry `document_type` (e.g. "pdf-document"); section notes carry
  // `parent` (the index path) and `section_index` (1-based). Plain notes
  // have all three null.
  document_type?: string | null
  parent?: string | null
  section_index?: number | null
}

// Step 28b — Memory sidebar tree node. Documents collapse into one
// expandable row with their sections; everything else stays flat.
export type NoteTreeNode =
  | { kind: 'note'; note: NoteMetadata }
  | { kind: 'document'; index: NoteMetadata; sections: NoteMetadata[] }

export interface NoteDetail {
  path: string
  title: string
  content: string
  frontmatter: Record<string, unknown>
  updated_at: string
}

export interface ReindexResponse {
  indexed: number
}

// --- Connections (Smart Connect — Step 25) ---

export interface SuggestedLink {
  path: string
  confidence: number
  methods: string[]
  tier?: string
  evidence?: unknown
  score_breakdown?: Record<string, number> | null
  suggested_at?: string | null
  suggested_by?: string | null
}

export interface SemanticOrphan {
  id: string
  label: string
  folder?: string
}

export interface ConnectionResult {
  note_path: string
  suggested: SuggestedLink[]
  strong_count: number
  aliases_matched: string[]
  graph_edges_added: number
}

// --- Chat ---

// Step 28a — per-note retrieval trace surfaced under each assistant answer.
export interface TraceItem {
  path: string
  title: string
  score: number
  reason: 'primary' | 'expansion'
  via: string
  edge_type?: string | null
  tier?: string | null
  signals?: Record<string, number>
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  model?: string
  provider?: string
  timestamp?: string
  trace?: TraceItem[]
}

export interface WsTextDelta {
  type: 'text_delta'
  content: string
}

export interface WsToolUse {
  type: 'tool_use'
  name: string
  input: Record<string, unknown>
}

export interface WsToolResult {
  type: 'tool_result'
  name: string
  content: string
}

export interface WsDone {
  type: 'done'
  session_id: string
  model?: string
  provider?: string
  tool_mode?: string
}

export interface WsError {
  type: 'error'
  content: string
}

export interface WsSessionStart {
  type: 'session_start'
  session_id: string
}

export interface WsSessionHistory {
  type: 'session_history'
  messages: ChatMessage[]
}

export interface WsDisconnected {
  type: 'disconnected'
}

export interface WsWarning {
  type: 'warning'
  content: string
}

export interface WsMemoryChanged {
  type: 'memory_changed'
  path: string
  action: string
}

export interface WsTrace {
  type: 'trace'
  items: TraceItem[]
}

export type WsEvent = WsTextDelta | WsToolUse | WsToolResult | WsDone | WsError | WsSessionStart | WsSessionHistory | WsDisconnected | WsWarning | WsMemoryChanged | WsTrace

// --- Sessions ---

export interface SessionMetadata {
  session_id: string
  title: string
  created_at: string
  message_count: number
}

export interface SessionDetail extends SessionMetadata {
  ended_at?: string
  messages: ChatMessage[]
  tools_used: string[]
}

// --- Graph ---

export interface GraphNode {
  id: string
  type: string
  label: string
  folder: string
}

export interface ChunkEvidence {
  source_chunk: number
  target_chunk: number
  similarity: number
}

export interface GraphEdge {
  source: string
  target: string
  type: string
  weight?: number
  evidence?: ChunkEvidence[]
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  node_count: number
  edge_count: number
  top_connected: { id: string; degree: number }[]
}

export interface GraphNodeDetail {
  node: GraphNode
  preview: string | null
  metadata?: Record<string, unknown>
  note_path?: string | null
  connected_notes: GraphNode[]
  connected_tags: string[]
  connected_people: string[]
  neighbor_count: number
  degree: number
}

export interface GraphOrphan {
  id: string
  label: string
  folder: string
}

// --- Specialists ---

export interface SpecialistSummary {
  id: string
  name: string
  icon: string
  source_count: number
  rule_count: number
  file_count: number
  default_model?: { provider: string; model: string } | null
  builtin?: boolean
}

export interface SpecialistDetail {
  id: string
  name: string
  role: string
  system_prompt?: string
  sources: string[]
  style: { tone?: string; format?: string; length?: string }
  rules: string[]
  tools: string[]
  examples: { user: string; assistant: string }[]
  icon: string
  default_model?: { provider: string; model: string } | null
  created_at: string
  updated_at: string
}

export interface SpecialistFileInfo {
  filename: string
  path: string
  title: string
  size: number
  created_at: string
}

// JARVIS-self: only two user-editable fields. The default Jarvis system
// prompt is intentionally NOT exposed by the backend — `system_prompt` here
// is the user's override (or "" to use the built-in default).
export interface JarvisSelfConfig {
  system_prompt: string
  behavior_extension: string
}

// --- URL Ingest ---

export interface UrlIngestResult {
  path: string
  title: string
  type: 'youtube' | 'article'
  source: string
  word_count: number
  summary?: string
}

// --- API Error ---

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// --- AI Providers ---

export interface ProviderConfig {
  id: string
  name: string
  icon: string
  keyPrefix: string
  docsUrl: string
  models: string[]
  color: string
}

export interface StoredKeyMeta {
  remember: boolean
  addedAt: string
}

// --- Duel ---

export interface DuelConfig {
  topic: string
  specialist_ids: string[]
}

export interface DuelEvent {
  type: string
  specialist?: string
  content?: string
  round?: number
  // Metadata fields spread at top level by backend
  scores?: Record<string, Record<string, number>>
  winner?: string
  reasoning?: string
  recommendation?: string
  action_items?: string[]
  saved_path?: string
  duel_id?: string
  specialists?: { id: string; name: string; icon: string }[]
  topic?: string
  label?: string
  token_usage?: { input: number; output: number }
}

export interface DuelVerdict {
  scores: Record<string, Record<string, number>>
  winner: string
  reasoning: string
  recommendation: string
  action_items: string[]
}

export type DuelPhase = 'idle' | 'setup' | 'round1' | 'round2' | 'judging' | 'verdict' | 'done' | 'error'

// --- Local Models (Ollama) ---

export type HardwareTier = 'light' | 'balanced' | 'strong' | 'workstation'
export type ModelCompatibility = 'great' | 'good' | 'warning' | 'unsupported'
export type LocalModelPreset = 'fast' | 'everyday' | 'balanced' | 'long-docs'
  | 'reasoning' | 'code' | 'best-local'

export interface HardwareProfile {
  os: string
  arch: string
  total_ram_gb: number
  free_disk_gb: number
  cpu_cores: number
  gpu_vendor?: string
  gpu_vram_gb?: number
  is_apple_silicon: boolean
  tier: HardwareTier
}

export interface RuntimeStatus {
  runtime: string
  installed: boolean
  running: boolean
  base_url: string
  version?: string
  reachable: boolean
}

export interface ModelRecommendation {
  model_id: string
  preset: LocalModelPreset
  label: string
  ollama_model: string
  litellm_model: string
  download_size_gb: number
  context_window: string
  strengths: string[]
  best_for: string[]
  recommended_ram: string
  native_tools: boolean
  tool_mode: string
  compatibility: ModelCompatibility
  score: number
  recommended: boolean
  reason: string
  installed: boolean
  active: boolean
}

export interface PullProgress {
  status: string
  digest?: string
  total?: number
  completed?: number
}
