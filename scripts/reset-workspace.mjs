/**
 * reset-workspace.mjs
 *
 * Deletes Jarvis workspace data without touching the source code or config.
 *
 * Usage:
 *   node scripts/reset-workspace.mjs <target>
 *
 * Targets:
 *   all       — delete everything (database + memory + sessions + graph + agents + cache)
 *               requires typing "yes" in the terminal to confirm
 *   db        — delete jarvis.db only
 *   memory    — delete memory/ folder
 *   sessions  — delete app/sessions/ folder
 *   graph     — delete graph/ folder
 *   agents    — delete agents/ folder
 *   cache     — delete app/cache/ folder
 *
 * Workspace path: JARVIS_WORKSPACE_PATH env var (default: ~/Jarvis)
 */

import { rm, access } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { homedir } from 'node:os';
import { join } from 'node:path';const RED    = '\x1b[31m';
const YELLOW = '\x1b[33m';
const GREEN  = '\x1b[32m';
const CYAN   = '\x1b[36m';
const BOLD   = '\x1b[1m';
const DIM    = '\x1b[2m';
const RESET  = '\x1b[0m';

const DEFAULT_WORKSPACE = join(homedir(), 'Jarvis');
const workspace = process.env.JARVIS_WORKSPACE_PATH || DEFAULT_WORKSPACE;

const TARGETS = {
  db: {
    paths:       [
      join(workspace, 'app', 'jarvis.db'),
      join(workspace, 'app', 'jarvis.db-shm'),
      join(workspace, 'app', 'jarvis.db-wal'),
    ],
    label:       'Database',
    description: 'SQLite index — will be rebuilt on next ingest',
    isFile:      true,
  },
  memory: {
    paths:       [join(workspace, 'memory')],
    label:       'Memory',
    description: 'All Markdown notes, sources, preferences, examples',
  },
  sessions: {
    paths:       [join(workspace, 'app', 'sessions')],
    label:       'Sessions',
    description: 'Chat session history (JSON files)',
  },
  graph: {
    paths:       [join(workspace, 'graph')],
    label:       'Graph',
    description: 'knowledge graph data (graph.json + reports)',
  },
  agents: {
    paths:       [join(workspace, 'agents')],
    label:       'Agents / Specialists',
    description: 'Specialist definitions (JSON)',
  },
  cache: {
    paths:       [join(workspace, 'app', 'cache')],
    label:       'Cache',
    description: 'Retrieval cache',
  },
  preferences: {
    paths:       [join(workspace, 'app', 'preferences.json')],
    label:       'Preferences',
    description: 'User preferences (Sharpen toggle, battery, etc.)',
    isFile:      true,
  },
};

async function exists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

async function deleteTarget(key) {
  const t = TARGETS[key];
  let removed = 0;
  for (const p of t.paths) {
    if (!(await exists(p))) {
      console.log(`  ${DIM}${t.label}: not found — skipping (${p})${RESET}`);
      continue;
    }
    await rm(p, { recursive: true, force: true });
    console.log(`  ${GREEN}✓${RESET} ${BOLD}${t.label}${RESET} removed  ${DIM}(${p})${RESET}`);
    removed++;
  }
  return removed;
}

async function confirm(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => {
    rl.question(question, answer => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

/**
 * Detect whether the Jarvis backend is currently serving on the dev port.
 * We use a short-timeout fetch to /api/memory/ingest/status because that
 * route requires no auth and is idempotent. Any successful HTTP response
 * (even a 404) means a server is bound to the port.
 */
async function isBackendRunning() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 400);
  try {
    const res = await fetch('http://127.0.0.1:8000/api/memory/ingest/status', {
      signal: controller.signal,
    });
    return res.status > 0;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  const target = process.argv[2];

  if (!target || !['all', ...Object.keys(TARGETS)].includes(target)) {
    console.error(`${YELLOW}Usage: node scripts/reset-workspace.mjs <target>${RESET}`);
    console.error(`Targets: all | ${Object.keys(TARGETS).join(' | ')}`);
    process.exit(1);
  }

  // Refuse to wipe the workspace while the backend is running — otherwise
  // any in-flight ingest/embedding/Smart-Connect job will crash with
  // FileNotFoundError, leaving the database in a half-written state.
  const backendUp = await isBackendRunning();
  if (backendUp && !process.argv.includes('--force')) {
    console.error();
    console.error(`${RED}${BOLD}✗  Jarvis backend is running on http://127.0.0.1:8000${RESET}`);
    console.error(`${DIM}   Wiping data while it's up corrupts in-flight ingests.${RESET}`);
    console.error();
    console.error(`   1. Stop the dev server (Ctrl+C in the ${CYAN}npm start${RESET} terminal)`);
    console.error(`   2. Re-run this command`);
    console.error();
    console.error(`${DIM}   (Bypass with --force if you know what you're doing.)${RESET}`);
    console.error();
    process.exit(2);
  }

  console.log();
  console.log(`${CYAN}${BOLD}Jarvis workspace reset${RESET}  ${DIM}(${workspace})${RESET}`);
  console.log(`${DIM}${'─'.repeat(60)}${RESET}`);

  if (target === 'all') {
    console.log();
    console.log(`${RED}${BOLD}⚠  This will permanently delete:${RESET}`);
    for (const [key, t] of Object.entries(TARGETS)) {
      console.log(`   ${BOLD}${t.label}${RESET}  ${DIM}— ${t.description}${RESET}`);
    }
    console.log();
    console.log(`${DIM}Workspace: ${workspace}${RESET}`);
    console.log();

    const answer = await confirm(
      `${YELLOW}${BOLD}Type "yes" to confirm, or anything else to cancel: ${RESET}`
    );

    if (answer !== 'yes') {
      console.log(`\n${DIM}Cancelled — nothing was deleted.${RESET}\n`);
      process.exit(0);
    }

    console.log();
    let total = 0;
    for (const key of Object.keys(TARGETS)) {
      total += await deleteTarget(key);
    }
    console.log();
    if (total === 0) {
      console.log(`${DIM}Nothing found to delete — workspace was already clean.${RESET}`);
    } else {
      console.log(`${GREEN}${BOLD}Done.${RESET} Workspace cleared. Run ${CYAN}npm start${RESET} to create a fresh one.`);
    }
  } else {
    const t = TARGETS[target];
    console.log(`\nRemoving: ${BOLD}${t.label}${RESET}  ${DIM}— ${t.description}${RESET}\n`);
    const removed = await deleteTarget(target);
    console.log();
    if (removed === 0) {
      console.log(`${DIM}Nothing found to delete.${RESET}`);
    } else {
      console.log(`${GREEN}${BOLD}Done.${RESET}`);
    }
  }

  console.log();
}

main().catch(err => {
  console.error(`${RED}Error: ${err.message}${RESET}`);
  process.exit(1);
});
