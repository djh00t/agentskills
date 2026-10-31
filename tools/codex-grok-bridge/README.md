# Codex-Grok bridge envelope

`cg_envelope.py` parses and formats bounded `[CG ...]` messages. Parsing never
authorizes execution. A missing or unknown recipient produces an informational
message with no recipient.

`roles.json` maps role names to agent IDs. The envelope validates role names and
uses the role names for recipient checks; agent IDs are currently unused.
The shipped `{}` roster is invalid, so every parse and format call rejects it
until a populated roster is supplied. A CRLF-terminated header does not match;
the parser treats the full message as informational text with no header.

`cg_log.py` stores message state in an atomic, locked TSV log. Each sequence is
recorded once and can move from `received` to `routed` to `acked` to `done`, or
to `failed` from any nonterminal state. New records must start as `received`
and exceed the cursor only when it has reached a stored, handled row. Existing
sequence records are unchanged on replay, including handled and migrated rows.
Before any row is handled, out-of-order arrivals such as 2 then 1 are accepted.
New sequences at or below a handled cursor raise `LogError`.
The migration note
`migrated legacy cursor` is reserved: neither public write method accepts it,
and the terminal migration row cannot be changed.

`received_at` holds the receive timestamp. Text fields use CSV escaping with a
TSV delimiter, including embedded tabs, quotes, and newlines.

The cursor starts immediately before the lowest stored sequence (zero for an
empty log). It advances through consecutive `routed`, `acked`, `done`, or
`failed` rows; missing and `received` rows stop it. A terminal failure counts as
handled and does not block later progress. For example, sequence 4
`received` and sequence 5 `routed` return cursor 3.

A legacy last-sequence file can seed a missing log on first use. Values must be
one non-negative ASCII decimal integer and are stored in canonical decimal
form. A UTF-8 BOM and surrounding whitespace are accepted; a final newline is
optional. Empty, non-numeric, and multiple values are rejected. A truncated
numeric prefix cannot be distinguished from a complete integer; legacy writers
must replace the file atomically.
Once the log exists (even with only a header), an unconsumed legacy value at or
below the log cursor is ignored; a higher value raises `LogError`. The persisted
migration row marks the legacy file as consumed, so leaving that file in place
does not stop later progress. `cursor()` writes only to persist this seed once;
this lets a later reader recover the cursor without the legacy file. It also
creates the parent directory and lock file when needed. Ordinary cursor reads
do not rewrite the TSV.

Log and lock files are created with mode `0600`. Writes sync the temporary file,
replace the log atomically, then sync the parent directory. A directory-fsync
`OSError` can occur after `os.replace` has already installed the new log. Read
back the log before retrying; the error does not prove durable completion.
POSIX `fcntl` is required. `flock` is unreliable on NFS; use a local filesystem
with cooperating writers. Invalid headers, rows, sequences, duplicate
sequences, and unknown states raise `LogError` without rewriting the log.

## Checks

```shell
make check
```

The repository workflow runs `make quality-gates` from this folder. It includes
`make check`; there is no root quality-gates target. All checks run offline.
The scenarios in `features/message_log.feature` are implemented by the named
`unittest` methods in `tests/test_cg_log.py` and run with `make check`.
