/**
 * In-memory vector store — works on cloud (browser, Node), workstation, and ESP32 (no_std port).
 *
 * Uses brute-force cosine similarity. For up to 10K reflexes this is faster
 * than any HNSW index because the search fits in a single L2 cache.
 */
import type { Reflex, ReflexStore } from '../core/types.js';

interface Entry {
  reflex: Reflex;
  embedding: number[];
}

export class MemoryReflexStore implements ReflexStore {
  private entries: Entry[] = [];
  /** When set, the store federates by also calling the upstream store. */
  private upstream?: ReflexStore;

  constructor(opts: { upstream?: ReflexStore } = {}) {
    this.upstream = opts.upstream;
  }

  async insert(reflex: Reflex): Promise<void> {
    const i = this.entries.findIndex((e) => e.reflex.id === reflex.id);
    const entry: Entry = { reflex, embedding: reflex.embedding };
    if (i >= 0) this.entries[i] = entry;
    else this.entries.push(entry);
    if (this.upstream) await this.upstream.insert(reflex);
  }

  async query(embedding: number[], k: number): Promise<{ reflex: Reflex; score: number }[]> {
    const scored = this.entries.map((e) => ({
      reflex: e.reflex,
      score: cosineSimilarity(embedding, e.embedding),
    }));
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, k);
  }

  async get(id: string): Promise<Reflex | undefined> {
    return this.entries.find((e) => e.reflex.id === id)?.reflex;
  }

  async delete(id: string): Promise<void> {
    this.entries = this.entries.filter((e) => e.reflex.id !== id);
    if (this.upstream) await this.upstream.delete(id);
  }

  async count(): Promise<number> {
    return this.entries.length;
  }

  /** Export all entries (for .nail bundle). */
  async all(): Promise<Reflex[]> {
    return this.entries.map((e) => e.reflex);
  }
}

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i]! * b[i]!;
    na += a[i]! * a[i]!;
    nb += b[i]! * b[i]!;
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) || 1);
}
