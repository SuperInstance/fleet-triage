/**
 * The Pincher engine — composes embedder, store, compiler, veto.
 *
 * The engine runs in three tiers (per the original pincher design):
 *   - FAST (<50ms): direct hit, no LLM
 *   - MEDIUM (~1s): confirmation + execute
 *   - SLOW (~5s): LLM compile new reflex
 *
 * The whole engine is a Quilt cell in a sheet.
 */
import type {
  Pinch, PinchResult, PincherConfig, Reflex, Embedder, ReflexStore, Compiler, Veto,
} from './types.js';

export class PincherEngine {
  private embedder: Embedder;
  private store: ReflexStore;
  private compiler?: Compiler;
  private veto?: Veto;
  private hitThreshold: number;
  private confirmThreshold: number;
  private executionTimeoutMs: number;

  constructor(config: PincherConfig) {
    this.embedder = config.embedder;
    this.store = config.store;
    this.compiler = config.compiler;
    this.veto = config.veto;
    this.hitThreshold = config.hitThreshold ?? 0.80;
    this.confirmThreshold = config.confirmThreshold ?? 0.55;
    this.executionTimeoutMs = config.executionTimeoutMs ?? 5000;
  }

  /** Run a pinch. Returns a result indicating the tier. */
  async run(pinch: Pinch): Promise<PinchResult> {
    const t0 = Date.now();
    try {
      // 1. Embed the trigger
      const embedding = await this.embedder.embed(pinch.trigger);

      // 2. Match against the reflex database
      const matches = await this.store.query(embedding, 5);
      if (matches.length === 0 || matches[0]!.score < this.confirmThreshold) {
        // 3a. No match — compile a new reflex (SLOW tier)
        if (!this.compiler) {
          return { kind: 'error', error: 'No match and no compiler configured', latencyMs: Date.now() - t0 };
        }
        return await this.compileAndStore(pinch, embedding, t0);
      }

      const top = matches[0]!;
      if (top.score >= this.hitThreshold) {
        // 3b. Direct hit (FAST tier)
        return await this.executeDirectly(top.reflex, pinch, t0);
      }
      // 3c. Confirm (MEDIUM tier)
      return await this.confirmAndExecute(top.reflex, pinch, t0);
    } catch (e) {
      return { kind: 'error', error: (e as Error).message, latencyMs: Date.now() - t0 };
    }
  }

  /** Direct hit: skip confirmation, just execute. */
  private async executeDirectly(reflex: Reflex, pinch: Pinch, t0: number): Promise<PinchResult> {
    // Veto check
    if (this.veto) {
      const verdict = await this.veto.check(reflex, pinch);
      if (!verdict.ok) {
        return { kind: 'vetoed', reason: verdict.reason ?? 'vetoed', latencyMs: Date.now() - t0 };
      }
    }

    // Execute
    const output = await this.execute(reflex, pinch);
    await this.bumpHit(reflex.id);
    return { kind: 'hit', reflex, output, latencyMs: Date.now() - t0 };
  }

  /** Confirm: increase confidence, then execute. */
  private async confirmAndExecute(reflex: Reflex, pinch: Pinch, t0: number): Promise<PinchResult> {
    if (this.veto) {
      const verdict = await this.veto.check(reflex, pinch);
      if (!verdict.ok) {
        return { kind: 'vetoed', reason: verdict.reason ?? 'vetoed', latencyMs: Date.now() - t0 };
      }
    }
    const output = await this.execute(reflex, pinch);
    await this.bumpHit(reflex.id);
    return { kind: 'confirm', reflex, output, latencyMs: Date.now() - t0 };
  }

