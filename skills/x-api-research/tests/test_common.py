from __future__ import annotations

from pathlib import Path

from scripts._common import collect_pages, parse_csv_option, parse_csv_options, to_plain


class _ModelLike:
    def model_dump(self, exclude_none: bool = True):
        return {"id": "123", "exclude_none": exclude_none}


def test_parse_csv_option_splits_values() -> None:
    assert parse_csv_option("a,b, c") == ["a", "b", "c"]


def test_parse_csv_options_merges_values() -> None:
    assert parse_csv_options(["a,b", "c", "d,e"]) == ["a", "b", "c", "d", "e"]


def test_collect_pages_honors_limit() -> None:
    iterator = iter([{"data": [1]}, {"data": [2]}, {"data": [3]}])
    pages = collect_pages(iterator, page_limit=2)
    assert pages == [{"data": [1]}, {"data": [2]}]


def test_to_plain_handles_models_and_paths() -> None:
    payload = {"obj": _ModelLike(), "path": Path("tmp/file.json")}
    plain = to_plain(payload)
    assert plain["obj"] == {"id": "123", "exclude_none": True}
    assert plain["path"] == "tmp/file.json"
