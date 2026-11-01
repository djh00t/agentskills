# Codex-Grok bridge envelope

`cg_envelope.py` parses and formats bounded `[CG ...]` messages. Parsing never
authorizes execution. A missing or unknown recipient produces an informational
message with no recipient. Decision messages retain their kind when the
recipient is unknown; warnings and the missing recipient still prevent routing.

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

`cg_inbox.py` reads paged Codex messages and prints a JSON routing plan:

```shell
python3 cg_inbox.py conversation --reader fixture_reader:read --log log.tsv
```

The imported reader is trusted operator code and **must be read-only**. The
bridge cannot prevent an imported reader from performing writes or sends.
The inbox itself does not create directories or lock files, write the log,
send, acknowledge, or launch messages. `MessageLog.snapshot()` returns one
consistent cursor/sequence snapshot without a writer lock; legacy migration is
computed in memory. Pass `--legacy PATH` to inspect an unmigrated legacy cursor.

> **Cursor semantics:** The first reader call receives the log's last handled
> sequence. Every later call receives the previous `next_cursor` unchanged.
> The reader accepts `(conversation_id, cursor, limit)` and returns a dictionary
> with a `messages` list and `next_cursor` (an integer/string token or `None`).
> Repeated tokens stop paging; 1000 pages is the hard cap. Repeated sequences
> appear only once. Handled and migrated sequences are skipped using the log's
> record-rejection rules.

Optional `--roles FILE` supplies validated role-to-agent-ID mappings, loaded once
per pass. Without it, recipients are unknown and entries include parse warnings
and no agent route. No roster IDs are embedded in code. Received-but-unrouted
sequences resurface with `pending: true` when returned by the reader; readers
must replay unresolved messages even when they precede the handled cursor.
Pending state is a separate read-only advisory observation and can change while
a writer runs. A plan neither claims nor changes message state.

`needs_owner` is advisory only, never an authorization gate. Decisions, parse
warnings, and sensitive terms set it. Every entry has
`execution_authorized: false`, including entries without the advisory flag.
Parse warnings remain visible. Invalid messages become flagged error entries
and do not abort other messages; invalid pages stop the pass with a clean error.
Excerpts are bounded to 200 characters.

`expires_at` is optional **epoch seconds**, from 0 through 253402300799 (the end
of year 9999). ISO strings, millisecond epochs, booleans, NaN, infinities, and
negative values are invalid. The clock is read once per pass; equality means
expired. Every entry includes `expired`; error entries use `false` because
expiry was not established. `--limit` must be positive.

Scenarios in `features/inbox.feature` map to the named executable tests in
`tests/test_cg_inbox.py`. All tests use local fixtures.
