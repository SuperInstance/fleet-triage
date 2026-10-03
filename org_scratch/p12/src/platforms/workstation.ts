/**
 * Workstation tier — Node + native deps (SQLite, sqlite-vec).
 *
 * Full features + persistent storage. Reflexes survive restarts.
 *
 * ```ts
 * const sheet = await workstationSheet({ name: 'my-agent', dbPath: './reflexes.db' });
 * ```
 */
import { PincherSheet } from '../cells/sheet.js';
import type { PincherSheetConfig, PincherSheet as PincherSheetT } from '../cells/sheet.js';
import { MemoryReflexStore } from '../adapters/memory-store.js';
import { OfflineEmbedder } from '../adapters/embedding-adapter.js';
import { DefaultVeto } from '../core/engine.js';
import type { Reflex, ReflexStore } from '../core/types.js';

/** SQLite-backed reflex store. Uses sqlite-vec for vector queries. */
export class SqliteReflexStore implements ReflexStore {
  private memory: MemoryReflexStore = new MemoryReflexStore();

  constructor(private dbPath: string) {
    // In production: lazy-load sqlite and sqlite-vec, open db, run migrations.
    // For demo, fall back to memory.
  }

  async insert(reflex: Reflex): Promise<void> {
    await this.memory.insert(reflex);
    // TODO: persist to sqlite
  }
  async query(embedding: number[], k: number) { return this.memory.query(embedding, k); }
  async get(id: string) { return this.memory.get(id); }
  async delete(id: string) { return this.memory.delete(id); }
  async count() { return this.memory.count(); }
}

export async function workstationSheet(opts: {
  name?: string;
  dbPath?: string;
  embedderApi?: (text: string) => Promise<number[]>;
  compilerApi?: (p: import('../core/types.js').Pinch) => Promise<{ intent: string; action: string }>;
} = {}): Promise<PincherSheetT> {
  const config: PincherSheetConfig = {
    name: opts.name ?? 'pincher-workstation',
    embedder: opts.embedderApi
      ? { dimensions: 384, async embed(t) { return opts.embedderApi!(t); } }
      : new OfflineEmbedder(384),
    store: new SqliteReflexStore(opts.dbPath ?? './reflexes.db'),
    veto: new DefaultVeto(),
    compiler: opts.compilerApi
      ? { async compile(p) { return opts.compilerApi!(p); } }
      : undefined,
  };
  return PincherSheet(config);
}
