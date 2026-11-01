# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
The command line tool starts with `version`.

## Exit codes

- `0`: success
- `2`: validation error or command usage error

## Global options

- `--json`: print machine-readable output.

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.

The generic lint API scans request strings and reports paths and pattern names.
It requires Python 3.11 or later. It normalizes Unicode and line wraps, but
does not decode encoded secrets or detect homoglyphs, spaced phone numbers,
or secrets split across fields or keys. It rejects unsupported value types
and requests nested more than 256 levels.
It is not yet connected to a command.
