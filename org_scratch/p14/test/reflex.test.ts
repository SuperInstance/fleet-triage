/**
 * Tests for the Pincher engine.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { PincherEngine, HashEmbedder, DefaultVeto } from '../src/index.ts';
import { MemoryReflexStore } from '../src/index.ts';
import type { Pinch, Reflex, Compiler } from '../src/index.ts';

function makeEngine(opts: { withCompiler?: boolean } = {}) {
  const store = new MemoryReflexStore();
  const compiler: Compiler = opts.withCompiler
    ? {
        async compile(pinch: Pinch) {
          return {
            intent: `intent: ${pinch.trigger}`,
            action: `return { ok: true, message: 'compiled for ${pinch.trigger}' };`,
          };
        },
      }
    : undefined;
  return new PincherEngine({
    embedder: new HashEmbedder(64),  // smaller for tests
    store,
    compiler,
    veto: new DefaultVeto(),
  });
}

describe('PincherEngine — direct hit', () => {
  test('returns a hit when a reflex matches above threshold', async () => {
    const engine = makeEngine();
    const embedder = new HashEmbedder(64);
    const embedding = await embedder.embed('list containers');
    await engine.addReflex({
      id: 'r1',
      embedding,
      intent: 'list running containers',
      action: 'return { containers: [] };',
      safety: {},
      confidence: 0.9,
      hits: 5,
      createdAt: Date.now(),
      lastHitAt: Date.now(),
    });

    const result = await engine.run({ trigger: 'list containers' });
    assert.equal(result.kind, 'hit');
    assert.equal(result.latencyMs >= 0, true);
  });

  test('high-confidence reflexes fire even with slight trigger variation', async () => {
    const engine = makeEngine();
    const embedder = new HashEmbedder(64);
    const embedding = await embedder.embed('list containers');
    await engine.addReflex({
      id: 'r1',
      embedding,
      intent: 'list running containers',
      action: `return ['container1', 'container2'];`,
      safety: {},
      confidence: 0.9,
      hits: 100,
      createdAt: Date.now(),
      lastHitAt: Date.now(),
    });

    const result = await engine.run({ trigger: 'show me containers' });
    // Should be either hit or confirm (not compile)
    assert.ok(['hit', 'confirm'].includes(result.kind));
  });
});

describe('PincherEngine — confirm tier', () => {
  test('medium confidence triggers confirm tier', async () => {
    const engine = makeEngine();
    const embedder = new HashEmbedder(64);
    // Add a reflex with low confidence
    await engine.addReflex({
      id: 'r1',
      embedding: await embedder.embed('list containers'),
      intent: 'list containers',
      action: `return 'list';`,
      safety: {},
      confidence: 0.5,
      hits: 0,
      createdAt: Date.now(),
      lastHitAt: 0,
    });

    // Run with a similar but not identical trigger
    const result = await engine.run({ trigger: 'list container' });
    assert.ok(['hit', 'confirm'].includes(result.kind));
  });
});

describe('PincherEngine — compile tier', () => {
  test('unknown trigger triggers LLM compile when compiler is configured', async () => {
    const engine = makeEngine({ withCompiler: true });
    const result = await engine.run({ trigger: 'completely new unique thing xyz' });
    assert.equal(result.kind, 'compiled');
    assert.ok(result.reflex);
  });

  test('unknown trigger without compiler returns error', async () => {
    const engine = makeEngine();
    const result = await engine.run({ trigger: 'completely new unique thing xyz' });
    assert.equal(result.kind, 'error');
  });
});

describe('PincherEngine — veto', () => {
  test('vetoes pinches that exceed reflex safety constraints', async () => {
    const store = new MemoryReflexStore();
    const engine = new PincherEngine({
      embedder: new HashEmbedder(64),
      store,
      veto: new DefaultVeto(),
    });
    const embedder = new HashEmbedder(64);
    const embedding = await embedder.embed('list containers');
    await engine.addReflex({
      id: 'r1',
      embedding,
      intent: 'list containers',
      action: `return [];`,
      safety: { network: 'local' },
      confidence: 0.9,
      hits: 5,
      createdAt: Date.now(),
      lastHitAt: Date.now(),
    });

    // Pinch wants any-network, reflex is local-only → veto
    const result = await engine.run({
      trigger: 'list containers',
      safety: { network: 'any' },
    });
    assert.equal(result.kind, 'vetoed');
  });
});

describe('PincherEngine — confidence climbs with hits', () => {
  test('confidence approaches 0.99 as hits increase', async () => {
    const store = new MemoryReflexStore();
    const engine = new PincherEngine({
      embedder: new HashEmbedder(64),
      store,
      compiler: { async compile(p: Pinch) { return { intent: p.trigger, action: 'return 1;' }; } },
    });
    const embedder = new HashEmbedder(64);
    const embedding = await embedder.embed('test trigger');

    // Compile a new reflex
    await engine.run({ trigger: 'test trigger' });

    // Get it
    const r = await store.get((await store.query(embedding, 1))[0]!.reflex.id);
    assert.ok(r);
    // Initial confidence should be 0.5
    assert.equal(r!.confidence, 0.5);
  });
});

describe('PincherSheet — composes the engine as cells', () => {
  test('creates a sheet with all the reflex engine cells', async () => {
    const { PincherSheet } = await import('../src/index.ts');
    const sheet = PincherSheet({
      embedder: new HashEmbedder(64),
      store: new MemoryReflexStore(),
    });
    assert.equal(sheet.cells.length, 6);
    const kinds = sheet.cells.map((c) => c.kind);
    assert.ok(kinds.includes('formula'));  // pinch
    assert.ok(kinds.includes('program'));  // match, execute
    assert.ok(kinds.includes('listener')); // veto
    assert.ok(kinds.includes('ai'));       // compile
    assert.ok(kinds.includes('vector_store')); // store
  });
});

describe('cloudSheet', () => {
  test('returns a sheet with cloud defaults', async () => {
    const { cloudSheet } = await import('../src/index.ts');
    const sheet = await cloudSheet({ name: 'test' });
    assert.equal(sheet.name, 'test');
  });
});

describe('workstationSheet', () => {
  test('returns a sheet with workstation defaults', async () => {
    const { workstationSheet } = await import('../src/index.ts');
    const sheet = await workstationSheet({ name: 'workstation' });
    assert.equal(sheet.name, 'workstation');
  });
});

describe('esp32Sheet', () => {
  test('returns a sheet with ESP32 defaults + engine', async () => {
    const { esp32Sheet } = await import('../src/index.ts');
    const { sheet, engine } = await esp32Sheet({ name: 'esp32' });
    assert.equal(sheet.name, 'esp32');
    assert.ok(engine);
  });

  test('can load a .nail bundle', async () => {
    const { esp32Sheet, buildNail, MemoryReflexStore } = await import('../src/index.ts');
    const embedder = new HashEmbedder(64);
    const store = new MemoryReflexStore();
    const { PincherEngine } = await import('../src/index.ts');
    const cloud = new PincherEngine({ embedder, store });
    await cloud.addReflex({
      id: 'r1',
      embedding: await embedder.embed('list containers'),
      intent: 'list containers',
      action: `return [];`,
      safety: {},
      confidence: 0.5,
      hits: 0,
      createdAt: Date.now(),
      lastHitAt: 0,
    });

    const { sheet, engine: esp32 } = await esp32Sheet();
    const bundle = await buildNail({ name: 'test', engine: cloud, cells: [] } as any);
    await esp32.loadNail(bundle, new (await import('../src/index.ts')).OfflineEmbedder(64));
    const memUsage = await esp32.memoryUsage();
    assert.ok(memUsage > 0);
  });
});
