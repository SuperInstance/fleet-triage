/**
 * @quilt/pincher — main entry
 *
 * A reflex engine built entirely from Quilt cells. The engine is
 * a Quilt sheet that runs on cloud, workstation, and ESP32.
 *
 * The same code path:
 *   1. embeds the trigger
 *   2. matches against the reflex database
 *   3. executes the top match (or compiles a new reflex)
 *   4. vetoes unsafe execution
 *   5. persists the reflex for next time
 *
 * All five steps are Quilt cells. The whole engine is federable,
 * subscribable, and auditable.
 */

// Core types
export type {
  Pinch, PinchResult, PincherConfig, Reflex, Embedder, ReflexStore,
  Compiler, Veto, SafetyHints, NailBundle,
} from './core/types.js';

// Core engine
export { PincherEngine, HashEmbedder, DefaultVeto } from './core/engine.js';

// Adapters
export { MemoryReflexStore } from './adapters/memory-store.js';
export { CloudflareAIEmbedder, OfflineEmbedder, QuiltAIEmbedder } from './adapters/embedding-adapter.js';

// Quilt sheet (the engine as cells)
export { PincherSheet, runPinch } from './cells/sheet.js';
export type { PincherSheetConfig, PincherCell } from './cells/sheet.js';

// Platform adapters
export { cloudSheet } from './platforms/cloud.js';
export { workstationSheet, SqliteReflexStore } from './platforms/workstation.js';
export { esp32Sheet, buildNail, ESP32Engine } from './platforms/esp32.js';
export type { EmbeddedNail } from './platforms/esp32.js';
