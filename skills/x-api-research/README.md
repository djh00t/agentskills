# x-api-research

Skill package for collecting X content with the Python XDK.

## Quick start

1. Create a skill-specific environment with uv:

```bash
uv venv .venv
```

2. Install dependencies:

```bash
uv sync --group dev
```

3. Run quality gates:

```bash
make check
```

## Environment variables

- `X_BEARER_TOKEN` (required)
- `X_USER_ACCESS_TOKEN` (required for bookmarks)
- `X_USER_ID` (required for bookmarks unless `--user-id` is passed)

Optional OAuth token lifecycle vars:

- `X_CLIENT_ID`
- `X_CLIENT_SECRET`
- `X_REDIRECT_URI`
- `X_REFRESH_TOKEN`
- `X_SCOPES`

## Common commands

- Search posts: `uv run python scripts/search_posts.py --query 'OpenAI lang:en'`
- Bookmarks: `uv run python scripts/get_bookmarks.py --pages 1`
- Stream rules: `uv run python scripts/stream_rules.py get`
- Stream posts: `uv run python scripts/stream_filtered_posts.py --max-events 20`
- User posts: `uv run python scripts/get_user_posts.py --user-id 2244994945`
- Post lookup: `uv run python scripts/get_posts_by_ids.py --ids 20,24`
- List posts: `uv run python scripts/get_list_posts.py --list-id 1234567890`
- News lookup: `uv run python scripts/search_news.py --query 'market volatility'`
