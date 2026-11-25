"""Write launcher specs and read offline ``codex exec --json`` output.

spec(req, directory) accepts req_id, prompt_file, base, branch, timeout_s and
optional model (gpt-6-luna). It returns path, status and launch_allowed; only
status=specced permits a launch. It never executes a command. Keep the spec
file for the lifetime of the request, including failed or cancelled launches.

usage(jsonl, pricing_row=None) reads JSONL text. Missing telemetry stays None.
Exec 0.166.0 reports turn.completed.usage input_tokens, cached_input_tokens
and output_tokens; model, cache writes and elapsed time may be absent. Optional
model and duration_ms event fields are preserved when present. An interrupted
stream retains all complete usage events; a truncated final line is ignored.

Pricing is joined, never recalculated: pass the matching fsm-ledger row priced
from a dated models.dev snapshot. turn_cost_ledger.row_cost selects its API
equivalent using the same subscription rules as the turn ledger. billed_cost_usd
is separate and remains unknown unless explicitly supplied by that row. No
network, credentials, hooks or default user-state files are accessed.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

_LEDGER_PATH = Path(__file__).resolve().parents[1] / 'turn-cost-ledger' / 'turn_cost_ledger.py'
_loader = importlib.util.spec_from_file_location('cg_turn_cost_ledger', _LEDGER_PATH)
_ledger = importlib.util.module_from_spec(_loader)
_loader.loader.exec_module(_ledger)


def spec(req: dict, directory: str | Path) -> dict:
    """Publish one immutable spec per request; refuse every duplicate launch."""
    req_id = req.get('req_id')
    if not isinstance(req_id, str) or not re.fullmatch(r'REQ-CG-[0-9]{8}-[0-9]{3}', req_id):
        raise ValueError('invalid request id')
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (req_id + '.json')
    if path.exists():
        return dict(path=path, status='already specced', launch_allowed=False)
    record = {key: req.get(key) for key in ('req_id', 'prompt_file', 'base', 'branch', 'timeout_s')}
    record['model'] = req.get('model', 'gpt-6-luna')
    for key in ('prompt_file', 'base', 'branch', 'model'):
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError('missing or invalid ' + key)
    timeout = record['timeout_s']
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout_s must be positive and finite')
    content = json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + '\n'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return dict(path=path, status='already specced', launch_allowed=False)
    # A failed write leaves a reservation: retry must not authorize a launch.
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return dict(path=path, status='specced', launch_allowed=True)


def _count(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def usage(jsonl: str, pricing_row: dict | None = None) -> dict:
    """Sum per-turn usage without fabricating missing counts or billed costs."""
    result = dict.fromkeys(('model', 'input', 'cache_read', 'cache_write', 'output', 'wall_clock_s'))
    names = dict(input='input_tokens', cache_read='cached_input_tokens',
                 cache_write='cache_write_input_tokens', output='output_tokens')
    samples = []
    durations = []
    completed = False
    damaged = False
    lines = jsonl.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if index != len(lines) - 1 or jsonl.endswith('\n'):
                raise ValueError('invalid JSONL event') from None
            damaged = True
            continue
        if not isinstance(event, dict):
            raise ValueError('event must be an object')
        if isinstance(event.get('model'), str) and event['model']:
            result['model'] = event['model']
        kind = event.get('type')
        if kind in ('turn.completed', 'turn.failed'):
            completed = kind == 'turn.completed'
            counts = event.get('usage')
            if kind == 'turn.failed' and counts is None:
                continue
            if isinstance(counts, dict):
                samples.append({key: _count(counts.get(name)) for key, name in names.items()})
            else:
                samples.append(dict.fromkeys(names))
            duration = event.get('duration_ms')
            durations.append(duration / 1000 if isinstance(duration, (int, float))
                             and not isinstance(duration, bool) and math.isfinite(duration)
                             and duration >= 0 else None)
        elif kind in ('turn.started', 'error'):
            completed = False
    for key in names:
        values = [sample[key] for sample in samples]
        if values and all(value is not None for value in values):
            result[key] = sum(values)
    if durations and all(value is not None for value in durations):
        result['wall_clock_s'] = sum(durations)
    result['completeness'] = 'complete' if completed and not damaged and all(
        value is not None for value in result.values()) else 'partial'
    result.update(est_cost_usd=None, billed_cost_usd=None,
                  subscription_equivalent_usd=None, pricing_date=None, pricing_source=None)
    if pricing_row is not None:
        source = pricing_row.get('source_url', '')
        if urlsplit(source).hostname != 'models.dev':
            raise ValueError('pricing must reference a models.dev snapshot')
        date.fromisoformat(pricing_row.get('pricing_date', ''))
        if not result['model'] or pricing_row.get('model') != result['model']:
            raise ValueError('pricing row model does not match usage')
        for key, field in dict(input='inputTokens', cache_read='cachedInputTokens',
                              cache_write='cacheWriteInputTokens', output='outputTokens').items():
            if pricing_row.get(field) != result[key]:
                raise ValueError('pricing row tokens do not match usage')
        cost = _ledger.row_cost(pricing_row)
        if cost is not None and (not math.isfinite(cost) or cost < 0):
            raise ValueError('invalid estimated cost')
        billed = pricing_row.get('billed_cost_usd')
        if billed is not None and (isinstance(billed, bool) or not isinstance(billed, (int, float))
                                   or not math.isfinite(billed) or billed < 0):
            raise ValueError('invalid billed cost')
        result.update(est_cost_usd=cost, billed_cost_usd=billed,
                      pricing_date=pricing_row['pricing_date'], pricing_source=source)
        if pricing_row.get('cost_is_plan') is True:
            result['subscription_equivalent_usd'] = cost
    return result
