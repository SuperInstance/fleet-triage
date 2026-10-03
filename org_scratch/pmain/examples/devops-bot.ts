/**
 * Example: a DevOps bot that uses Pincher to learn reflexes.
 *
 * The bot starts with zero reflexes. Each time you ask it to do
 * something, it either hits a learned reflex (<50ms) or compiles
 * a new one via the LLM and stores it for next time.
 */
import { cloudSheet, runPinch, type Pinch } from '../src/index.js';

async function main() {
  // 1. Build a cloud sheet with a fake LLM compiler
  //    (in real use, this would call z.ai / Kimi / DeepSeek)
  const sheet = await cloudSheet({
    name: 'devops-bot',
    compilerApi: async (pinch: Pinch) => ({
      intent: `devops: ${pinch.trigger}`,
      action: `
        if (pinch.context?.host) {
          return { ran: true, on: pinch.context.host, for: '${pinch.trigger}' };
        }
        return { ran: true, for: '${pinch.trigger}' };
      `,
    }),
  });

  console.log('═══ Pincher devops bot ═══\n');

  // 2. First pinch — unknown, gets compiled
  console.log('First pinch: "list running containers"');
  const r1 = await runPinch(sheet, {
    trigger: 'list running containers',
    context: { host: 'prod-01' },
  });
  console.log('  →', r1.kind, '(' + r1.latencyMs + 'ms)\n');

  // 3. Second pinch — similar, should hit
  console.log('Second pinch: "show me running containers"');
  const r2 = await runPinch(sheet, {
    trigger: 'show me running containers',
    context: { host: 'prod-01' },
  });
  console.log('  →', r2.kind, '(' + r2.latencyMs + 'ms)\n');

  // 4. Third pinch — completely new, compile again
  console.log('Third pinch: "check disk space"');
  const r3 = await runPinch(sheet, {
    trigger: 'check disk space',
    context: { host: 'prod-01' },
  });
  console.log('  →', r3.kind, '(' + r3.latencyMs + 'ms)\n');

  // 5. Fourth pinch — similar to #3
  console.log('Fourth pinch: "how much disk"');
  const r4 = await runPinch(sheet, {
    trigger: 'how much disk',
    context: { host: 'prod-01' },
  });
  console.log('  →', r4.kind, '(' + r4.latencyMs + 'ms)\n');

  // 6. Stats
  console.log('Total reflexes in DB:', await sheet.engine.size());
}

main().catch(console.error);
