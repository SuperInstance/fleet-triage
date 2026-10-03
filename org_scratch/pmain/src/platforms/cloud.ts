/**
 * Cloud tier — browser, Node, Cloudflare Workers.
 *
 * Full features: real embedders, LLM compiler, federated storage, R2 mirror.
 *
 * ```ts
 * const sheet = await cloudSheet({ name: 'my-agent' });
 * const result = await sheet.engine.run({ trigger: 'list containers' });
 * ```
 */
import { PincherSheet } from '../cells/sheet.js';
import type { PincherSheetConfig, PincherSheet as PincherSheetT } from '../cells/sheet.js';
import { MemoryReflexStore } from '../adapters/memory-store.js';
import { CloudflareAIEmbedder } from '../adapters/embedding-adapter.js';
import { DefaultVeto } from '../core/engine.js';
import type { Compiler, Pinch } from '../core/types.js';

export async function cloudSheet(opts: {
  name?: string;
  embedderApi?: (text: string) => Promise<number[]>;
  compilerApi?: (pinch: Pinch) => Promise<{ intent: string; action: string }>;
  federation?: { upstreamStore?: import('../core/types.js').ReflexStore };
} = {}): Promise<PincherSheetT> {
  const config: PincherSheetConfig = {
    name: opts.name ?? 'pincher-cloud',
    embedder: opts.embedderApi
      ? {
          dimensions: 384,
          async embed(text) { return opts.embedderApi!(text); },
        }
      : new CloudflareAIEmbedder(384),
    store: new MemoryReflexStore({ upstream: opts.federation?.upstreamStore }),
    veto: new DefaultVeto(),
    compiler: opts.compilerApi
      ? {
          async compile(pinch) { return opts.compilerApi!(pinch); },
        }
      : undefined,
  };
  return PincherSheet(config);
}
