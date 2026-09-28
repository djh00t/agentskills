/**
 * fsm-ledger Pi extension — on message_end, shell out to python3 -m fsm_ledger append.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const SKILL = join(homedir(), ".agents/skills/feature-status-matrix");

function appendUsage(payload: Record<string, unknown>): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      "python3",
      ["-m", "fsm_ledger", "append", "--harness", "pi", "--render"],
      {
        env: { ...process.env, PYTHONPATH: SKILL },
        stdio: ["pipe", "ignore", "ignore"],
      },
    );
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? resolve() : reject(new Error(`append exited ${code}`)));
    child.stdin.end(JSON.stringify(payload));
  });
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
      const cacheWrite = Number(usage.cacheWrite || usage.cacheWriteInputTokens || 0);
      const costTotal =
        usage.cost?.total ?? usage.costTotal ?? usage.cost ?? undefined;
      const model =
        msg?.model
        ?? (ctx as any)?.model?.id
        ?? "";
      const sessionId = String(ctx.sessionManager.getSessionId());
      const messageId = String(msg?.id || msg?.uuid || "");

      await appendUsage({
        harness: "pi",
        model: String(model || ""),
        inputTokens: input + cached + cacheWrite,
        outputTokens: output,
        cachedInputTokens: usage.cacheRead != null || usage.cachedInputTokens != null ? cached : undefined,
        cacheWriteInputTokens: usage.cacheWrite != null || usage.cacheWriteInputTokens != null ? cacheWrite : undefined,
        totalTokens: Number(usage.totalTokens || input + cached + cacheWrite + output),
        costTotal: costTotal != null ? Number(costTotal) : undefined,
        event_id: sessionId && messageId ? `pi:${sessionId}:${messageId}` : undefined,
        session_id: sessionId,
        ts: msg?.timestamp ? new Date(msg.timestamp).toISOString() : new Date().toISOString(),
        cwd: String((ctx as any)?.cwd || process.cwd()),
        status: "response",
        provider: String((ctx as any)?.model?.provider || ""),
      });
    } catch (error) {
      process.stderr.write(`fsm-ledger Pi capture failed: ${String(error)}\n`);
    }
  });
}
