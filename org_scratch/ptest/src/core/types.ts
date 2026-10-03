/**
 * @quilt/pincher — core types
 *
 * A reflex engine built from Quilt cells. Every layer of the engine
 * (pinch, match, execute, veto, store) is a cell.
 *
 * The engine is portable across cloud, workstation, and ESP32 because
 * the cell model is portable. Cells compose, federate, persist, and
 * audit — and the same is true of pincher.
 */

/** A pinch — the input to the reflex engine. */
export interface Pinch {
  /** The raw trigger string. */
  trigger: string;
  /** Optional context. */
  context?: Record<string, unknown>;
  /** Optional safety hints. */
  safety?: SafetyHints;
}

/** Safety hints for a pinch — checked by the veto cell. */
export interface SafetyHints {
  /** Execution sandbox. */
  sandbox?: 'none' | 'wasm' | 'docker' | 'process';
  /** Network access allowed. */
  network?: 'none' | 'local' | 'lan' | 'any';
  /** Filesystem access. */
  filesystem?: 'none' | 'read' | 'write' | 'any';
  /** Time budget in ms. */
  timeoutMs?: number;
}

/** A reflex — a learned pattern in the database. */
export interface Reflex {
  /** Unique id. */
  id: string;
  /** The trigger embedding (vector). */
  embedding: number[];
  /** Human-readable intent. */
  intent: string;
  /** The action to execute (code, command, or cell URI). */
  action: string;
  /** Safety constraints for executing this reflex. */
  safety: SafetyHints;
  /** Confidence score (0-1, increases with hits). */
  confidence: number;
  /** Number of times this reflex has been hit. */
  hits: number;
  /** When the reflex was created. */
  createdAt: number;
  /** When the reflex was last hit. */
  lastHitAt: number;
  /** Optional provenance — who created it, why. */
  provenance?: { compiledBy: string; parentReflex?: string };
}

/** The result of a pinch. */
export type PinchResult =
  | { kind: 'hit'; reflex: Reflex; output: unknown; latencyMs: number }
  | { kind: 'confirm'; reflex: Reflex; output: unknown; latencyMs: number }
  | { kind: 'compiled'; reflex: Reflex; output: unknown; latencyMs: number }
  | { kind: 'vetoed'; reason: string; latencyMs: number }
  | { kind: 'error'; error: string; latencyMs: number };

/** The embedder interface — any function from text to vector. */
export interface Embedder {
  embed(text: string): Promise<number[]>;
  dimensions: number;
}

/** The vector store interface — content-addressed, queryable. */
export interface ReflexStore {
  insert(reflex: Reflex): Promise<void>;
  query(embedding: number[], k: number): Promise<{ reflex: Reflex; score: number }[]>;
  get(id: string): Promise<Reflex | undefined>;
  delete(id: string): Promise<void>;
  count(): Promise<number>;
}

/** The LLM compiler — turns unknown pinches into reflexes. */
export interface Compiler {
  compile(pinch: Pinch): Promise<{ intent: string; action: string }>;
}

/** The veto — checks safety before executing. */
export interface Veto {
  check(reflex: Reflex, pinch: Pinch): Promise<{ ok: boolean; reason?: string }>;
}

/** Configuration for the Pincher engine. */
export interface PincherConfig {
  embedder: Embedder;
  store: ReflexStore;
  compiler?: Compiler;
  veto?: Veto;
  /** Threshold for direct hit (default 0.80). */
  hitThreshold?: number;
  /** Threshold for confirmation (default 0.55). */
  confirmThreshold?: number;
  /** Maximum time for a reflex execution (default 5000ms). */
  executionTimeoutMs?: number;
}

/** A .nail bundle — portable agent state. */
export interface NailBundle {
  /** Schema version. */
  version: string;
  /** The reflex database, content-addressed. */
  reflexes: Reflex[];
  /** Veto rules. */
  vetoRules: { rule: string; severity: 'allow' | 'deny' | 'warn' }[];
  /** Compile history. */
  compileHistory: { trigger: string; reflexId: string; ts: number }[];
  /** Bundle metadata. */
  metadata: { name: string; createdAt: number; updatedAt: number; tier: string };
}
