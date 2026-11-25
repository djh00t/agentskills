"""Best-effort wake after a confirmed successful message_send.

Call wake_after_send(conversation_id, seq, send_result) only after success;
its return value is the original send result. CLI usage after success:
python cg_wake.py --conversation-id X --seq 1
Each invocation attempts one POST, waits at most five seconds for HTTP I/O,
and never retries or follows redirects. Credentials stay in memory.
"""
from __future__ import annotations

import argparse
import http.client
import json
import subprocess
from urllib.parse import urlsplit


def authorization_header(key: str) -> dict[str, str]:
    """Use the webhook's assumed Bearer authentication contract."""
    return {"Authorization": "Bearer " + key}


def wake_after_send(conversation_id: str, seq: int, send_result):
    """Attempt a wake without changing or inspecting the successful result."""
    values = []
    for account in ("webhook-key", "webhook-url"):
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "codex-grok-wake",
                 "-a", account, "-w"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
                text=True,
            )
            values.append(result.stdout.rstrip("\r\n") if result.returncode == 0 else "")
        except Exception:
            values.append("")
    key, url = values
    if not key or not url:
        print("wake disabled: keychain item absent")
        return send_result

    connection = None
    try:
        target = urlsplit(url)
        if target.scheme not in {"http", "https"} or not target.hostname or target.username:
            raise ValueError
        factory = (http.client.HTTPSConnection if target.scheme == "https"
                   else http.client.HTTPConnection)
        connection = factory(target.hostname, target.port, timeout=5)
        headers = authorization_header(key)
        headers["Content-Type"] = "application/json"
        body = json.dumps({"conversation_id": conversation_id, "seq": seq}).encode("utf-8")
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection.request("POST", path, body=body, headers=headers)
        status = connection.getresponse().status
        print("ping ok" if 200 <= status < 300 else f"ping failed ({int(status)})")
    except Exception:
        # Never render transport exceptions: they can contain credentials or URLs.
        print("ping failed (timeout)")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    return send_result


def main() -> None:
    """Wake only after the caller has confirmed message_send success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--seq", required=True, type=int)
    args = parser.parse_args()
    wake_after_send(args.conversation_id, args.seq, None)


if __name__ == "__main__":
    main()
