# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
Use `verify-log` to check the stored event chain. It detects accidental damage and edits that leave the head unchanged. It is not a security boundary against the store user, who can rewrite both files.
A missing or inconsistent head is reported as a broken log. Under the exclusive lock, append advances a head that is exactly one valid event behind. If the final line is torn (no final newline and not valid JSON), stop all writers, preserve a copy of both files, and cut only the incomplete bytes after the last newline when the remaining log matches the head. Run `verify-log` before resuming. A missing head requires recovery from a trusted copy. Each event line is limited to 1 MiB.

## Read commands

Use `status ID` to show an item, or `status --requester UUID --key KEY` to find it by requester and key. Use `list` to show items, `list --open` to omit closed items, and `list --requester UUID` to filter by requester. Both commands support the global `--json` option. A missing item returns exit code 4; an invalid argument returns 2, a broken log returns 3, and an unavailable store returns 5. Reads accept a valid log whose head is exactly one event behind; the next append repairs the head.

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

Text permits ordinary Unicode spaces and emoji sequences using symbols, variation selectors, and joiners. Keycap sequences and zero-width non-joiners are rejected. Nonspacing or enclosing marks cannot start text or follow whitespace. At most two such marks are allowed per run; Hebrew points require a Hebrew letter as the base and have a separate limit of four per run. The `cc`, `depends_on`, and `pr.trailers` lists each allow at most 20 items.

Use `verify-pr <id>` to print a JSON plan; the operator makes the calls and no token is needed. Fail closed if a reviews or check-runs page is full, or if check-run `total_count` exceeds the returned runs.
