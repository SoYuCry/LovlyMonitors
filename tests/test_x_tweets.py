"""Regression tests for the minimal X/Twitter monitor."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from lovlymonitors.monitors.x_tweets import (
    TweetJsonlStore,
    XApiClient,
    XApiError,
    normalize_username,
    XMonitorConfig,
    XTweetsMonitor,
    main,
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
    def test_main_reads_dotenv_username_and_cli_override(self) -> None:
        for argv, expected in [(["X_Monitor.py"], "jack"), (["X_Monitor.py", "other"], "other")]:
            with self.subTest(argv=argv), tempfile.TemporaryDirectory() as tmp:
                env_file = Path(tmp) / ".env"
                env_file.write_text("X_USERNAME=jack\nX_BEARER_TOKEN=test-token\n", encoding="utf-8")
                from dotenv import load_dotenv
                with patch.dict(os.environ, {}, clear=True), patch("sys.argv", argv), patch(
                    "lovlymonitors.monitors.x_tweets.load_dotenv",
                    side_effect=lambda: load_dotenv(env_file),
                ), patch("lovlymonitors.monitors.x_tweets.XTweetsMonitor") as monitor:
                    main()
                    self.assertEqual(monitor.call_args.args[0].username, expected)
                    monitor.return_value.run_forever.assert_called_once()

    def test_pagination_keeps_since_id_and_reads_all_pages(self) -> None:
        client = XApiClient("token", session=FakeSession())
        with patch.object(client, "_get", side_effect=[
            {"data": [{"id": "103"}], "meta": {"next_token": "page2"}},
            {"data": [{"id": "101"}, {"id": "102"}]},
        ]) as get:
            self.assertEqual(len(client.latest_tweets("12", since_id="100")), 3)
            self.assertNotIn("pagination_token", get.call_args_list[0].kwargs["params"])
            self.assertEqual(get.call_args_list[1].kwargs["params"]["pagination_token"], "page2")
            self.assertEqual(get.call_args_list[1].kwargs["params"]["since_id"], "100")

    def test_failed_page_does_not_advance_store_then_retry_saves_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            monitor = XTweetsMonitor(XMonitorConfig("jack", "token", Path(tmp)))
            monitor.user_id = "12"
            monitor.store.append_new([{"id": "100"}])
            first = {"data": [{"id": "103"}], "meta": {"next_token": "page2"}}
            with patch.object(monitor.client, "_get", side_effect=[first, XApiError("failed")]):
                with self.assertRaises(XApiError):
                    monitor.tick()
            self.assertEqual(TweetJsonlStore(monitor.store.path).newest_id(), "100")
            with patch.object(monitor.client, "_get", side_effect=[first, {"data": [{"id": "101"}, {"id": "102"}]}]):
                self.assertEqual([t["id"] for t in monitor.tick()], ["101", "102", "103"])

    def test_repeated_pagination_token_fails(self) -> None:
        client = XApiClient("token", session=FakeSession())
        with patch.object(client, "_get", return_value={"meta": {"next_token": "same"}}) as get:
            with self.assertRaises(XApiError):
                client.latest_tweets("12")
            self.assertEqual(get.call_count, 2)

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
