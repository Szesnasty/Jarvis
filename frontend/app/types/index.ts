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
