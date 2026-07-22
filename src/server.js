#!/usr/bin/env node
import http from 'node:http';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { WebSocketServer } from 'ws';

import { loadConfig, loadOrCreateToken, initConfig } from './config.js';
import { ProcessManager } from './processManager.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');

if (process.argv.includes('--init')) {
  initConfig();
  process.exit(0);
}

const config = loadConfig();
const TOKEN = loadOrCreateToken();
const manager = new ProcessManager(config);

/** Constant-time token comparison to avoid timing leaks. */
function tokenValid(candidate) {
  if (typeof candidate !== 'string' || candidate.length === 0) return false;
  const a = Buffer.from(candidate);
  const b = Buffer.from(TOKEN);
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function extractToken(req) {
  const header = req.headers['authorization'];
  if (header && header.startsWith('Bearer ')) return header.slice(7).trim();
  if (req.query && req.query.token) return String(req.query.token);
  return null;
}

const app = express();
app.use(express.json());

// The login page and its assets are public; everything under /api requires a token.
app.use((req, res, next) => {
  if (!req.path.startsWith('/api/')) return next();
  if (tokenValid(extractToken(req))) return next();
  res.status(401).json({ ok: false, error: 'Unauthorized' });
});

app.get('/api/health', (_req, res) => res.json({ ok: true }));

app.get('/api/config', (_req, res) => {
  res.json({
    ok: true,
    projectRoot: config.projectRoot,
    tasks: manager.list(),
  });
});

app.get('/api/log/:kind/:id', (req, res) => {
  const { kind, id } = req.params;
  res.json({ ok: true, log: manager.recentLog(id, kind) });
});

app.post('/api/process/:id/start', (req, res) => res.json(manager.start(req.params.id)));
app.post('/api/process/:id/stop', (req, res) => res.json(manager.stop(req.params.id)));
app.post('/api/process/:id/restart', (req, res) => res.json(manager.restart(req.params.id)));
app.post('/api/command/:id/run', (req, res) => res.json(manager.run(req.params.id)));

app.use(express.static(PUBLIC_DIR));

const server = http.createServer(app);

// --- WebSocket: live log + status stream ---
const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (req, socket, head) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname !== '/ws') {
    socket.destroy();
    return;
  }
  if (!tokenValid(url.searchParams.get('token'))) {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => wss.emit('connection', ws, req));
});

function broadcast(type, payload) {
  const msg = JSON.stringify({ type, payload });
  for (const client of wss.clients) {
    if (client.readyState === 1) client.send(msg);
  }
}

manager.on('log', (e) => broadcast('log', e));
manager.on('status', (s) => broadcast('status', s));

wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'snapshot', payload: manager.list() }));
});

// --- boot ---
manager.autostart();

server.listen(config.port, config.host, () => {
  printBanner();
});

function localIPs() {
  const out = [];
  for (const nets of Object.values(os.networkInterfaces())) {
    for (const net of nets || []) {
      if (net.family === 'IPv4' && !net.internal) out.push(net.address);
    }
  }
  return out;
}

function printBanner() {
  const ips = localIPs();
  const lan = ips[0] || 'localhost';
  console.log('\n  productmaker control panel is running');
  console.log('  ─────────────────────────────────────');
  console.log(`  Project root : ${config.projectRoot}`);
  console.log(`  This device  : http://localhost:${config.port}`);
  if (ips.length) {
    console.log('  From phone   : (same Wi-Fi) open one of these');
    for (const ip of ips) console.log(`                 http://${ip}:${config.port}`);
  }
  console.log('\n  Access token (enter this on your phone):');
  console.log(`      ${TOKEN}`);
  console.log('\n  Quick-open link with token embedded:');
  console.log(`      http://${lan}:${config.port}/?token=${TOKEN}`);
  console.log('\n  Ctrl+C to stop.\n');
}

function shutdown() {
  console.log('\nStopping managed processes...');
  manager.stopAll();
  setTimeout(() => process.exit(0), 500);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
