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

export type WsEvent = WsTextDelta | WsToolUse | WsToolResult | WsDone | WsError | WsSessionStart
