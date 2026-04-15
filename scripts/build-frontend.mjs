import { spawnSync } from 'node:child_process';

const isWin = process.platform === 'win32';
const npm = isWin ? 'npm.cmd' : 'npm';

console.log('[build-frontend] running nuxt build');
const r = spawnSync(npm, ['--prefix', 'frontend', 'run', 'build'], {
  stdio: 'inherit',
  shell: isWin,
});
if (r.error) {
  console.error(`[build-frontend] failed: ${r.error.message}`);
  process.exit(1);
}
process.exit(r.status ?? 0);
