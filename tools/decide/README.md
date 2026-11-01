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

Text permits ordinary Unicode spaces and emoji sequences using symbols, variation selectors, and joiners. Keycap sequences and zero-width non-joiners are rejected. Nonspacing or enclosing marks cannot start text or follow whitespace. At most two such marks are allowed per run; Hebrew points require a Hebrew letter as the base and have a separate limit of four per run. The `cc`, `depends_on`, and `pr.trailers` lists each allow at most 20 items.
