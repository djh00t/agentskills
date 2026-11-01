# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
Use `verify-log` to check the stored event chain. It detects accidental damage and edits that leave the head unchanged. It is not a security boundary against the store user, who can rewrite both files.
A missing or inconsistent head is reported as a broken log. Under the exclusive lock, append advances a head that is exactly one valid event behind. If the final line is torn (no final newline and not valid JSON), stop all writers, preserve a copy of both files, and cut only the incomplete bytes after the last newline when the remaining log matches the head. Run `verify-log` before resuming. A missing head requires recovery from a trusted copy. Each event line is limited to 1 MiB.

## Exit codes

- `0`: success
- `2`: validation error or command usage error
- `3`: broken log or conflicting store operation

## Global options

- `--json`: print machine-readable output.
- `--home DIR`: select the private store directory (or set `DECIDE_HOME`).

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.

## Request text and collection limits

Text permits ordinary Unicode spaces, emoji presentation sequences, and Hebrew marks. A leading nonspacing or enclosing mark is invalid. Other consecutive nonspacing or enclosing marks are limited to two. The `cc`, `depends_on`, and `pr.trailers` lists each allow at most 20 items.
