'use strict';

const $ = (sel) => document.querySelector(sel);
const state = {
  token: null,
  ws: null,
  tasks: [],
  selectedLog: null, // "kind:id"
  logs: {}, // "kind:id" -> array of lines
};

// ---------- auth ----------
function saveToken(t) {
  state.token = t;
  try {
    localStorage.setItem('control.token', t);
  } catch {}
}
function loadToken() {
  const url = new URL(location.href);
  const fromUrl = url.searchParams.get('token');
  if (fromUrl) {
    // Clean the token out of the address bar after grabbing it.
    url.searchParams.delete('token');
    history.replaceState({}, '', url.pathname + url.search);
    return fromUrl;
  }
  try {
    return localStorage.getItem('control.token') || '';
  } catch {
    return '';
  }
}

async function api(path, method = 'GET') {
  const res = await fetch('/api' + path, {
    method,
    headers: { Authorization: 'Bearer ' + state.token },
  });
  if (res.status === 401) throw new Error('unauthorized');
  return res.json();
}

// ---------- boot ----------
async function connect(token) {
  state.token = token;
  const cfg = await api('/config'); // throws on 401
  saveToken(token);
  state.tasks = cfg.tasks;
  $('#login').hidden = true;
  $('#dashboard').hidden = false;
  render();
  openSocket();
}

$('#connectBtn').addEventListener('click', async () => {
  const t = $('#token').value.trim();
  const err = $('#loginError');
  err.hidden = true;
  if (!t) return;
  try {
    await connect(t);
  } catch (e) {
    err.textContent = '연결 실패: 토큰을 확인하세요.';
    err.hidden = false;
  }
});
$('#token').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('#connectBtn').click();
});

$('#logoutBtn').addEventListener('click', () => {
  try {
    localStorage.removeItem('control.token');
  } catch {}
  if (state.ws) state.ws.close();
  location.reload();
});

$('#clearLog').addEventListener('click', () => {
  if (state.selectedLog) state.logs[state.selectedLog] = [];
  renderLog();
});
$('#logSelect').addEventListener('change', (e) => {
  state.selectedLog = e.target.value;
  loadLogHistory(state.selectedLog);
});

// ---------- websocket ----------
function openSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(state.token)}`);
  state.ws = ws;

  ws.onopen = () => setConn(true);
  ws.onclose = () => {
    setConn(false);
    setTimeout(() => {
      if (state.token && !$('#dashboard').hidden) openSocket();
    }, 2000);
  };
  ws.onmessage = (ev) => {
    const { type, payload } = JSON.parse(ev.data);
    if (type === 'snapshot') {
      state.tasks = payload;
      render();
    } else if (type === 'status') {
      const i = state.tasks.findIndex((t) => t.id === payload.id && t.kind === payload.kind);
      if (i >= 0) state.tasks[i] = payload;
      renderCards();
    } else if (type === 'log') {
      appendLog(payload.kind, payload.id, payload.line);
    }
  };
}

function setConn(up) {
  const el = $('#conn');
  el.classList.toggle('up', up);
  el.title = up ? 'connected' : 'disconnected';
}

// ---------- actions ----------
async function act(path) {
  try {
    const r = await api(path, 'POST');
    if (!r.ok && r.error) flash(r.error);
  } catch {
    flash('요청 실패');
  }
}
function flash(msg) {
  // Lightweight, non-blocking: surface errors in the log view.
  const line = { ts: Date.now(), stream: 'stderr', text: '[ui] ' + msg };
  if (state.selectedLog) appendLog(...state.selectedLog.split(/:(.+)/), line, true);
}

// ---------- rendering ----------
function render() {
  renderCards();
  renderLogSelect();
  renderLog();
}

function badge(t) {
  const cls = t.running ? 'running' : t.status;
  const label = t.running ? 'RUNNING' : (t.status || 'stopped').toUpperCase();
  return `<span class="badge ${cls}">${label}</span>`;
}

function renderCards() {
  const procs = state.tasks.filter((t) => t.kind === 'process');
  const cmds = state.tasks.filter((t) => t.kind === 'command');

  $('#processes').innerHTML = procs.length
    ? procs.map(processCard).join('')
    : '<p class="muted">설정된 프로세스가 없습니다.</p>';
  $('#commands').innerHTML = cmds.length
    ? cmds.map(commandCard).join('')
    : '<p class="muted">설정된 명령이 없습니다.</p>';

  bindCardButtons();
}

function processCard(t) {
  const running = t.running;
  return `
    <div class="card">
      <div class="card-top">
        <div>
          <div class="card-name">${esc(t.name)}</div>
          <div class="card-cmd">${esc(t.command)}</div>
        </div>
        ${badge(t)}
      </div>
      <div class="actions">
        <button class="btn-start" data-act="/process/${t.id}/start" ${running ? 'disabled' : ''}>시작</button>
        <button class="btn-stop" data-act="/process/${t.id}/stop" ${running ? '' : 'disabled'}>중지</button>
        <button class="btn-restart" data-act="/process/${t.id}/restart">재시작</button>
      </div>
    </div>`;
}

function commandCard(t) {
  return `
    <div class="card">
      <div class="card-top">
        <div>
          <div class="card-name">${esc(t.name)}</div>
          <div class="card-cmd">${esc(t.command)}</div>
        </div>
        ${badge(t)}
      </div>
      <div class="actions">
        <button class="btn-run" data-act="/command/${t.id}/run" ${t.running ? 'disabled' : ''}>실행</button>
      </div>
    </div>`;
}

function bindCardButtons() {
  document.querySelectorAll('[data-act]').forEach((btn) => {
    btn.addEventListener('click', () => act(btn.dataset.act));
  });
}

function renderLogSelect() {
  const sel = $('#logSelect');
  sel.innerHTML = state.tasks
    .map((t) => `<option value="${t.kind}:${t.id}">${esc(t.name)}</option>`)
    .join('');
  if (!state.selectedLog && state.tasks.length) {
    state.selectedLog = `${state.tasks[0].kind}:${state.tasks[0].id}`;
    loadLogHistory(state.selectedLog);
  }
  if (state.selectedLog) sel.value = state.selectedLog;
}

async function loadLogHistory(key) {
  const [kind, id] = key.split(/:(.+)/);
  try {
    const r = await api(`/log/${kind}/${id}`);
    state.logs[key] = r.log || [];
  } catch {
    state.logs[key] = [];
  }
  renderLog();
}

function appendLog(kind, id, line, isUi = false) {
  const key = `${kind}:${id}`;
  (state.logs[key] ||= []).push(line);
  if (state.logs[key].length > 800) state.logs[key].shift();
  if (key === state.selectedLog) renderLog();
}

function renderLog() {
  const view = $('#logView');
  const lines = state.selectedLog ? state.logs[state.selectedLog] || [] : [];
  const nearBottom = view.scrollTop + view.clientHeight >= view.scrollHeight - 40;
  view.innerHTML = lines
    .map((l) => {
      const ts = new Date(l.ts).toLocaleTimeString();
      return `<span class="${l.stream}"><span class="ts">${ts}</span>  ${esc(l.text)}</span>`;
    })
    .join('\n');
  if (nearBottom) view.scrollTop = view.scrollHeight;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------- auto-login ----------
(async function init() {
  const t = loadToken();
  if (t) {
    $('#token').value = t;
    try {
      await connect(t);
    } catch {
      /* fall back to login screen */
    }
  }
})();
