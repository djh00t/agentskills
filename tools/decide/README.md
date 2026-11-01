# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
Use `verify-log` to check the stored event chain. It detects accidental damage and edits that leave the head unchanged. It is not a security boundary against the store user, who can rewrite both files.
Append initializes an empty head and removes stale head temporary files under the exclusive lock. If the head update fails after an event is written, append exits 5 and warns not to retry. Verification and reads can fail until the next append repairs the head. If the event directory sync fails, the error says not to retry because the event may already exist. A missing or inconsistent head is reported as a broken log. Under the exclusive lock, append advances a head that is exactly one valid event behind. If the final line is torn (no final newline and not valid JSON), stop all writers, preserve a copy of both files, and cut only the incomplete bytes after the last newline when the remaining log matches the head. Run `verify-log` before resuming. A missing head requires recovery from a trusted copy. Each event line is limited to 1 MiB.

## Exit codes

- `0`: success
- `2`: validation error or command usage error
- `3`: broken log or conflicting store operation
- `5`: store or environment error

## Global options

- `--json`: print machine-readable output.
- `--home DIR`: select the private store directory (or set `DECIDE_HOME`).

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.
