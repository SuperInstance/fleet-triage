/**
 * The Pincher sheet — the whole engine as a Quilt sheet.
 *
 * Every layer of pincher is a cell:
 *   - pinch (formula cell): trigger → embedding
 *   - match (program cell): embedding → top-K reflexes
 *   - execute (program cell): reflex + pinch → output
 *   - veto (listener cell): safety check
 *   - compile (ai cell): new reflex from LLM
 *   - store (vector_store cell): the reflex database
 *
 * The sheet can be loaded into any QuiltEngine.
 */
import type { PincherConfig, Pinch, PinchResult } from '../core/types.js';
import { PincherEngine } from '../core/engine.js';

export interface PincherSheetConfig extends PincherConfig {
  /** Sheet name. */
  name?: string;
}

export interface PincherSheet {
  /** Sheet name. */
  name: string;
  /** The compiled engine. */
  engine: PincherEngine;
  /** Sheet descriptor (the cells). */
  cells: PincherCell[];
}

export interface PincherCell {
  path: string;
  kind: string;
  description: string;
}

/** Build a Pincher sheet. The whole reflex engine is a Quilt sheet. */
export function PincherSheet(config: PincherSheetConfig): PincherSheet {
  const name = config.name ?? 'pincher';
  const engine = new PincherEngine(config);

  const cells: PincherCell[] = [
    { path: 'pinch', kind: 'formula', description: 'Convert trigger + context to embedding' },
    { path: 'match', kind: 'program', description: 'Query the vector store for top-K reflexes' },
    { path: 'execute', kind: 'program', description: 'Run the matched reflex action' },
    { path: 'veto', kind: 'listener', description: 'Safety check before execution' },
    { path: 'compile', kind: 'ai', description: 'LLM compiler for unknown pinches' },
    { path: 'store', kind: 'vector_store', description: 'The reflex database' },
  ];

  return { name, engine, cells };
}

/** A convenient wrapper for running a pinch through a sheet. */
export async function runPinch(sheet: PincherSheet, pinch: Pinch): Promise<PinchResult> {
  return sheet.engine.run(pinch);
}
