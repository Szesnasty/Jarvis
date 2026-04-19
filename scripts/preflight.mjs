import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

// process.platform === 'win32' is true on ALL Windows (32-bit AND 64-bit).
const isWin = process.platform === 'win32';

// Local standalone Python (downloaded on demand by install-backend.mjs).
const LOCAL_PYTHON_BIN = resolve(
  isWin
    ? join('backend', '.python-local', 'python', 'python.exe')
    : join('backend', '.python-local', 'python', 'bin', 'python3'),
);

const REQUIRED = {
  node: { major: 20, minor: 0, label: 'Node.js 20+' },
  npm: { major: 9, minor: 0, label: 'npm 9+' },
  python: { major: 3, minor: 12, label: 'Python 3.12 or 3.13' },
};
const PYTHON_MAX_MINOR = 13;

const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED = '\x1b[31m';
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';
const RESET = '\x1b[0m';

const results = [];

function record(name, status, found, required, hint) {
  results.push({ name, status, found, required, hint });
}

function cmp(major, minor, req) {
  if (major > req.major) return 'ok';
  if (major < req.major) return 'fail';
  if (minor < req.minor) return 'fail';
  return 'ok';
}

function cmpPython(major, minor) {
  if (major < 3) return 'fail';
  if (major === 3 && minor < REQUIRED.python.minor) return 'fail';
  if (major === 3 && minor > PYTHON_MAX_MINOR) return 'fail';
  return 'ok';
}

// --- Node ---
{
  const [maj, min] = process.versions.node.split('.').map(Number);
  const status = cmp(maj, min, REQUIRED.node);
  record(
    'Node.js',
    status,
    `${process.versions.node}`,
    REQUIRED.node.label,
    'Install from https://nodejs.org/ or via nvm / nvm-windows',
  );
}

// --- npm ---
{
  // npm.cmd is a batch file — needs shell on Windows. Use single-string form
  // to avoid DEP0190 ("args + shell: true" deprecation).
  const r = isWin
    ? spawnSync('npm.cmd --version', { stdio: 'pipe', shell: true, encoding: 'utf8' })
    : spawnSync('npm', ['--version'], { stdio: 'pipe', encoding: 'utf8' });
  if (r.error || r.status !== 0) {
    record('npm', 'fail', 'not found', REQUIRED.npm.label, 'npm ships with Node.js — reinstall Node.js');
  } else {
    const version = (r.stdout || '').trim();
    const [maj, min] = version.split('.').map(Number);
    const status = cmp(maj, min, REQUIRED.npm);
    record('npm', status, version, REQUIRED.npm.label, 'Upgrade with: npm install -g npm');
  }
}

// --- Python ---
{
  const candidates = isWin
    ? [['py', ['-3.13']], ['py', ['-3.12']], ['py', ['-3']], ['python', []], ['python3', []]]
    : [['python3.13', []], ['python3.12', []], ['python3', []], ['python', []]];

  // If a local standalone Python was already downloaded, count it as found.
  if (existsSync(LOCAL_PYTHON_BIN)) {
    candidates.unshift([LOCAL_PYTHON_BIN, []]);
  }

  let found = null;
  for (const [cmd, baseArgs] of candidates) {
    const r = spawnSync(cmd, [...baseArgs, '--version'], {
      stdio: 'pipe',
      encoding: 'utf8',
    });
    if (r.error || r.status !== 0) continue;
    const out = (r.stdout || '') + (r.stderr || '');
    const m = out.match(/Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i);
    if (!m) continue;
    const major = Number(m[1]);
    const minor = Number(m[2]);
    if (major < 3) continue;
    const isStandalone = cmd === LOCAL_PYTHON_BIN;
    found = {
      cmd: isStandalone ? 'local standalone' : `${cmd}${baseArgs.length ? ' ' + baseArgs.join(' ') : ''}`,
      major,
      minor,
      patch: m[3] ? Number(m[3]) : 0,
    };
    break;
  }

  if (!found) {
    record(
      'Python',
      'fail',
      'not found',
      REQUIRED.python.label,
      isWin
        ? 'Install from https://www.python.org/downloads/ and tick "Add Python to PATH"'
        : 'macOS: brew install python@3.12   |   Linux: sudo apt install python3.12 python3.12-venv',
    );
  } else {
    const status = cmpPython(found.major, found.minor);
    const tooNew = found.major === 3 && found.minor > PYTHON_MAX_MINOR;
    record(
      'Python',
      status,
      `${found.major}.${found.minor}.${found.patch} (${found.cmd})`,
      REQUIRED.python.label,
      tooNew
        ? `Python ${found.major}.${found.minor} is too new — many ML packages lack prebuilt wheels. Install 3.12 or 3.13.`
        : 'Install Python 3.12 or 3.13 from https://www.python.org/downloads/',
    );
  }
}

// --- Report ---
console.log(`\n${BOLD}Jarvis — preflight check${RESET}\n`);

const icon = { ok: `${GREEN}✓${RESET}`, warn: `${YELLOW}!${RESET}`, fail: `${RED}✗${RESET}` };
const maxName = Math.max(...results.map((r) => r.name.length));

for (const r of results) {
  const name = r.name.padEnd(maxName);
  const foundStr = r.status === 'fail' ? `${RED}${r.found}${RESET}` : r.found;
  console.log(`  ${icon[r.status]}  ${BOLD}${name}${RESET}  ${foundStr}  ${DIM}(need: ${r.required})${RESET}`);
  if (r.status !== 'ok') {
    console.log(`     ${DIM}→ ${r.hint}${RESET}`);
  }
}

// Python failures are non-blocking — install:backend can auto-download Python
const failed = results.filter((r) => r.status === 'fail' && r.name !== 'Python');
const pythonFailed = results.find((r) => r.status === 'fail' && r.name === 'Python');
const warned = results.filter((r) => r.status === 'warn');

console.log();
if (failed.length > 0) {
  console.log(`${RED}${BOLD}Preflight failed.${RESET} Fix the issues above and run again.`);
  console.log(`${DIM}See README.md → Requirements for install instructions.${RESET}\n`);
  process.exit(1);
}
if (pythonFailed) {
  console.log(`${YELLOW}Python issue detected${RESET} — the install step will offer to download it locally.\n`);
} else if (warned.length > 0) {
  console.log(`${YELLOW}Preflight passed with warnings.${RESET} Proceeding…\n`);
} else {
  console.log(`${GREEN}${BOLD}All checks passed.${RESET} Proceeding…\n`);
}

// ── Configure git hooks (repo-local, no global side-effects) ──
{
  const hooksDir = join(import.meta.dirname, '..', '.githooks');
  if (existsSync(hooksDir)) {
    const r = spawnSync('git', ['config', 'core.hooksPath', '.githooks'], {
      cwd: join(import.meta.dirname, '..'),
      stdio: 'ignore',
    });
    if (r.status === 0) {
      console.log(`${DIM}Git hooks configured (.githooks/)${RESET}`);
    }
  }
}
