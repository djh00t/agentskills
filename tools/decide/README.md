# decide

`decide` is a deterministic queue for questions that only a human owner can answer.
The command line tool starts with `version`.

## Exit codes

- `0`: success
- `2`: validation error, command usage error, or lint hit
- `4`: input file not found or not a regular file
- `5`: invalid or inaccessible configuration or roster

## Global options

- `--json`: print machine-readable output.
- `--config PATH`: select the private configuration; `DECIDE_CONFIG` is the fallback.

Global options go before the command. For example, run `python3 decide.py --json version`.

## Tests

Run `make check` from this directory.

The generic lint API scans request strings and reports paths and pattern names.
It requires Python 3.11 or later. It normalizes Unicode and line wraps, but
does not decode encoded secrets or detect homoglyphs, spaced phone numbers,
or secrets split across fields or keys. It rejects unsupported value types
and requests nested more than 256 levels.
Use `lint-files PATH ...` to scan files with the generic, private, and mask patterns.
Wrapped private values are detected across adjacent lines.

Private config and roster files must be owned by the current user and have no group or other permissions. Roster paths must remain within the config directory and cannot contain symlinks or `..` components. Text scans reject fields or lines over 65,536 characters. Invalid UTF-8 is replaced during file scans; replacement characters can split a sensitive value and prevent a match. Use valid UTF-8 input.
