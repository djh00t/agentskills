# Codex-Grok bridge envelope

`cg_envelope.py` parses and formats bounded `[CG ...]` messages. Parsing never
authorizes execution. A missing or unknown recipient produces an informational
message with no recipient.

`roles.json` maps role names to agent IDs. The envelope validates role names and
uses the role names for recipient checks; agent IDs are currently unused.
The shipped `{}` roster is invalid, so every parse and format call rejects it
until a populated roster is supplied. A CRLF-terminated header does not match;
the parser treats the full message as informational text with no header.

## Checks

```shell
make check
```
