import { spawn } from 'node:child_process';

const isWin = process.platform === 'win32';
const npm = isWin ? 'npm.cmd' : 'npm';

const procs = [
  { name: 'backend', color: '\x1b[36m', child: null },
  { name: 'frontend', color: '\x1b[35m', child: null },
];
const reset = '\x1b[0m';

procs[0].child = spawn(npm, ['run', 'serve:backend'], { stdio: 'inherit', shell: isWin });
procs[1].child = spawn(npm, ['run', 'serve:frontend'], { stdio: 'inherit', shell: isWin });

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const p of procs) {
    if (p.child && p.child.exitCode === null) {
      try {
        p.child.kill(isWin ? undefined : 'SIGINT');
      } catch {}
    }
  }
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

let exited = 0;
for (const p of procs) {
  p.child.on('exit', (code) => {
    console.log(`${p.color}[${p.name}]${reset} exited with code ${code}`);
    exited++;
    shutdown();
    if (exited === procs.length) process.exit(code ?? 0);
  });
  p.child.on('error', (err) => {
    console.error(`${p.color}[${p.name}]${reset} failed to start: ${err.message}`);
    shutdown();
    process.exit(1);
  });
}
