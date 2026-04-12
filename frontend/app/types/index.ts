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
