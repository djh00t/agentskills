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
