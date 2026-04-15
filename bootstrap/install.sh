#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_LOCAL_DIR="$ROOT_DIR/.node-local"
NODE_CACHE_DIR="$NODE_LOCAL_DIR/cache"

log() {
  printf '[bootstrap] %s\n' "$1"
}

warn() {
  printf '[bootstrap] %s\n' "$1" >&2
}

has_system_node() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    return 1
  fi
  local version major
  version="$(node --version 2>/dev/null || true)"
  if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    return 1
  fi
  major="${version#v}"
  major="${major%%.*}"
  [[ "$major" -ge 20 ]]
}

get_platform_tuple() {
  local os arch platform ext
  os="$(uname -s)"
  arch="$(uname -m)"

  case "$arch" in
    x86_64|amd64)
      arch='x64'
      ;;
    arm64|aarch64)
      arch='arm64'
      ;;
    *)
      warn "Unsupported CPU architecture: $arch"
      return 1
      ;;
  esac

  case "$os" in
    Darwin)
      platform='darwin'
      ext='tar.gz'
      ;;
    Linux)
      platform='linux'
      ext='tar.xz'
      ;;
    *)
      warn "Unsupported OS: $os"
      return 1
      ;;
  esac

  printf '%s %s %s\n' "$platform" "$arch" "$ext"
}

download_local_node() {
  local answer platform arch ext index_tab version file_name url archive_path extract_dir

  read -r -p "Node.js 20+ not found. Download a local copy now (~50 MB, no admin required)? [Y/n] " answer
  answer="${answer:-Y}"
  case "$answer" in
    y|Y|yes|YES)
      ;;
    *)
      warn "Aborted. Install Node.js 20+ manually from https://nodejs.org/"
      return 1
      ;;
  esac

  read -r platform arch ext < <(get_platform_tuple)

  mkdir -p "$NODE_CACHE_DIR"
  index_tab="$(curl -fsSL https://nodejs.org/dist/index.tab)"
  version="$(printf '%s\n' "$index_tab" | awk 'NR>1 && $1 ~ /^v20\./ {print $1; exit}')"

  if [[ -z "$version" ]]; then
    warn 'Could not resolve latest Node.js 20 release from nodejs.org.'
    return 1
  fi

  file_name="node-${version}-${platform}-${arch}.${ext}"
  url="https://nodejs.org/dist/${version}/${file_name}"
  archive_path="$NODE_CACHE_DIR/$file_name"
  extract_dir="$NODE_LOCAL_DIR/node-${version}-${platform}-${arch}"

  log "Downloading ${file_name}"
  if [[ ! -f "$archive_path" ]]; then
    curl -fSL "$url" -o "$archive_path"
  else
    log "Using cached archive ${file_name}"
  fi

  if [[ ! -d "$extract_dir" ]]; then
    log 'Extracting Node.js archive'
    mkdir -p "$NODE_LOCAL_DIR"
    if [[ "$ext" == 'tar.gz' ]]; then
      tar -xzf "$archive_path" -C "$NODE_LOCAL_DIR"
    else
      tar -xJf "$archive_path" -C "$NODE_LOCAL_DIR"
    fi
  fi

  printf '%s\n' "$extract_dir"
}

run_wake_up() {
  local npm_cmd="$1"
  cd "$ROOT_DIR"
  "$npm_cmd" run wake-up-jarvis
}

if has_system_node; then
  log "Using system Node.js: $(node --version)"
  run_wake_up "$(command -v npm)"
  exit 0
fi

node_dir="$(download_local_node)" || exit 1
node_bin="$node_dir/bin"

if [[ ! -x "$node_bin/node" || ! -x "$node_bin/npm" ]]; then
  warn 'Local Node.js install appears incomplete.'
  exit 1
fi

export PATH="$node_bin:$PATH"
log "Using local Node.js: $($node_bin/node --version)"
run_wake_up "$node_bin/npm"
