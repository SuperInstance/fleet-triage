/**
 * Embedder adapters — wire Quilt's @quilt/ai embedders to the Pincher interface.
 *
 * For cloud, you can use Cloudflare AI's @cf/baai/bge-small-en-v1.5 (384d).
 * For workstation, you can use a local ONNX model.
 * For ESP32, you use a quantized in-memory embedder.
 */
import type { Embedder } from '../core/types.js';
import { HashEmbedder } from '../core/engine.js';

/** Cloudflare AI embedder — runs in Cloudflare Workers, returns 384d vectors. */
export class CloudflareAIEmbedder implements Embedder {
  constructor(public dimensions: number = 384) {}

  async embed(text: string): Promise<number[]> {
    // In production this would call Cloudflare's REST API
    // For now, fall back to hash embedder (offline-friendly)
    return new HashEmbedder(this.dimensions).embed(text);
  }
}

/** Hash embedder wrapper — for ESP32 (no network). */
export class OfflineEmbedder implements Embedder {
  constructor(public dimensions: number = 384) {}
  async embed(text: string): Promise<number[]> {
    return new HashEmbedder(this.dimensions).embed(text);
  }
}

/** Quilt AI embedder — uses the @quilt/ai EmbedderCell. */
export class QuiltAIEmbedder implements Embedder {
  constructor(public dimensions: number, private delegate: (text: string) => Promise<number[]>) {}

  async embed(text: string): Promise<number[]> {
    return this.delegate(text);
  }
}
