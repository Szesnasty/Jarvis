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
}

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

// --- Chat ---

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
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

export type WsEvent = WsTextDelta | WsToolUse | WsToolResult | WsDone | WsError | WsSessionStart | WsSessionHistory | WsDisconnected | WsWarning | WsMemoryChanged

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

export interface GraphEdge {
  source: string
  target: string
  type: string
  weight?: number
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
}

export interface SpecialistDetail {
  id: string
  name: string
  role: string
  sources: string[]
  style: { tone?: string; format?: string; length?: string }
  rules: string[]
  tools: string[]
  examples: { user: string; assistant: string }[]
  icon: string
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
