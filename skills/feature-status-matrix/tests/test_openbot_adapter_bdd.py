"""Executable offline acceptance scenarios for the OpenBot adapter.

The fixtures model two ordered releases and local issue-detail readback. The
optional ``blocker_statuses`` argument is a comma-separated extension to the
default ``BLOCKED`` status; values are trimmed and matched case-insensitively.
All delivery goes to ReplyCapture, and network entry points are denied.
"""
import copy
import json
import re
import shutil
import socket
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from tools.openbot_adapter import handle_request  # noqa: E402


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "openbot_adapter"
ISSUE_LINK = re.compile(r"\[Issue\]\(<(https://github\.com/[^>]+)>\)")


class FixtureSource:
    """Local-only source with the adapter's release and item interface."""

    def __init__(self, fixture_path):
        self.data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self.list_item_calls = []

    def list_releases(self):
        return copy.deepcopy(self.data["releases"])

    def list_items(self, release_id):
        self.list_item_calls.append(release_id)
        return copy.deepcopy(self.data["items"][release_id])

    def read_issue_detail(self, issue_url):
        """Resolve a captured fixture URL without making a network request."""
        return copy.deepcopy(self.data["issue_details"][issue_url])


class ReplyCapture:
    """Fake inline sink that rejects duplicate replies and performs no send."""

    def __init__(self):
        self.replies = []

    def reply(self, markdown):
        if self.replies:
            raise AssertionError("the adapter attempted more than one inline reply")
        self.replies.append(markdown)

    def issue_urls(self):
        return ISSUE_LINK.findall(self.replies[0]) if self.replies else []

    def read_linked_issue_details(self, source):
        return [source.read_issue_detail(url) for url in self.issue_urls()]


class OpenBotAdapterBDDTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="openbot-adapter-fixture-")
        self.addCleanup(temporary.cleanup)
        self.fixture_path = Path(temporary.name) / "source.json"
        shutil.copyfile(FIXTURE_DIR / "source.json", self.fixture_path)
        self.source = FixtureSource(self.fixture_path)
        self.sink = ReplyCapture()

    def request(self, request, *, blocker_statuses=None):
        # Calls to normal network APIs are test failures. The source and sink
        # above serve the entire request from the copied synthetic fixture.
        with patch.object(
            socket, "create_connection",
            side_effect=AssertionError("offline acceptance must not connect"),
        ), patch.object(
            socket.socket, "connect",
            side_effect=AssertionError("offline acceptance must not open sockets"),
        ), patch.object(
            socket, "getaddrinfo",
            side_effect=AssertionError("offline acceptance must not resolve hosts"),
        ), patch.object(
            urllib.request, "urlopen",
            side_effect=AssertionError("offline acceptance must not open URLs"),
        ):
            if blocker_statuses is None:
                return handle_request(request, self.source, self.sink)
            return handle_request(
                request, self.source, self.sink,
                blocker_statuses=blocker_statuses,
            )

    def golden(self, name):
        return (FIXTURE_DIR / name).read_text(encoding="utf-8")

    def test_full_mode_matches_ordered_golden_and_reads_linked_fixture_details(self):
        markdown = self.request({"mode": "full"})

        self.assertEqual(self.sink.replies, [markdown])
        self.assertEqual(self.source.list_item_calls, ["rel-2026-01", "rel-2026-02"])
        self.assertLess(markdown.index("## rel-2026-01"), markdown.index("## rel-2026-02"))

        expected_urls = [
            item["issue_url"]
            for release in self.source.data["releases"]
            for item in self.source.data["items"][release["id"]]
        ]
        self.assertEqual(self.sink.issue_urls(), expected_urls)
        linked_details = self.sink.read_linked_issue_details(self.source)
        expected_details = [
            self.source.data["issue_details"][url] for url in expected_urls
        ]
        self.assertEqual(linked_details, expected_details)
        self.assertEqual(
            [detail["acceptance"] for detail in linked_details],
            [
                "The blocked release is marked while its issue stays linked.",
                "Cell text keeps its pipe and line break in one table row.",
                "Accepted work remains visible in release order.",
                "Configured status matching ignores case and surrounding spaces.",
                "An unknown status stays visible without a blocker marker.",
            ],
        )
        self.assertEqual(markdown, self.golden("full.md"))

    def test_release_mode_matches_golden_for_only_the_selected_release(self):
        markdown = self.request({"mode": "release", "release": "rel-2026-02"})

        self.assertEqual(self.sink.replies, [markdown])
        self.assertNotIn("## rel-2026-01", markdown)
        self.assertEqual(self.source.list_item_calls, ["rel-2026-02"])
        self.assertEqual(markdown, self.golden("release-2026-02.md"))

    def test_csv_blocker_configuration_extends_default_and_leaves_unknown_visible(self):
        markdown = self.request(
            {"mode": "full"}, blocker_statuses=" waiting , SHIPPED "
        )

        self.assertIn("| Release notes | ⚠️ BLOCKED |", markdown)
        self.assertIn("| Pipe \\| and line<br>break | ⚠️ Waiting |", markdown)
        self.assertIn("| Export status report | ⚠️ Shipped |", markdown)
        self.assertIn("| Mystery state stays visible | UNRECOGNIZED |", markdown)
        self.assertNotIn("⚠️ UNRECOGNIZED", markdown)
        self.assertEqual(self.sink.replies, [markdown])
        self.assertEqual(markdown, self.golden("full-extended-blockers.md"))

    def test_invalid_mode_raises_value_error_without_reply(self):
        with self.assertRaises(ValueError):
            self.request({"mode": "compact"})
        self.assertEqual(self.sink.replies, [])

    def test_missing_release_selector_raises_value_error_without_reply(self):
        with self.assertRaises(ValueError):
            self.request({"mode": "release"})
        self.assertEqual(self.sink.replies, [])

    def test_unknown_release_selector_raises_value_error_without_reply(self):
        with self.assertRaises(ValueError):
            self.request({"mode": "release", "release": "rel-unknown"})
        self.assertEqual(self.sink.replies, [])

    def test_malformed_blocker_configuration_raises_value_error_without_reply(self):
        with self.assertRaises(ValueError):
            self.request({"mode": "full"}, blocker_statuses=" , ")
        self.assertEqual(self.sink.replies, [])


if __name__ == "__main__":
    unittest.main()
