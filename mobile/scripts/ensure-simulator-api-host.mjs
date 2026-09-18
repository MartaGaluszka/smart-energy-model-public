#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const out = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src/environments/simulator-api-host.ts');
if (!fs.existsSync(out)) {
  fs.writeFileSync(
    out,
    `/** Placeholder — npm run build:sim nadpisze IP LAN Maca */
export const SIMULATOR_API_ORIGIN: string | null = null;
`,
    'utf8',
  );
}
