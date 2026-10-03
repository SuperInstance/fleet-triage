/**
 * ESP32 tier — no_std Rust (a port lives in src/port/no_std/).
 *
 * Subset: in-memory only, no LLM, no network. Reflexes are loaded from a
 * pre-compiled .nail bundle.
 *
 * The TypeScript version below mirrors the no_std Rust API so you can
 * prototype on a workstation and then port the same logic to ESP32.
 */
import { PincherSheet } from '../cells/sheet.js';
import type { PincherSheetConfig, PincherSheet as PincherSheetT } from '../cells/sheet.js';
import { MemoryReflexStore } from '../adapters/memory-store.js';
import { OfflineEmbedder } from '../adapters/embedding-adapter.js';
import { DefaultVeto } from '../core/engine.js';
import type { Pinch, PinchResult, Reflex } from '../core/types.js';

/** Embedded reflex database — the .nail bundle, pre-loaded. */
export interface EmbeddedNail {
  /** Schema version. */
  version: string;
  /** The reflex database (no embeddings — recomputed on load). */
  reflexes: Omit<Reflex, 'embedding'>[];
  /** When the bundle was built. */
  builtAt: number;
}

/** ESP32 engine — in-memory, no LLM, no network. */
export class ESP32Engine {
  private engine: import('../core/engine.js').PincherEngine;

  constructor(sheet: PincherSheetT) {
    this.engine = sheet.engine;
  }

  /** Pre-load a .nail bundle. Reflexes are embedded on the device. */
  async loadNail(bundle: EmbeddedNail, embedder: OfflineEmbedder): Promise<void> {
    for (const reflex of bundle.reflexes) {
      const embedding = await embedder.embed(reflex.intent);
      await this.engine.addReflex({ ...reflex, embedding });
    }
  }

  /** Run a pinch. */
  async run(pinch: Pinch): Promise<PinchResult> {
    return this.engine.run(pinch);
  }

  /** Memory usage in bytes (approximate). */
  async memoryUsage(): Promise<number> {
    const n = await this.engine.size();
    return n * 4096;  // ~4KB per reflex including embedding
  }
}

export async function esp32Sheet(opts: { name?: string } = {}): Promise<{ sheet: PincherSheetT; engine: ESP32Engine }> {
  const config: PincherSheetConfig = {
    name: opts.name ?? 'pincher-esp32',
    embedder: new OfflineEmbedder(384),
    store: new MemoryReflexStore(),
    veto: new DefaultVeto(),
    // No compiler — ESP32 is offline
  };
  const sheet = PincherSheet(config);
  return { sheet, engine: new ESP32Engine(sheet) };
}

/**
 * Build a .nail bundle for ESP32 from a cloud or workstation sheet.
 * The bundle is small enough to fit in flash (typical: 100KB-1MB).
 */
export async function buildNail(sheet: PincherSheetT): Promise<EmbeddedNail> {
  const reflexes = await (sheet.engine as any).store.all?.() ?? [];
  return {
    version: '0.1.0',
    reflexes: reflexes.map((r: Reflex) => {
      const { embedding, ...rest } = r;
      return rest;
    }),
    builtAt: Date.now(),
  };
}
