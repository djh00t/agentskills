# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
The command line tool starts with `version`; later commands live in their own
`decide_*.py` module.

## Exit codes

- `0`: success
- `2`: validation error or command usage error
- `3`: conflict or stale state
- `4`: item not found
- `5`: configuration or environment error

## Global options

- `--home DIR`: set the data directory (or use `DECIDE_HOME`).
- `--config FILE`: set the config file (or use `DECIDE_CONFIG`).
- `--json`: print machine-readable output.

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.

The generic lint API scans request strings and reports paths and pattern names.
It normalizes Unicode and line wraps, but does not decode encoded secrets.
It is not yet connected to a command.
