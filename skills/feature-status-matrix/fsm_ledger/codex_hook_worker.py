import fcntl, json, os, sys, traceback
from pathlib import Path

# Ensure skill on path
skill = Path(os.environ.get("PYTHONPATH", "").split(os.pathsep)[0])
if str(skill) not in sys.path:
    sys.path.insert(0, str(skill))

from .ledger import _existing_ids, _log, append_dict, usage_log_path
from .render_trigger import render_now
from .attribute import matrices_root, resolve_project


def rollout_path(payload: dict) -> Path | None:
    explicit = deep_find(payload, ["transcript_path", "rollout_path", "session_path"])
    if explicit and Path(str(explicit)).is_file():
        return Path(str(explicit))
    session_id = deep_find(payload, ["session_id", "thread_id", "conversation_id"])
    if session_id:
        matches = list((Path.home() / ".codex" / "sessions").rglob(f"*{session_id}.jsonl"))
        if matches:
            return matches[-1]
    return None


def append_rollout(payload: dict) -> tuple[bool, str]:
    path = rollout_path(payload)
    if path is None:
        return False, ""
    session_id = str(deep_find(payload, ["session_id", "thread_id", "conversation_id"]) or "")
    cwd = str(deep_find(payload, ["cwd", "workdir"]) or "")
    turns: dict[str, tuple[str, str]] = {}
    seen_by_project: dict[str, set[str]] = {}
    project = ""
    with path.open(encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = record.get("type")
            data = record.get("payload") or {}
            if kind == "session_meta":
                session_id = session_id or str(data.get("session_id") or data.get("id") or "")
                cwd = cwd or str(data.get("cwd") or "")
            elif kind == "turn_context":
                turns[str(data.get("turn_id") or "")] = (
                    str(data.get("model") or ""), str(data.get("cwd") or cwd)
                )
                cwd = cwd or str(data.get("cwd") or "")
            elif kind == "token_usage_record":
                usage = data.get("usage") or {}
                response_id = data.get("response_id")
                if not response_id or not isinstance(usage, dict) or not session_id:
                    continue
                model, response_cwd = turns.get(str(data.get("turn_id") or ""), ("", cwd))
                project_hint = resolve_project(response_cwd)
                if project_hint not in seen_by_project:
                    seen_by_project[project_hint] = _existing_ids(usage_log_path(project_hint))
                seen = seen_by_project[project_hint]
                event_id = f"codex:{session_id}:{response_id}"
                if f"event_id:{event_id}" in seen:
                    continue
                event = {
                    "event_id": event_id,
                    "session_id": session_id,
                    "model": model,
                    "inputTokens": as_int(usage.get("input_tokens")),
                    "outputTokens": as_int(usage.get("output_tokens")),
                    "totalTokens": as_int(usage.get("total_tokens")),
                    "ts": record.get("timestamp"),
                    "cwd": response_cwd,
                    "harness": "codex",
                    "status": "response",
                }
                if "cached_input_tokens" in usage:
                    event["cachedInputTokens"] = usage["cached_input_tokens"]
                if "cache_write_input_tokens" in usage:
                    event["cacheWriteInputTokens"] = usage["cache_write_input_tokens"]
                result = append_dict(event)
                if not result.get("ok"):
                    raise RuntimeError(result.get("error") or "ledger append failed")
                project = result["project"]
                seen.add(f"event_id:{event_id}")
    return True, project or resolve_project(cwd)

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

def process_one(path: Path) -> None:
    with path.open(encoding="utf-8") as stream:
        event = stream.readline().strip().lower().replace("-", "_")
        payload = parse_hook_payload(stream.read())
        found_rollout, project = append_rollout(payload)
    if not found_rollout:
        raise RuntimeError("Codex rollout unavailable; keeping event for retry")
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
