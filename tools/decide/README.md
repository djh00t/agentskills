# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
The command line tool starts with `version`.

## Exit codes

- `0`: success
- `2`: validation error or command usage error
- `3`: conflict or stale state
- `4`: item not found
- `5`: configuration or environment error

## Global options

- `--json`: print machine-readable output.

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.

The generic lint API scans request strings and reports paths and pattern names.
It normalizes Unicode and line wraps, but does not decode encoded secrets.
It is not yet connected to a command.

Private config and roster files must be owned by the current user and have no group or other permissions. Roster paths must remain within the config directory and cannot contain symlinks or `..` components. Text scans reject fields or lines over 65,536 characters. Invalid UTF-8 is replaced during file scans; replacement characters can split a sensitive value and prevent a match. Use valid UTF-8 input.
