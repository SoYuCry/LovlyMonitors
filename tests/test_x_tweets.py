"""Regression tests for the minimal X/Twitter monitor."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from lovlymonitors.monitors.x_tweets import (
    TweetJsonlStore,
    XApiClient,
    XApiError,
    normalize_username,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = text or json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> FakeResponse:
        self.calls.append((url, params))
        if url.endswith("/users/by/username/jack"):
            return FakeResponse(200, {"data": {"id": "12"}})
        if url.endswith("/users/12/tweets"):
            return FakeResponse(200, {"data": [{"id": "101", "text": "hello"}]})
        return FakeResponse(404, {"title": "not found"})


class XTweetsTests(unittest.TestCase):
    def test_normalize_username(self) -> None:
        self.assertEqual(normalize_username(" @jack "), "jack")
        self.assertEqual(normalize_username("user_123"), "user_123")
        with self.assertRaises(ValueError):
            normalize_username("")
        with self.assertRaises(ValueError):
            normalize_username("bad-name")

    def test_jsonl_store_dedupes_existing_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jack.jsonl"
            path.write_text('{"id":"100","text":"old"}\n', encoding="utf-8")
            store = TweetJsonlStore(path)
            saved = store.append_new(
                [
                    {"id": "100", "text": "old duplicate"},
                    {"id": "102", "text": "newer"},
                    {"id": "101", "text": "new"},
                ]
            )
            self.assertEqual([tweet["id"] for tweet in saved], ["101", "102"])
            self.assertEqual(store.newest_id(), "102")
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)

    def test_x_api_client_uses_bearer_and_parses_posts(self) -> None:
        session = FakeSession()
        client = XApiClient("token", session=session)  # type: ignore[arg-type]
        self.assertEqual(session.headers["Authorization"], "Bearer token")
        user_id = client.user_id_for_username("jack")
        tweets = client.latest_tweets(user_id, since_id="100", max_results=1)
        self.assertEqual(user_id, "12")
        self.assertEqual(tweets, [{"id": "101", "text": "hello"}])
        self.assertEqual(session.calls[-1][1]["since_id"], "100")
        self.assertEqual(session.calls[-1][1]["max_results"], 5)

    def test_x_api_client_raises_on_http_error(self) -> None:
        client = XApiClient("token", session=FakeSession())  # type: ignore[arg-type]
        with self.assertRaises(XApiError):
            client.user_id_for_username("missing")


if __name__ == "__main__":
    unittest.main()
