import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

export const CONFIG_PATH = path.join(ROOT, 'control.config.json');
export const EXAMPLE_PATH = path.join(ROOT, 'control.config.example.json');
export const TOKEN_PATH = path.join(ROOT, '.control-token');

/**
 * Load and validate the control config, resolving all paths to absolute.
 * Exits with a helpful message if the config is missing or malformed.
 */
export function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    console.error(
      `\n[!] Config not found: ${CONFIG_PATH}\n` +
        `    Run "npm run init" to create it from the example, then edit it.\n`
    );
    process.exit(1);
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  } catch (err) {
    console.error(`\n[!] Could not parse ${CONFIG_PATH}: ${err.message}\n`);
    process.exit(1);
  }

  const projectRoot = path.resolve(ROOT, raw.projectRoot || '.');

  const normalizeTask = (t, kind) => {
    if (!t.id || !t.command) {
      throw new Error(`Each ${kind} needs an "id" and a "command".`);
    }
    return {
      id: String(t.id),
      name: t.name || t.id,
      command: t.command,
      args: Array.isArray(t.args) ? t.args.map(String) : [],
      cwd: t.cwd ? path.resolve(projectRoot, t.cwd) : projectRoot,
      autostart: kind === 'process' ? Boolean(t.autostart) : false,
    };
  };

  return {
    projectRoot,
    port: Number(raw.port) || 4477,
    host: raw.host || '0.0.0.0',
    processes: (raw.processes || []).map((p) => normalizeTask(p, 'process')),
    commands: (raw.commands || []).map((c) => normalizeTask(c, 'command')),
  };
}

/**
 * Load an existing access token or generate + persist a new one.
 * The token gates every API call and the WebSocket stream.
 */
export function loadOrCreateToken() {
  if (process.env.CONTROL_TOKEN) return process.env.CONTROL_TOKEN.trim();
  if (fs.existsSync(TOKEN_PATH)) {
    const t = fs.readFileSync(TOKEN_PATH, 'utf8').trim();
    if (t) return t;
  }
  const token = crypto.randomBytes(24).toString('base64url');
  fs.writeFileSync(TOKEN_PATH, token + '\n', { mode: 0o600 });
  return token;
}

/** Create control.config.json from the example if it doesn't exist yet. */
export function initConfig() {
  if (fs.existsSync(CONFIG_PATH)) {
    console.log(`Config already exists: ${CONFIG_PATH}`);
    return;
  }
  fs.copyFileSync(EXAMPLE_PATH, CONFIG_PATH);
  console.log(`Created ${CONFIG_PATH} from example. Edit it for your project.`);
}
