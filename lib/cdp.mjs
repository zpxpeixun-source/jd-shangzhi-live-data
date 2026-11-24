const DEFAULT_PORT = 9222;

export async function listTargets(port = DEFAULT_PORT) {
  const res = await fetch(`http://127.0.0.1:${port}/json/list`);
  if (!res.ok) throw new Error(`CDP HTTP ${res.status}`);
  return res.json();
}

export async function pageTarget(port = DEFAULT_PORT, match = 'jdsz.jd.com') {
  const targets = await listTargets(port);
  const pages = targets.filter(t => t.type === 'page');
  return pages.find(t => t.url.includes(match)) || pages[0];
}

export class CDP {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 0;
    this.pending = new Map();
    this.events = [];
    this.eventWaiters = [];
  }
  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('CDP connect timeout')), 10000);
      this.ws.onopen = () => { clearTimeout(timer); resolve(); };
      this.ws.onerror = () => { clearTimeout(timer); reject(new Error('CDP websocket error')); };
    });
    this.ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject, timer } = this.pending.get(msg.id);
        clearTimeout(timer);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      } else if (msg.method) {
        this.events.push(msg);
        for (const w of [...this.eventWaiters]) {
          if (w.method === msg.method) {
            this.eventWaiters.splice(this.eventWaiters.indexOf(w), 1);
            clearTimeout(w.timer);
            w.resolve(msg.params);
          }
        }
      }
    };
    return this;
  }
  send(method, params = {}, timeoutMs = 30000) {
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression, { awaitPromise = true, returnByValue = true } = {}) {
    const r = await this.send('Runtime.evaluate', {
      expression, awaitPromise, returnByValue, userGesture: true,
    }, 60000);
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || JSON.stringify(r.exceptionDetails));
    }
    return r.result?.value;
  }
  close() { try { this.ws.close(); } catch {} }
}

export async function connectPage(port = DEFAULT_PORT, match = 'jdsz.jd.com') {
  const t = await pageTarget(port, match);
  if (!t) throw new Error('No page target found. Open and log in to jdsz.jd.com first.');
  const cdp = await new CDP(t.webSocketDebuggerUrl).connect();
  return { cdp, target: t };
}

export async function getAllCookies(port = DEFAULT_PORT) {
  const { cdp } = await connectPage(port);
  try {
    return (await cdp.send('Network.getAllCookies')).cookies;
  } finally {
    cdp.close();
  }
}

export function cookieHeader(cookies, domainSuffix = 'jd.com') {
  return cookies
    .filter(c => c.domain.endsWith(domainSuffix))
    .map(c => `${c.name}=${c.value}`)
    .join('; ');
}

export function findCookie(cookies, name) {
  return cookies.find(c => c.name === name)?.value || null;
}

export const sleep = ms => new Promise(r => setTimeout(r, ms));
