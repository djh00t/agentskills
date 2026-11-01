# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
Use `verify-log` to check the stored event chain. It detects partial edits and truncation, but a writer who can rewrite both the log and its head can forge a new chain.
A missing or incomplete head is reported as a broken log; restore the log and head together from a trusted backup.

## Exit codes

- `0`: success
- `2`: validation error or command usage error

## Global options

- `--json`: print machine-readable output.
- `--home DIR`: select the private store directory (or set `DECIDE_HOME`).

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.
