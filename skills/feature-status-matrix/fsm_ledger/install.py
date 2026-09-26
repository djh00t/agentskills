"""Install / uninstall harness hooks for fsm-ledger.

Merges carefully with *.bak-fsm-YYYYMMDD backups and fsm-ledger markers.
Never clobbers existing Codex plugin hooks (brute / ponytail / context-mode).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .attribute import matrices_root

SKILL_ROOT = Path(__file__).resolve().parents[1]
HARNESSES = SKILL_ROOT / "harnesses"
MARKER = "fsm-ledger"
TODAY = date.today().strftime("%Y%m%d")

AGENT_BRAIN_PROJECT = {
    "id": "agent-brain",
    "roots": [
        "/Users/djh/work/src/github.com_local/djh00t/agent-brain",
        "/Users/djh/work/agent-brain-poc",
    ],
    "remote_contains": "djh00t/agent-brain",
}


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    bak = path.with_name(path.name + f".bak-fsm-{TODAY}")
    if not bak.exists():
        shutil.copy2(path, bak)
    return bak


def ensure_project_scaffold(project: str = "agent-brain") -> dict[str, Any]:
    root = matrices_root() / project
    root.mkdir(parents=True, exist_ok=True)
    project_json = root / "project.json"
    usage = root / "usage.jsonl"
    created: list[str] = []
    if not project_json.exists():
        project_json.write_text(json.dumps(AGENT_BRAIN_PROJECT, indent=2) + "\n", encoding="utf-8")
        created.append(str(project_json))
    if not usage.exists():
        usage.write_text("", encoding="utf-8")
        created.append(str(usage))
    return {"root": str(root), "created": created}


def install_codex() -> dict[str, Any]:
    """Install Codex plugin under skill marketplace; merge config.toml safely."""
    plugin_src = HARNESSES / "codex"
    marketplace = HARNESSES / "codex-marketplace"
    plugin_dst = marketplace / "plugins" / "fsm-ledger"
    plugin_dst.parent.mkdir(parents=True, exist_ok=True)
    if plugin_dst.exists() or plugin_dst.is_symlink():
        if plugin_dst.is_symlink() or plugin_dst.is_file():
            plugin_dst.unlink()
        else:
            shutil.rmtree(plugin_dst)
    shutil.copytree(plugin_src, plugin_dst)

    config = Path.home() / ".codex" / "config.toml"
    result: dict[str, Any] = {
        "harness": "codex",
        "plugin": str(plugin_dst),
        "reminders": [
            "Codex hooks require trust — accept the fsm-ledger plugin hooks when prompted.",
            "Existing brute / ponytail / context-mode hooks are untouched.",
        ],
    }
    if not config.exists():
        result["ok"] = False
        result["error"] = f"missing {config}"
        return result

    text = config.read_text(encoding="utf-8")
    if f"# {MARKER} BEGIN" in text:
        result["ok"] = True
        result["skipped"] = "already installed"
        return result

    bak = _backup(config)
    block = (
        f"\n\n# {MARKER} BEGIN — shared usage ledger (do not remove marker lines)\n"
        f"[marketplaces.fsm-ledger-local]\n"
        f'source = "{marketplace}"\n'
        f'source_type = "local"\n'
        f"\n"
        f'[plugins."fsm-ledger@fsm-ledger-local"]\n'
        f"enabled = true\n"
        f"# {MARKER} END\n"
    )
    config.write_text(text.rstrip() + block, encoding="utf-8")
    result["ok"] = True
    result["backup"] = str(bak) if bak else None
    result["config"] = str(config)
    return result


def uninstall_codex() -> dict[str, Any]:
    config = Path.home() / ".codex" / "config.toml"
    if not config.exists():
        return {"harness": "codex", "ok": True, "skipped": "no config"}
    text = config.read_text(encoding="utf-8")
    new, n = re.subn(
        rf"\n# {MARKER} BEGIN.*?# {MARKER} END\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )
    if n:
        _backup(config)
        config.write_text(new, encoding="utf-8")
    return {"harness": "codex", "ok": True, "removed_blocks": n}


def install_claude() -> dict[str, Any]:
    settings = Path.home() / ".claude" / "settings.json"
    hook_script = HARNESSES / "claude" / "stop_hook.py"
    result: dict[str, Any] = {"harness": "claude", "hook": str(hook_script)}
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("{}\n", encoding="utf-8")

    bak = _backup(settings)
    data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    hooks = data.setdefault("hooks", {})
    stop_list = hooks.setdefault("Stop", [])

    cmd = f'PYTHONPATH="{SKILL_ROOT}" python3 "{hook_script}"'
    stop_list[:] = [entry for entry in stop_list if MARKER not in json.dumps(entry)]
    stop_list.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": cmd,
                    "statusMessage": "fsm-ledger usage capture",
                }
            ],
            MARKER: True,
        }
    )
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result["ok"] = True
    result["backup"] = str(bak) if bak else None
    result["note"] = "PreToolUse hooks preserved; Stop hook merged."
    return result


def uninstall_claude() -> dict[str, Any]:
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.exists():
        return {"harness": "claude", "ok": True, "skipped": "no settings"}
    bak = _backup(settings)
    data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    hooks = data.get("hooks") or {}
    for key in list(hooks.keys()):
        if isinstance(hooks[key], list):
            hooks[key] = [e for e in hooks[key] if MARKER not in json.dumps(e)]
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"harness": "claude", "ok": True, "backup": str(bak) if bak else None}


def install_pi() -> dict[str, Any]:
    settings = Path.home() / ".pi" / "agent" / "settings.json"
    pkg = HARNESSES / "pi"
    result: dict[str, Any] = {"harness": "pi", "package": str(pkg)}
    if not settings.exists():
        return {"harness": "pi", "ok": False, "error": f"missing {settings}"}
    bak = _backup(settings)
    data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    packages = data.setdefault("packages", [])
    packages[:] = [p for p in packages if MARKER not in str(p) and str(pkg) not in str(p)]
    packages.append(str(pkg))
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result["ok"] = True
    result["backup"] = str(bak) if bak else None
    result["note"] = "Pi package added; extension listens on message_end."
    return result


def uninstall_pi() -> dict[str, Any]:
    settings = Path.home() / ".pi" / "agent" / "settings.json"
    if not settings.exists():
        return {"harness": "pi", "ok": True, "skipped": "no settings"}
    bak = _backup(settings)
    data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    pkg = str(HARNESSES / "pi")
    packages = data.get("packages") or []
    data["packages"] = [p for p in packages if MARKER not in str(p) and pkg not in str(p)]
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"harness": "pi", "ok": True, "backup": str(bak) if bak else None}


def install_opencode() -> dict[str, Any]:
    """Phase-2 stub: write enable hint; do not rewrite opencode.jsonc."""
    cfg = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    plugin = HARNESSES / "opencode" / "plugin.mjs"
    hint = Path.home() / ".config" / "opencode" / "fsm-ledger.ENABLE.txt"
    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text(
        f"# {MARKER}\n"
        f"Add to plugin array in opencode.jsonc:\n"
        f'  "{plugin}"\n',
        encoding="utf-8",
    )
    return {
        "harness": "opencode",
        "ok": True,
        "stub": True,
        "plugin": str(plugin),
        "hint": str(hint),
        "note": f"Phase-2 stub. Manual enable via {cfg}; jsonc left untouched.",
    }


def uninstall_opencode() -> dict[str, Any]:
    hint = Path.home() / ".config" / "opencode" / "fsm-ledger.ENABLE.txt"
    if hint.exists():
        hint.unlink()
    return {"harness": "opencode", "ok": True, "stub": True}


INSTALLERS = {
    "codex": install_codex,
    "claude": install_claude,
    "pi": install_pi,
    "opencode": install_opencode,
}
UNINSTALLERS = {
    "codex": uninstall_codex,
    "claude": uninstall_claude,
    "pi": uninstall_pi,
    "opencode": uninstall_opencode,
}


def install(harnesses: list[str]) -> list[dict[str, Any]]:
    scaffold = ensure_project_scaffold("agent-brain")
    results: list[dict[str, Any]] = [{"scaffold": scaffold}]
    for name in harnesses:
        fn = INSTALLERS.get(name.strip().lower())
        if not fn:
            results.append({"harness": name, "ok": False, "error": "unknown harness"})
            continue
        results.append(fn())
    return results


def uninstall(harnesses: Optional[list[str]] = None) -> list[dict[str, Any]]:
    names = harnesses or list(UNINSTALLERS)
    return [UNINSTALLERS[n]() for n in names if n in UNINSTALLERS]