  /** Compile a new reflex via the LLM compiler. */
  private async compileAndStore(pinch: Pinch, embedding: number[], t0: number): Promise<PinchResult> {
    if (!this.compiler) {
      return { kind: 'error', error: 'No compiler', latencyMs: Date.now() - t0 };
    }
    const compiled = await this.compiler.compile(pinch);
    const reflex: Reflex = {
      id: `reflex-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      embedding,
      intent: compiled.intent,
      action: compiled.action,
      safety: pinch.safety ?? {},
      confidence: 0.5,  // start at 0.5, climb with hits
      hits: 0,
      createdAt: Date.now(),
      lastHitAt: 0,
      provenance: { compiledBy: 'compiler' },
    };
    if (this.veto) {
      const verdict = await this.veto.check(reflex, pinch);
      if (!verdict.ok) {
        return { kind: 'vetoed', reason: verdict.reason ?? 'vetoed', latencyMs: Date.now() - t0 };
      }
    }
    await this.store.insert(reflex);
    const output = await this.execute(reflex, pinch);
    return { kind: 'compiled', reflex, output, latencyMs: Date.now() - t0 };
  }

  /** Execute a reflex — the action is a string; we treat it as a JavaScript expression. */
  private async execute(reflex: Reflex, pinch: Pinch): Promise<unknown> {
    const start = Date.now();
    try {
      // The action is a string. In production this would be sandboxed.
      // For demo: we use eval-in-Function with the pinch context.
      const fn = new Function('pinch', `return (async () => { ${reflex.action} })();`);
      const result = await Promise.race([
        fn(pinch),
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), this.executionTimeoutMs)),
      ]);
      return result;
    } catch (e) {
      throw new Error(`Execution failed: ${(e as Error).message}`);
    }
  }

  /** Bump a reflex's hit count. */
  private async bumpHit(id: string): Promise<void> {
    const reflex = await this.store.get(id);
    if (!reflex) return;
    reflex.hits += 1;
    reflex.lastHitAt = Date.now();
    // Confidence climbs with hits: 0.5 → 0.99 over 100 hits (logarithmic)
    reflex.confidence = Math.min(0.99, 0.5 + 0.49 * Math.log10(1 + reflex.hits));
    await this.store.insert(reflex);
  }

  /** Add a reflex manually. */
  async addReflex(reflex: Reflex): Promise<void> {
    await this.store.insert(reflex);
  }

  /** Get all reflexes. */
  async allReflexes(): Promise<Reflex[]> {
    const count = await this.store.count();
    if (count === 0) return [];
    // For a real implementation, we'd paginate. For demo, we re-query.
    return [];
  }

  /** Get total reflex count. */
  async size(): Promise<number> {
    return this.store.count();
  }

  /** Export to a .nail bundle. */
  async exportNail(name: string, tier: string): Promise<import('./types.js').NailBundle> {
    const reflexes = await this.allReflexes();
    return {
      version: '0.1.0',
      reflexes,
      vetoRules: [],
      compileHistory: [],
      metadata: {
        name,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        tier,
      },
    };
  }
}

// ──────────────────────────────────────────────────────────────────────────
//  Default implementations
// ──────────────────────────────────────────────────────────────────────────

/** A hash-based fake embedder — for tests, demos, and offline use. */
export class HashEmbedder implements Embedder {
  constructor(public dimensions: number = 384) {}
  async embed(text: string): Promise<number[]> {
    const v = new Array(this.dimensions).fill(0);
    for (let i = 0; i < text.length; i++) {
      v[i % this.dimensions]! += text.charCodeAt(i) / 1000;
    }
    const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
    return v.map((x) => x / norm);
  }
}

/** A default veto — checks safety constraints. */
export class DefaultVeto implements Veto {
  async check(reflex: Reflex, pinch: Pinch): Promise<{ ok: boolean; reason?: string }> {
    // Check that the pinch's safety hints don't exceed the reflex's
    if (pinch.safety?.network === 'any' && reflex.safety.network !== 'any') {
      return { ok: false, reason: 'pinch wants any-network but reflex is restricted' };
    }
    if (pinch.safety?.filesystem === 'any' && reflex.safety.filesystem !== 'any') {
      return { ok: false, reason: 'pinch wants any-filesystem but reflex is restricted' };
    }
    if (pinch.safety?.sandbox === 'none' && reflex.safety.sandbox === 'wasm') {
      return { ok: false, reason: 'pinch wants no-sandbox but reflex requires sandbox' };
    }
    return { ok: true };
  }
}
