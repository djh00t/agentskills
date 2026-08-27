---
name: x-api-research
description: Retrieve and analyze X content using the official Python XDK. Use this skill when an agent needs to search posts by topic, pull bookmarks for analysis, stream near real-time filtered posts, fetch posts from specific users, look up posts by ID or IDs (including edit history fields), read list timeline posts, or query the X news endpoint for headlines.
---

# X API Research

## Overview
Use this skill to gather X-native evidence for company, executive, market sentiment, and breaking news analysis. The skill uses Python scripts in `scripts/` and expects credentials in environment variables.

## Environment Variables
Set these before running scripts.

- `X_BEARER_TOKEN` (required): app token for search, user/list timelines, post lookup, stream, and news.
- `X_USER_ACCESS_TOKEN` (required for bookmarks): OAuth2 user-context token.
- `X_USER_ID` (required for bookmarks unless passed as `--user-id`): user id for bookmark lookup.
- `X_CLIENT_ID` (optional): OAuth2 client id for token workflows.
- `X_CLIENT_SECRET` (optional): OAuth2 client secret for token workflows.
- `X_REDIRECT_URI` (optional): OAuth2 redirect URI.
- `X_REFRESH_TOKEN` (optional): OAuth2 refresh token.
- `X_SCOPES` (optional): OAuth2 scopes list for token workflows.

## Setup
Run all commands from this skill directory.

```bash
make install
```

This creates and syncs a skill-specific `.venv` with `uv`.

## Capabilities

### 1. Search Topic Content
Use `scripts/search_posts.py` for recent or full-archive search.

```bash
uv run python scripts/search_posts.py \
  --query '(from:OpenAI OR OpenAI) lang:en -is:retweet' \
  --scope recent \
  --max-results 50 \
  --pages 2
```

### 2. Retrieve Bookmarks
Use `scripts/get_bookmarks.py` for private bookmark analysis.

```bash
uv run python scripts/get_bookmarks.py --pages 2
```

### 3. Stream Near Real-Time Posts
Use `scripts/stream_filtered_posts.py` after configuring rules.

```bash
uv run python scripts/stream_rules.py get
uv run python scripts/stream_rules.py update --add-json '[{"value":"OpenAI lang:en -is:retweet","tag":"openai"}]'
uv run python scripts/stream_filtered_posts.py --max-events 100
```

### 4. Retrieve Posts From Specific Users
Use `scripts/get_user_posts.py`.

```bash
uv run python scripts/get_user_posts.py --user-id 2244994945 --pages 1
```

### 5. Retrieve Posts By ID or IDs
Use `scripts/get_posts_by_ids.py` to verify availability and inspect edit history fields.

```bash
uv run python scripts/get_posts_by_ids.py --id 20
uv run python scripts/get_posts_by_ids.py --ids 20,24
```

### 6. Retrieve Posts From a List Timeline
Use `scripts/get_list_posts.py`.

```bash
uv run python scripts/get_list_posts.py --list-id 1234567890 --pages 2
```

### 7. Lookup News and Headlines
Use `scripts/search_news.py`.

```bash
uv run python scripts/search_news.py --query 'NVIDIA earnings' --max-results 20
```

## Output Contract
- Non-stream scripts output one JSON document with:
  - `ok`: boolean success flag
  - `source`: operation identifier
  - payload data
- Stream script outputs JSON Lines (one event per line).
- Add `--out <path>` to write output to a file.

## Failure Modes
- Missing `X_BEARER_TOKEN`: script exits with explicit config error.
- Missing bookmark user token/id: bookmark script exits with required env guidance.
- API errors: script returns non-zero and prints JSON error details.

## References
- X API introduction: `https://docs.x.com/x-api/introduction`
- Python XDK overview: `https://docs.x.com/xdks/python/overview`
