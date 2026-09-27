import fcntl, json, os, sys, traceback
from pathlib import Path

# Ensure skill on path
skill = Path(os.environ.get("PYTHONPATH", "").split(os.pathsep)[0])
if str(skill) not in sys.path:
    sys.path.insert(0, str(skill))

from .ledger import _log, append_dict
from .render_trigger import render_now
from .attribute import matrices_root, resolve_project

def deep_find(data, candidates):
    wanted = set(candidates)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in wanted:
                return v
            found = deep_find(v, wanted)
            if found is not None:
                return found
    elif isinstance(data, list):
        for v in data:
            found = deep_find(v, wanted)
            if found is not None:
                return found
    return None

def parse_hook_payload(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw_payload": data}
    except json.JSONDecodeError:
        return {"raw_text": text}

def as_int(v):
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0

def usage_from_payload(payload: dict, event_name: str) -> dict:
    """Prefer usage fields; else best-effort transcript/rollout JSONL."""
    usage = deep_find(payload, ["usage", "token_usage", "last_token_usage", "token_count"]) or {}
    if not isinstance(usage, dict):
        usage = {}
    model = deep_find(payload, ["model", "model_slug"])
    tc = deep_find(payload, ["turn_context"])
    if not model and isinstance(tc, dict):
        model = tc.get("model")
    inp = as_int(usage.get("input_tokens") or usage.get("prompt_tokens") or deep_find(payload, ["input_tokens"]))
    out = as_int(usage.get("output_tokens") or usage.get("completion_tokens") or deep_find(payload, ["output_tokens"]))
    cached = as_int(usage.get("cached_input_tokens") or usage.get("cached_tokens"))
    total = as_int(usage.get("total_tokens")) or (inp + out)
    cost = usage.get("cost_total") or usage.get("cost") or deep_find(payload, ["cost_usd", "costTotal"])
    session_id = str(deep_find(payload, ["session_id", "conversation_id"]) or "")
    cwd = str(deep_find(payload, ["cwd", "workdir"]) or os.environ.get("PWD") or "")
    message_id = str(deep_find(payload, ["message_id", "turn_id"]) or "")

    # Best-effort: transcript_path / rollout JSONL
    if total <= 0:
        tpath = deep_find(payload, ["transcript_path", "rollout_path", "session_path"])
        if tpath and Path(str(tpath)).is_file():
            try:
                lines = Path(str(tpath)).read_text(encoding="utf-8", errors="ignore").splitlines()
                for line in reversed(lines[-200:]):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    u = deep_find(row, ["token_count", "last_token_usage", "usage"]) or {}
                    if isinstance(u, dict) and (u.get("input_tokens") or u.get("total_tokens")):
                        inp = as_int(u.get("input_tokens") or u.get("prompt_tokens"))
                        out = as_int(u.get("output_tokens") or u.get("completion_tokens"))
                        cached = as_int(u.get("cached_input_tokens"))
                        total = as_int(u.get("total_tokens")) or (inp + out)
                        if not model:
                            tc = row.get("turn_context") if isinstance(row.get("turn_context"), dict) else {}
                            model = tc.get("model") or deep_find(row, ["model"])
                        break
            except OSError:
                pass

    return {
        "model": str(model or ""),
        "inputTokens": inp,
        "outputTokens": out,
        "cachedInputTokens": cached,
        "totalTokens": total,
        "costTotal": float(cost) if cost is not None else None,
        "session_id": session_id,
        "cwd": cwd,
        "message_id": message_id,
        "harness": "codex",
        "status": event_name,
    }

def process_one(path: Path) -> None:
    with path.open(encoding="utf-8") as stream:
        event = stream.readline().strip().lower().replace("-", "_")
        payload = parse_hook_payload(stream.read())
        row = usage_from_payload(payload, event)
    row["event_id"] = path.name
    if row.get("costTotal") is None:
        row.pop("costTotal", None)
    if row.get("totalTokens") or row.get("inputTokens") or row.get("outputTokens"):
        result = append_dict(row)
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "ledger append failed")
        project = result["project"]
    else:
        project = resolve_project(row.get("cwd"))
    if event in ("stop", "session_end"):
        render_now(project)
    path.unlink()


queue = matrices_root() / "_hook_pending"
with (queue / ".lock").open("w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    for path in sorted(queue.glob("event-*")):
        try:
            process_one(path)
        except Exception as exc:
            _log(f"hook_worker_error path={path} err={exc}\n{traceback.format_exc()}")
sys.exit(0)
