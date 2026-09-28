"""Install / uninstall harness hooks for fsm-ledger.

Merges carefully with *.bak-fsm-YYYYMMDD backups and fsm-ledger markers.
Never clobbers existing Codex plugin hooks (brute / ponytail / context-mode).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
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


def _owned_plugin(path: Path) -> bool:
    manifest = path / ".codex-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name") == MARKER
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return False


def install_codex() -> dict[str, Any]:
    """Copy the plugin into the personal marketplace and prepare manual install."""
    plugin_src = HARNESSES / "codex"
    catalog_root = Path.home() / ".agents" / "plugins"
    plugin_dst = Path.home() / "plugins" / "fsm-ledger"
    catalog = catalog_root / "marketplace.json"

    data: dict[str, Any]
    catalog_changed = not catalog.exists()
    if catalog.exists():
        try:
            data = json.loads(catalog.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"harness": "codex", "ok": False, "error": f"invalid {catalog}: {exc}"}
        if not isinstance(data, dict) or not isinstance(data.get("plugins", []), list):
            return {"harness": "codex", "ok": False, "error": f"invalid plugin catalog {catalog}"}
    else:
        data = {"name": "local", "interface": {"displayName": "Local Plugins"}, "plugins": []}

    if plugin_dst.exists() or plugin_dst.is_symlink():
        if plugin_dst.is_symlink() or not _owned_plugin(plugin_dst):
            return {
                "harness": "codex",
                "ok": False,
                "error": f"refusing to replace existing unrelated plugin path: {plugin_dst}",
            }

    entry = {
        "name": MARKER,
        "source": {"source": "local", "path": "./plugins/fsm-ledger"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    plugins = data["plugins"]
    updated = False
    merged_plugins = []
    for item in plugins:
        if isinstance(item, dict) and item.get("name") == MARKER:
            if not updated:
                merged_plugins.append(entry)
                updated = True
            continue
        merged_plugins.append(item)
    if not updated:
        merged_plugins.append(entry)
    catalog_changed = catalog_changed or merged_plugins != plugins
    data["plugins"] = merged_plugins

    catalog.parent.mkdir(parents=True, exist_ok=True)
    stale_dst = catalog_root / "plugins" / "fsm-ledger"
    if stale_dst != plugin_dst and stale_dst.is_dir() and not stale_dst.is_symlink():
        if _owned_plugin(stale_dst):
            shutil.rmtree(stale_dst)

    plugin_dst.parent.mkdir(parents=True, exist_ok=True)
    if plugin_dst.exists() or plugin_dst.is_symlink():
        if plugin_dst.is_symlink() or plugin_dst.is_file():
            plugin_dst.unlink()
        else:
            shutil.rmtree(plugin_dst)
    shutil.copytree(plugin_src, plugin_dst)

    bak_catalog = _backup(catalog) if catalog_changed and catalog.exists() else None
    if catalog_changed:
        catalog.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    config = Path.home() / ".codex" / "config.toml"
    result: dict[str, Any] = {
        "harness": "codex",
        "plugin": str(plugin_dst),
        "catalog": str(catalog),
        "reminders": [
            "Run `codex plugin add fsm-ledger@local`, then accept/trust the fsm-ledger hooks when prompted.",
            "Existing brute / ponytail / context-mode hooks are untouched.",
        ],
    }
    result["ok"] = True
    result["catalog_backup"] = str(bak_catalog) if bak_catalog else None
    if config.exists():
        text = config.read_text(encoding="utf-8")
        new, count = re.subn(rf"^# {MARKER} BEGIN.*?^# {MARKER} END\n?", "", text, flags=re.DOTALL | re.MULTILINE)
        if count:
            bak = _backup(config)
            config.write_text(new, encoding="utf-8")
            result["legacy_config_backup"] = str(bak) if bak else None
            result["migrated_legacy_config"] = True
    return result


def uninstall_codex() -> dict[str, Any]:
    cli = shutil.which("codex")
    remove_result: dict[str, Any]
    if not cli:
        remove_result = {"ok": False, "skipped": "codex CLI unavailable"}
    else:
        try:
            proc = subprocess.run(
                [cli, "plugin", "remove", f"{MARKER}@local"],
                capture_output=True,
                text=True,
                check=False,
            )
            remove_result = {"ok": proc.returncode == 0, "returncode": proc.returncode}
            if proc.stdout:
                remove_result["stdout"] = proc.stdout.strip()
            if proc.stderr:
                remove_result["stderr"] = proc.stderr.strip()
        except OSError as exc:
            remove_result = {"ok": False, "error": str(exc)}

    if not remove_result["ok"]:
        return {
            "harness": "codex",
            "ok": False,
            "codex_remove": remove_result,
            "removed_blocks": 0,
            "removed_catalog": False,
            "removed_plugin": False,
        }

    config = Path.home() / ".codex" / "config.toml"
    removed_blocks = 0
    backup = None
    if config.exists():
        text = config.read_text(encoding="utf-8")
        new, removed_blocks = re.subn(rf"^# {MARKER} BEGIN.*?^# {MARKER} END\n?", "", text, flags=re.DOTALL | re.MULTILINE)
        if removed_blocks:
            backup = _backup(config)
            config.write_text(new, encoding="utf-8")

    catalog = Path.home() / ".agents" / "plugins" / "marketplace.json"
    removed_catalog = False
    if catalog.exists():
        data = json.loads(catalog.read_text(encoding="utf-8"))
        plugins = data.get("plugins", []) if isinstance(data, dict) else []
        kept = [item for item in plugins if not (isinstance(item, dict) and item.get("name") == MARKER)]
        removed_catalog = len(kept) != len(plugins)
        if removed_catalog:
            _backup(catalog)
            data["plugins"] = kept
            catalog.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    plugin = Path.home() / "plugins" / MARKER
    removed_plugin = False
    if remove_result["ok"] and not plugin.is_symlink() and _owned_plugin(plugin):
        shutil.rmtree(plugin)
        removed_plugin = True
    return {
        "harness": "codex",
        "ok": True,
        "removed_blocks": removed_blocks,
        "backup": str(backup) if backup else None,
        "removed_catalog": removed_catalog,
        "codex_remove": remove_result,
        "removed_plugin": removed_plugin,
    }


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
