/**
 * fsm-ledger OpenCode plugin — phase-2 stub.
 * Listens message.updated when available and shells to fsm_ledger append.
 */
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const SKILL = join(homedir(), ".agents/skills/feature-status-matrix");

function append(payload) {
  try {
    const child = spawn(
      "python3",
      ["-m", "fsm_ledger", "append", "--harness", "opencode"],
      { env: { ...process.env, PYTHONPATH: SKILL }, stdio: ["pipe", "ignore", "ignore"] },
    );
    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  } catch {
    /* never block */
  }
}

export const FSMLedgerPlugin = async ({ $ }) => {
  // Best-effort: OpenCode plugin API varies; this is a phase-2 stub.
  return {
    name: "fsm-ledger",
    // Placeholder — enable via ~/.config/opencode/fsm-ledger.ENABLE.txt instructions
  };
};

export default FSMLedgerPlugin;
