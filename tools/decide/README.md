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

## Request text and collection limits

Text permits ordinary Unicode spaces, emoji presentation sequences, and Hebrew marks. A leading nonspacing or enclosing mark is invalid. Other consecutive nonspacing or enclosing marks are limited to two. The `cc`, `depends_on`, and `pr.trailers` lists each allow at most 20 items.
