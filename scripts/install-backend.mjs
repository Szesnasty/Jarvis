import { spawnSync } from 'node:child_process';
import * as fs from 'node:fs';
import { existsSync, mkdirSync, rmSync } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { join, resolve } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';

// ─── Platform detection ─────────────────────────────────────────────────────
const isWin = process.platform === 'win32';
const isMac = process.platform === 'darwin';

const CYAN = '\x1b[36m';
const YELLOW = '\x1b[33m';
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';
const RESET = '\x1b[0m';

// ─── Paths ──────────────────────────────────────────────────────────────────
const venvDirAbs = join('backend', '.venv');
const venvPythonRel = isWin
  ? join('.venv', 'Scripts', 'python.exe')
  : join('.venv', 'bin', 'python');
const venvPythonAbs = join('backend', venvPythonRel);

// Local standalone Python (downloaded on demand, never global)
const LOCAL_PYTHON_DIR = join('backend', '.python-local');
const LOCAL_PYTHON_BIN = resolve(
  isWin
    ? join(LOCAL_PYTHON_DIR, 'python', 'python.exe')
    : join(LOCAL_PYTHON_DIR, 'python', 'bin', 'python3'),
);

// ─── Python candidate commands ──────────────────────────────────────────────
// Try specific compatible versions FIRST, then generic commands.
// Windows `py -3.12` selects that exact minor version via the py launcher.
// Unix `python3.12` is a separate binary name installed by package managers.
const pythonCandidates = isWin
  ? [
      ['py', ['-3.13']],
      ['py', ['-3.12']],
      ['py', ['-3']],
      ['python', []],
      ['python3', []],
    ]
  : [
      ['python3.13', []],
      ['python3.12', []],
      ['python3', []],
      ['python', []],
    ];

// ─── Helpers ────────────────────────────────────────────────────────────────

function tryCommand(cmd, baseArgs) {
  const r = spawnSync(cmd, [...baseArgs, '--version'], {
    stdio: 'pipe',
    encoding: 'utf8',
  });
  if (r.error || r.status !== 0) return null;
  const out = (r.stdout || '') + (r.stderr || '');
  const match = out.match(/Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i);
  if (!match) return null;
  const major = Number(match[1]);
  const minor = Number(match[2]);
  if (major < 3 || (major === 3 && minor < 12)) {
    console.warn(
      `${DIM}[install-backend] skipping ${cmd} ${baseArgs.join(' ')} — Python ${major}.${minor} (need 3.12–3.13)${RESET}`,
    );
    return null;
  }
  if (major === 3 && minor > 13) {
    console.warn(
      `${DIM}[install-backend] skipping ${cmd} ${baseArgs.join(' ')} — Python ${major}.${minor} is too new (many ML packages lack wheels)${RESET}`,
    );
    return null;
  }
  const version = `${major}.${minor}${match[3] ? '.' + match[3] : ''}`;
  return { cmd, baseArgs, version };
}

function resolvePython() {
  for (const [cmd, baseArgs] of pythonCandidates) {
    const found = tryCommand(cmd, baseArgs);
    if (found) return found;
  }
  return null;
}

function checkLocalPython() {
  if (!existsSync(LOCAL_PYTHON_BIN)) return null;
  return tryCommand(LOCAL_PYTHON_BIN, []);
}

function isStandalonePython(py) {
  return resolve(py.cmd) === LOCAL_PYTHON_BIN;
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (r.error) {
    console.error(`[install-backend] failed to run ${cmd}: ${r.error.message}`);
    if (r.error.code === 'ENOENT') {
      console.error(`[install-backend] ${cmd} not found on PATH.`);
    }
    process.exit(1);
  }
  if (r.status !== 0) {
    console.error(`[install-backend] ${cmd} exited with code ${r.status}`);
    process.exit(r.status ?? 1);
  }
}

// Like `run`, but returns a result object instead of exiting on failure.
function tryRun(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  return r;
}

