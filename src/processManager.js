import { spawn } from 'node:child_process';
import { EventEmitter } from 'node:events';

const MAX_LOG_LINES = 500;

/**
 * Tracks the runtime state of one configured process or command.
 * A "process" is long-running (start/stop); a "command" is one-shot (run).
 */
class ManagedTask {
  constructor(def, kind) {
    this.def = def;
    this.kind = kind; // 'process' | 'command'
    this.child = null;
    this.status = 'stopped'; // stopped | running | exited | error
    this.exitCode = null;
    this.startedAt = null;
    this.log = []; // recent output lines (ring buffer)
  }

  get running() {
    return this.child !== null;
  }

  snapshot() {
    return {
      id: this.def.id,
      name: this.def.name,
      kind: this.kind,
      command: `${this.def.command} ${this.def.args.join(' ')}`.trim(),
      status: this.status,
      exitCode: this.exitCode,
      startedAt: this.startedAt,
      running: this.running,
    };
  }
}

export class ProcessManager extends EventEmitter {
  constructor(config) {
    super();
    this.tasks = new Map();
    for (const def of config.processes) {
      this.tasks.set(def.id, new ManagedTask(def, 'process'));
    }
    for (const def of config.commands) {
      // Namespaced so a process and command can share an id without clashing.
      this.tasks.set('cmd:' + def.id, new ManagedTask(def, 'command'));
    }
  }

  _key(id, kind) {
    return kind === 'command' ? 'cmd:' + id : id;
  }

  get(id, kind) {
    return this.tasks.get(this._key(id, kind));
  }

  list() {
    return [...this.tasks.values()].map((t) => t.snapshot());
  }

  recentLog(id, kind) {
    const t = this.get(id, kind);
    return t ? t.log : [];
  }

  _emitLine(task, stream, text) {
    for (const raw of text.split(/\r?\n/)) {
      if (raw === '') continue;
      const line = { ts: Date.now(), stream, text: raw };
      task.log.push(line);
      if (task.log.length > MAX_LOG_LINES) task.log.shift();
      this.emit('log', { id: task.def.id, kind: task.kind, line });
    }
  }

  _emitStatus(task) {
    this.emit('status', task.snapshot());
  }

  /** Start a long-running process (no-op if already running). */
  start(id) {
    const task = this.get(id, 'process');
    if (!task) return { ok: false, error: 'Unknown process: ' + id };
    if (task.running) return { ok: false, error: 'Already running' };
    return this._spawn(task);
  }

  /** Run a one-shot command (no-op if a previous run is still in flight). */
  run(id) {
    const task = this.get(id, 'command');
    if (!task) return { ok: false, error: 'Unknown command: ' + id };
    if (task.running) return { ok: false, error: 'Already running' };
    return this._spawn(task);
  }

  _spawn(task) {
    const { command, args, cwd } = task.def;
    let child;
    try {
      child = spawn(command, args, {
        cwd,
        env: process.env,
        shell: false,
      });
    } catch (err) {
      task.status = 'error';
      this._emitLine(task, 'stderr', `[spawn failed] ${err.message}`);
      this._emitStatus(task);
      return { ok: false, error: err.message };
    }

    task.child = child;
    task.status = 'running';
    task.exitCode = null;
    task.startedAt = Date.now();
    this._emitLine(task, 'system', `▶ started: ${task.def.command} ${task.def.args.join(' ')}`);
    this._emitStatus(task);

    child.stdout.on('data', (d) => this._emitLine(task, 'stdout', d.toString()));
    child.stderr.on('data', (d) => this._emitLine(task, 'stderr', d.toString()));

    child.on('error', (err) => {
      this._emitLine(task, 'stderr', `[error] ${err.message}`);
    });

    child.on('close', (code, signal) => {
      task.child = null;
      task.exitCode = code;
      task.status = signal ? 'stopped' : code === 0 ? 'exited' : 'error';
      this._emitLine(
        task,
        'system',
        signal ? `■ stopped (${signal})` : `■ exited with code ${code}`
      );
      this._emitStatus(task);
    });

    return { ok: true };
  }

  /** Gracefully stop a running process (SIGTERM, then SIGKILL after a grace period). */
  stop(id, kind = 'process') {
    const task = this.get(id, kind);
    if (!task) return { ok: false, error: 'Unknown task: ' + id };
    if (!task.running) return { ok: false, error: 'Not running' };

    const child = task.child;
    child.kill('SIGTERM');
    setTimeout(() => {
      if (task.child === child) {
        child.kill('SIGKILL');
      }
    }, 5000).unref();
    return { ok: true };
  }

  restart(id) {
    const task = this.get(id, 'process');
    if (!task) return { ok: false, error: 'Unknown process: ' + id };
    if (!task.running) return this.start(id);

    const child = task.child;
    child.once('close', () => this.start(id));
    return this.stop(id, 'process');
  }

  /** Stop everything that's still running (used on shutdown). */
  stopAll() {
    for (const task of this.tasks.values()) {
      if (task.running) task.child.kill('SIGTERM');
    }
  }

  autostart() {
    for (const task of this.tasks.values()) {
      if (task.kind === 'process' && task.def.autostart) this._spawn(task);
    }
  }
}
