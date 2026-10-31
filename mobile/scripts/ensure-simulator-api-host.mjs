#!/usr/bin/env node
/**
 * postinstall: zawsze odśwież IP LAN Maca (Simulator → API na hoście, nie 127.0.0.1 telefonu).
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const sync = path.join(root, 'scripts', 'sync-simulator-api-host.mjs');
const out = path.join(root, 'src/environments/simulator-api-host.ts');

if (fs.existsSync(sync)) {
  const r = spawnSync(process.execPath, [sync], { cwd: root, encoding: 'utf8' });
  if (r.status === 0) {
    process.stdout.write(r.stdout ?? '');
    process.exit(0);
  }
}

if (!fs.existsSync(out)) {
  fs.writeFileSync(
    out,
    `/** Placeholder — npm run build:sim nadpisze IP LAN Maca */
export const SIMULATOR_API_ORIGIN: string | null = null;
`,
    'utf8',
  );
}