// Quiet version: capture stdout/stderr instead of streaming. Used for probes.
function tryRunQuiet(cmd, args, opts = {}) {
  return spawnSync(cmd, args, {
    stdio: 'pipe',
    encoding: 'utf8',
    ...opts,
  });
}

// ─── Venv health check ─────────────────────────────────────────────────────
// After a previous run was interrupted (Ctrl+C), the venv directory can exist
// without a working pip inside. Detect that and recreate cleanly.

function isVenvHealthy() {
  if (!existsSync(venvPythonAbs)) return false;
  const r = tryRunQuiet(venvPythonRel, ['-m', 'pip', '--version'], {
    cwd: 'backend',
    timeout: 15000,
  });
  return !r.error && r.status === 0;
}

function removeVenv() {
  try {
    rmSync(venvDirAbs, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  } catch (err) {
    console.error(
      `${RED}[install-backend] could not remove ${venvDirAbs}: ${err.message}${RESET}`,
    );
    if (isWin) {
      console.error(
        `${DIM}  → Make sure no Jarvis backend is still running (close any 'python.exe' / 'uvicorn' in Task Manager).${RESET}`,
      );
      console.error(
        `${DIM}  → Then delete the folder manually and run 'npm run wake-up-jarvis' again.${RESET}`,
      );
    }
    process.exit(1);
  }
}

// ─── Standalone Python download ─────────────────────────────────────────────
// Uses python-build-standalone (astral-sh): prebuilt portable Python binaries.
// No admin rights needed. Downloaded into backend/.python-local/ (project-local).

const PLATFORM_TRIPLES = {
  'darwin-arm64': 'aarch64-apple-darwin',
  'darwin-x64': 'x86_64-apple-darwin',
  'linux-x64': 'x86_64-unknown-linux-gnu',
  'linux-arm64': 'aarch64-unknown-linux-gnu',
  'win32-x64': 'x86_64-pc-windows-msvc',
};

async function findStandalonePythonUrl() {
  const triple = PLATFORM_TRIPLES[`${process.platform}-${process.arch}`];
  if (!triple) {
    console.warn(`[install-backend] no standalone Python build available for ${process.platform}-${process.arch}`);
    return null;
  }

  // Match cpython-3.12.x or 3.13.x install_only builds for our platform
  const pattern = new RegExp(
    `cpython-3\\.1[23]\\.\\d+\\+\\d+-${triple.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-install_only(?:_stripped)?\\.tar\\.gz$`,
  );

  console.log(`${DIM}[install-backend] querying GitHub for standalone Python builds…${RESET}`);
  try {
    const resp = await fetch(
      'https://api.github.com/repos/astral-sh/python-build-standalone/releases?per_page=5',
      { headers: { Accept: 'application/vnd.github.v3+json', 'User-Agent': 'jarvis-installer' } },
    );
    if (!resp.ok) {
      console.warn(`[install-backend] GitHub API returned ${resp.status}`);
      return null;
    }
    const releases = await resp.json();

    for (const release of releases) {
      for (const asset of release.assets || []) {
        if (pattern.test(asset.name)) {
          return { url: asset.browser_download_url, name: asset.name };
        }
      }
    }
  } catch (err) {
    console.warn(`[install-backend] could not reach GitHub API: ${err.message}`);
    return null;
  }
  return null;
}

async function downloadStandalonePython() {
  const asset = await findStandalonePythonUrl();
  if (!asset) {
    console.error('[install-backend] could not find a matching standalone Python build.');
    return false;
  }

  mkdirSync(LOCAL_PYTHON_DIR, { recursive: true });
  const dest = join(LOCAL_PYTHON_DIR, asset.name);

  console.log(`[install-backend] downloading ${CYAN}${asset.name}${RESET}`);
  console.log(`${DIM}[install-backend] from: ${asset.url}${RESET}`);

  // curl is built into Windows 10+ (1803), macOS, and Linux.
  const dl = spawnSync('curl', ['-fSL', '--progress-bar', '-o', dest, asset.url], {
    stdio: 'inherit',
  });
  if (dl.error || dl.status !== 0) {
    console.error('[install-backend] download failed. Check your internet connection.');
    return false;
  }

  console.log('[install-backend] extracting…');
  // tar is built into Windows 10+ (1803), macOS, and Linux.
  // tar is built into Windows 10+ (1803), macOS, and Linux.
  const ext = spawnSync('tar', ['-xzf', dest, '-C', LOCAL_PYTHON_DIR], {
    stdio: 'inherit',
  });
  if (ext.error || ext.status !== 0) {
    console.error('[install-backend] extraction failed.');
    return false;
  }

  // Clean up tarball
  rmSync(dest, { force: true });

  console.log(`${GREEN}[install-backend] Python installed locally to ${LOCAL_PYTHON_DIR}${RESET}`);
  return true;
}

// ─── Pip bootstrap via get-pip.py ───────────────────────────────────────────
// For local standalone Python, we create the venv with --without-pip to avoid
// the well-known ensurepip hang on Windows (antivirus + PIPE deadlock during
// bootstrap). We then install pip into the venv via get-pip.py, which writes
// to the venv's Scripts/ and site-packages/ directly — fast and reliable.

const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py';

async function bootstrapPipIntoVenv() {
  // Use absolute paths everywhere so curl (run from project root) and python
  // (run from `backend/`) both see the exact same file. Relative paths break
  // because the two commands have different working directories.
  const getPipPath = resolve('backend', '.venv', 'get-pip.py');
  console.log(`${DIM}[install-backend] downloading get-pip.py (skips ensurepip bootstrap)${RESET}`);

  const dl = spawnSync('curl', ['-fSL', '--progress-bar', '-o', getPipPath, GET_PIP_URL], {
    stdio: 'inherit',
  });
  if (dl.error || dl.status !== 0) {
    console.error(`${RED}[install-backend] failed to download get-pip.py${RESET}`);
    console.error(`${DIM}  → Check your internet connection.${RESET}`);
    return false;
  }
  if (!existsSync(getPipPath)) {
    console.error(`${RED}[install-backend] get-pip.py not found at ${getPipPath} after download${RESET}`);
    return false;
  }

  console.log('[install-backend] installing pip into the venv');
  // Pass the absolute get-pip.py path. venvPythonRel is still relative to cwd='backend'
  // which is fine because we resolve it via shell lookup from that cwd.
  const r = tryRun(venvPythonRel, [getPipPath, '--no-warn-script-location'], { cwd: 'backend' });
  // Always try to clean up, even on failure
  try { rmSync(getPipPath, { force: true }); } catch {}

  if (r.error || r.status !== 0) {
    console.error(`${RED}[install-backend] get-pip.py failed${RESET}`);
    return false;
  }
  return true;
}

async function promptYesNo(question) {
  // Non-interactive (CI, piped stdin) → default no
  if (!stdin.isTTY) return false;
  const rl = createInterface({ input: stdin, output: stdout });
  try {
    const answer = await rl.question(question);
    const a = answer.trim().toLowerCase();
    return a === '' || a === 'y' || a === 'yes'; // default = yes
  } finally {
    rl.close();
  }
}

function printManualInstructions() {
  console.error();
  console.error(`${RED}${BOLD}[install-backend] could not find or download Python 3.12–3.13.${RESET}`);
  console.error('[install-backend] Please install manually:');
  if (isWin) {
    console.error('  → Download Python 3.12.x from https://www.python.org/downloads/');
    console.error('  → Tick "Add Python to PATH" during install');
  } else if (isMac) {
    console.error('  → brew install python@3.12');
  } else {
    console.error('  → sudo apt install python3.12 python3.12-venv   (Debian/Ubuntu)');
    console.error('  → sudo dnf install python3.12                    (Fedora)');
  }
  console.error();
}

// ─── Venv creation ──────────────────────────────────────────────────────────

async function createVenv(py) {
  const standalone = isStandalonePython(py);

  console.log(`[install-backend] creating venv at ${venvDirAbs}`);
  if (isWin) {
    console.log(
      `${DIM}  (on Windows this can take 30–90s — antivirus scans every file. Please wait.)${RESET}`,
    );
  }

  if (standalone) {
    // Standalone Python + ensurepip can deadlock on Windows — skip it entirely.
    console.log(`${DIM}[install-backend] using --without-pip (pip will be bootstrapped via get-pip.py)${RESET}`);
    const r = tryRun(py.cmd, [...py.baseArgs, '-m', 'venv', '--without-pip', '.venv'], { cwd: 'backend' });
    if (r.error || r.status !== 0) {
      console.error(`${RED}[install-backend] venv creation failed${RESET}`);
      return false;
    }
    const ok = await bootstrapPipIntoVenv();
    if (!ok) return false;
  } else {
    // System Python — ensurepip is reliable, use the normal path.
    const r = tryRun(py.cmd, [...py.baseArgs, '-m', 'venv', '.venv'], { cwd: 'backend' });
    if (r.error || r.status !== 0) {
      console.error(`${RED}[install-backend] venv creation failed${RESET}`);
      if (isWin) {
        console.error(`${DIM}  → If this looks hung on Windows, it's likely antivirus scanning pip.${RESET}`);
        console.error(`${DIM}  → Add an exclusion for: ${resolve(venvDirAbs)}${RESET}`);
      }
      return false;
    }
  }
  return true;
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  // --- Detect & clean up a broken venv from a previous interrupted run ---
  if (existsSync(venvDirAbs) && !isVenvHealthy()) {
    console.log(
      `${YELLOW}[install-backend] existing venv at ${venvDirAbs} is incomplete or broken — recreating${RESET}`,
    );
    console.log(
      `${DIM}  (this happens when a previous install was interrupted — e.g. Ctrl+C during pip bootstrap)${RESET}`,
    );
    removeVenv();
  }

  // --- Resolve Python (if venv doesn't already exist) ---
  if (!existsSync(venvDirAbs)) {
    // 1. Check for previously downloaded local Python
    let py = checkLocalPython();

    // 2. Check system Python
    if (!py) {
      py = resolvePython();
    }

    // 3. Offer to download if nothing found
    if (!py) {
      console.log();
      console.log(`${YELLOW}${BOLD}[install-backend] Python 3.12–3.13 not found on this system.${RESET}`);
      console.log();

      const wantDownload = await promptYesNo(
        `${BOLD}Download a local copy of Python 3.12?${RESET} ${DIM}(~50 MB, does NOT require admin)${RESET} [Y/n] `,
      );

      if (wantDownload) {
        const ok = await downloadStandalonePython();
        if (ok) {
          py = checkLocalPython();
        }
      }

      if (!py) {
        printManualInstructions();
        process.exit(1);
      }
    }

    const label = isStandalonePython(py) ? `${py.cmd} ${DIM}(local standalone)${RESET}` : `${py.cmd} ${py.baseArgs.join(' ')}`;
    console.log(`[install-backend] using ${CYAN}${label}${RESET} (Python ${py.version})`);

    const created = await createVenv(py);
    if (!created) {
      // Clean up whatever half-created state exists so the next run starts fresh.
      if (existsSync(venvDirAbs)) removeVenv();
      process.exit(1);
    }
  } else {
    console.log(`[install-backend] venv already exists at ${venvDirAbs}`);
  }

  // --- Verify venv ---
  if (!existsSync(venvPythonAbs)) {
    console.error(`${RED}[install-backend] venv created but ${venvPythonAbs} is missing.${RESET}`);
    console.error(`${DIM}  → Delete ${venvDirAbs} and run 'npm run wake-up-jarvis' again.${RESET}`);
    process.exit(1);
  }

  // --- Install dependencies ---
  console.log('[install-backend] upgrading pip');
  run(venvPythonRel, ['-m', 'pip', 'install', '--upgrade', 'pip'], { cwd: 'backend' });

  console.log('[install-backend] installing requirements.txt');
  if (isWin) {
    console.log(`${DIM}  (this downloads ~400MB of ML wheels — can take 2–5 minutes on first run)${RESET}`);
  }
  run(venvPythonRel, ['-m', 'pip', 'install', '-r', 'requirements.txt'], { cwd: 'backend' });

  // Apply security overrides AFTER the main install. pip's resolver can't
  // override transitive pins (uv can, but we use pip locally for portability),
  // so we force-upgrade vulnerable transitive deps in a second pass.
  // Currently: python-dotenv 1.0.1 → 1.2.2 (CVE-2026-28684). litellm only
  // uses load_dotenv() which is API-stable across these versions.
  // Source of truth: backend/overrides.txt.
  console.log('[install-backend] applying security overrides (overrides.txt)');
  run(
    venvPythonRel,
    ['-m', 'pip', 'install', '--upgrade', '-r', 'overrides.txt'],
    { cwd: 'backend' },
  );

  // Install backend as editable so the `jarvis-mcp` console script is generated.
  console.log('[install-backend] installing backend package (registers `jarvis-mcp` CLI)');
  run(venvPythonRel, ['-m', 'pip', 'install', '-e', '.'], { cwd: 'backend' });

  await setupMcpCli();

  console.log(`${GREEN}[install-backend] done${RESET}`);
}

async function setupMcpCli() {
  // Symlink jarvis-mcp into ~/.local/bin so MCP clients can spawn it without
  // any absolute paths in their config files.
  if (isWin) {
    console.log(
      `${DIM}[install-backend] skipping ~/.local/bin symlink on Windows; use full path or add backend\\.venv\\Scripts to PATH${RESET}`,
    );
    return;
  }

  const homedir = os.homedir();
  const localBin = path.join(homedir, '.local', 'bin');
  const target = path.resolve('backend', '.venv', 'bin', 'jarvis-mcp');
  const linkPath = path.join(localBin, 'jarvis-mcp');

  if (!fs.existsSync(target)) {
    console.warn(`${DIM}[install-backend] jarvis-mcp binary not found at ${target}; skipping symlink${RESET}`);
    return;
  }

  fs.mkdirSync(localBin, { recursive: true });
  try {
    if (fs.existsSync(linkPath) || fs.lstatSync(linkPath, { throwIfNoEntry: false })) {
      fs.unlinkSync(linkPath);
    }
  } catch {
    /* ignore — best-effort cleanup */
  }
  try {
    fs.symlinkSync(target, linkPath);
    console.log(`${GREEN}[install-backend] linked jarvis-mcp -> ${linkPath}${RESET}`);
  } catch (err) {
    console.warn(`[install-backend] could not symlink ${linkPath}: ${err.message}`);
    return;
  }

  // Persist workspace path to ~/.jarvis/config.toml so jarvis-mcp can find it
  // without any environment variables or CLI flags.
  const workspaceFromEnv = process.env.JARVIS_WORKSPACE;
  const workspace = workspaceFromEnv && workspaceFromEnv.trim()
    ? workspaceFromEnv.trim()
    : path.join(homedir, 'Jarvis');

  const configDir = path.join(homedir, '.jarvis');
  const configFile = path.join(configDir, 'config.toml');
  fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(configFile, `workspace = "${workspace}"\n`, 'utf8');
  console.log(`${GREEN}[install-backend] wrote ${configFile} (workspace=${workspace})${RESET}`);

  // PATH check
  const pathEntries = (process.env.PATH || '').split(path.delimiter);
  if (!pathEntries.includes(localBin)) {
    console.log(
      `${DIM}[install-backend] note: ${localBin} is not on your PATH. Add it via:${RESET}\n` +
        `    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc\n` +
        `${DIM}  GUI apps (Cursor, Claude Desktop) usually still find symlinks here on macOS.${RESET}`,
    );
  }
}

main().catch((err) => {
  console.error(`[install-backend] unexpected error: ${err.message}`);
  process.exit(1);
});
