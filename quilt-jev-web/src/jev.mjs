// quilt-jev-web :: jev.mjs
// VENDORED-DERIVED from SuperInstance/jev-quilt/jev_quilt/typesafe_client.py.
// The wire shape is the source's, cross-checked against fleet-triage/JEV-CONTRACT.md
// (which recorded the three ways the schema gets sent wrong).
// WHAT IS MINE: the failure taxonomy. The source raises RuntimeError and stops.
// The project's central failure mode is *conflating transport with schema* -- the
// contract doc says it did that for an hour and blamed the contract. So a failure
// here is one of four typed values and only one of them is worth retrying.

export const FAILURE = {
  TRANSPORT: 'TRANSPORT',   // TLS EOF, 5xx, timeout, DNS. RETRY.
  SCHEMA: 'SCHEMA',         // 4xx with a validation body. NEVER retry.
  AUTH: 'AUTH',             // 401/403. Never retry; the key is the problem.
  NOKEY: 'NOKEY',           // no key present. Not a failure, a MODE.
};
const RETRYABLE = new Set([FAILURE.TRANSPORT]);

export class JevError extends Error {
  constructor(kind, message, detail) { super(message); this.kind = kind; this.detail = detail; }
}

// Key detection is a MODE, not an error. A missing key must never be rendered
// as a field of zeros -- see synth.mjs and the banner in app.mjs.
export const keyPresent = (env = globalThis) => !!(env.TYPESAFEAI_KEY || env.TYPESAFE_API_KEY || env.JEV_API_KEY);

export class Jev {
  constructor({ base = 'https://api.typesafe.ai', key = null, fetchImpl = globalThis.fetch, timeoutMs = 30000, maxAttempts = 5 } = {}) {
    this.base = base.replace(/\/$/, '');
    this.key = key;
    this.fetch = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.maxAttempts = maxAttempts;
    this.log = [];           // the transport record, kept
  }
  get available() { return !!this.key; }

  async ask(state, questions) {
    if (!this.key) throw new JevError(FAILURE.NOKEY, 'no API key present (TYPESAFEAI_KEY / TYPESAFE_API_KEY / JEV_API_KEY)');
    // criteria values MUST be null -- the option SET is the keys. (contract §2)
    const qs = {};
    for (const q of questions) {
      qs[q.name] = {
        type: q.type || 'choice',
        instructions: q.instructions || q.question || '',
        ...(q.type === 'choice'
          ? { criteria: Object.fromEntries(q.options.map((o) => [o, null])) }
          : q.type === 'score' ? { criteria: q.rubric || ['low', 'medium', 'high'] } : {}),
      };
    }
    const body = { model: q_model, state, questions: qs };   // 'model' is REQUIRED; jev-latest is the alias (contract §1)
    return this.#withBackoff(async (attempt) => {
      const ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), this.timeoutMs);
      try {
        const r = await this.fetch(`${this.base}/v1/systemone`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.key}` },
          body: JSON.stringify(body), signal: ctl.signal,
        });
        if (r.status === 401 || r.status === 403) throw new JevError(FAILURE.AUTH, `HTTP ${r.status}: key rejected`);
        if (r.status >= 400 && r.status < 500) {
          const t = await r.text();
          throw new JevError(FAILURE.SCHEMA, `HTTP ${r.status}: ${t.slice(0, 300)}`, t);
        }
        if (!r.ok) {
          const t = await r.text().catch(() => '');
          throw new JevError(FAILURE.TRANSPORT, `HTTP ${r.status}: ${t.slice(0, 120)}`);
        }
        return { payload: await r.json(), attempt, at: new Date().toISOString() };
      } catch (e) {
        // fetch collapses TLS EOF, DNS, abort and offline into TypeError.
        if (e instanceof JevError) throw e;
        const msg = e && e.name === 'AbortError' ? `timeout after ${this.timeoutMs}ms` : (e && e.message) || String(e);
        throw new JevError(FAILURE.TRANSPORT, msg);
      } finally { clearTimeout(to); }
    });
  }

  async #withBackoff(fn) {
    let last;
    for (let attempt = 1; attempt <= this.maxAttempts; attempt++) {
      try {
        const r = await fn(attempt);
        this.log.push({ attempt, outcome: 'ok' });
        return r;
      } catch (e) {
        const kind = e instanceof JevError ? e.kind : FAILURE.TRANSPORT;
        last = e;
        this.log.push({ attempt, outcome: kind, msg: e.message });
        if (!RETRYABLE.has(kind) || attempt === this.maxAttempts) throw e;
        // full-jitter exponential backoff. 250, 500, 1000, 2000, 4000
        const wait = Math.random() * 250 * 2 ** (attempt - 1);
        await new Promise((r) => setTimeout(r, wait));
      }
    }
    throw last;
  }
}
const q_model = 'jev-latest';   // the ALIAS. 'jev-1.13.0' is the response id, not the request id.

// Response -> cell. Note that `confidence` is copied straight through and is NOT
// recomputed from probabilities. The contract's whole point: choice=grey,
// confidence=0.61, p(grey)=0.74. Deriving confidence from the map would erase
// the one field the judge says about itself.
export function answerToJudgment(name, ans) {
  if (ans.type !== 'choice') return null;
  return { judge: `jev/${name}`, at: null, confidence: ans.confidence, probabilities: ans.probabilities };
}
