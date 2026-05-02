---
name: upstream-feed-failure-semantics
description: Keep third-party feed parsers resilient and explicit when external payload shape drifts, with loud failures instead of silent truncation.
argument-hint: "[feed-parser-module]"
disable-model-invocation: false
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Bash
  - Edit
---

# When to use

Use this when integrating or changing ingest/parsing for market-data sources, vendor APIs, CSV/XLSX/HTML/JSON scrapers, or webhook-style payload feeds.

This is for PRs like #574, where missing `aaData` silently became empty output instead of a hard failure.

# Inputs / context to gather

1. The source contract you depend on (field names, required arrays, accepted types).
2. Parser boundary behavior for missing/invalid fields.
3. Existing fixtures and failure-mode test coverage.
4. Any docs that describe source mapping or fallback behavior.

# Procedure

1. Define required fields and cardinality as a schema table before touching code.
2. Implement parser logic so required fields are explicit errors when absent or malformed.
3. Add fixtures for:
  - missing required key
  - wrong type for required key
  - partially valid payload with extra fields
  - canonical valid payload
4. Add parser assertions that guarantee mapping includes expected venue/source-specific suffixes and filters.
5. Ensure docs state the fail-closed behavior (for example, "malformed upstream payload fails ingestion").

# Hard Gates

- Never allow missing required payload fields to be interpreted as "zero rows" unless explicitly documented as intended.
- Never mix parser fallback behavior with silent defaults for required fields.
- Preserve source-specific mapping behavior in docs and code when sources move between parser styles.
- Add regression fixture for each upstream integration touched in the PR.

# Scorecard

- `fail_open_parser_count`: parser code paths that return success on malformed/missing required fields.
- `malformed_fixture_coverage`: malformed fixtures per parser change / required malformed cases.
- `contract_doc_drift_count`: doc statements that do not match parser fail/skip behavior.

Score formula:

```text
score = 100
  - 35 * fail_open_parser_count
  - 25 * (1 - min(malformed_fixture_coverage,1))
  - 15 * contract_doc_drift_count
```

# Self-Assessment

- What exact fields are mandatory for this feed and who owns the shape contract?
- What malformed payload should cause fail-closed?
- Is any source-specific mapping only partially covered by fixtures?
- Confidence 1-5 for parser strictness, fixture coverage, and docs fidelity.

After review, record any silent-failure feedback and add a dedicated malformed fixture plus assertion.

# User Feedback

- Ask after merge: `Did malformed feed payloads fail loudly instead of masking data? (1-5)`.
- If score is below 4, promote the miss to a required contract fixture in this skill.
