/**
 * fsm-ledger Pi extension — on message_end, shell out to python3 -m fsm_ledger append.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const SKILL = join(homedir(), ".agents/skills/feature-status-matrix");

function appendUsage(payload: Record<string, unknown>): void {
  const child = spawn(
    "python3",
    ["-m", "fsm_ledger", "append", "--harness", "pi", "--render"],
    {
      env: { ...process.env, PYTHONPATH: SKILL },
      stdio: ["pipe", "ignore", "ignore"],
    },
  );
  child.stdin.write(JSON.stringify(payload));
  child.stdin.end();
  // fire-and-forget — never block the agent
  child.on("error", () => {});
}

export default function fsmLedgerExtension(pi: ExtensionAPI): void {
  pi.on("message_end", async (event, ctx) => {
    try {
      const msg: any = (event as any)?.message ?? event;
      const usage = msg?.usage;
      if (!usage) return;

      const input = Number(usage.input || usage.inputTokens || 0);
      const output = Number(usage.output || usage.outputTokens || 0);
      const cached = Number(usage.cacheRead || usage.cachedInputTokens || 0);
      const costTotal =
        usage.cost?.total ?? usage.costTotal ?? usage.cost ?? undefined;
      const model =
        msg?.model
        ?? (ctx as any)?.model?.id
        ?? "";

      if (!input && !output && costTotal == null) return;

      appendUsage({
        harness: "pi",
        model: String(model || ""),
        inputTokens: input,
        outputTokens: output,
        cachedInputTokens: cached,
        totalTokens: Number(usage.totalTokens || input + output),
        costTotal: costTotal != null ? Number(costTotal) : undefined,
        message_id: String(msg?.id || msg?.uuid || ""),
        session_id: String((ctx as any)?.sessionId || ""),
        cwd: String((ctx as any)?.cwd || process.cwd()),
        status: "message_end",
        provider: String((ctx as any)?.model?.provider || ""),
      });
    } catch {
      // never block
    }
  });
}
