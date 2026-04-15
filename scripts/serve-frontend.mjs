import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const serverEntry = join('frontend', '.output', 'server', 'index.mjs');
if (!existsSync(serverEntry)) {
  console.error(`[serve-frontend] ${serverEntry} not found. Run "npm run build" first.`);
  process.exit(1);
}

const isWin = process.platform === 'win32';
const child = spawn(process.execPath, [serverEntry], {
  stdio: 'inherit',
  shell: isWin,
  env: {
    ...process.env,
    NITRO_PORT: process.env.NITRO_PORT || '3000',
    NITRO_HOST: process.env.NITRO_HOST || '127.0.0.1',
  },
});

const forward = (sig) => () => child.kill(sig);
process.on('SIGINT', forward('SIGINT'));
process.on('SIGTERM', forward('SIGTERM'));
child.on('exit', (code) => process.exit(code ?? 0));
