"""Minimal X/Twitter username monitor that saves new posts locally."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
DEFAULT_OUTPUT_DIR = Path("data/x_tweets")
X_API_BASE_URL = "https://api.x.com/2"


class XApiError(RuntimeError):
    """Raised when X API returns an unusable response."""


@dataclass(frozen=True)
class XMonitorConfig:
    username: str
    bearer_token: str
    output_dir: Path = DEFAULT_OUTPUT_DIR
    interval_seconds: int = 60
    max_results: int = 5


def normalize_username(username: str) -> str:
    """Return a valid X username without a leading @."""
    normalized = username.strip().lstrip("@")
    if not USERNAME_RE.fullmatch(normalized):
        raise ValueError("username must be 1-15 chars: letters, numbers, underscore")
    return normalized


def tweet_sort_key(tweet: dict[str, Any]) -> int:
    tweet_id = str(tweet.get("id", "0"))
    return int(tweet_id) if tweet_id.isdigit() else 0


class TweetJsonlStore:
    """Append-only JSONL storage with ID-based dedupe."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seen_ids = self._load_seen_ids()

    def _load_seen_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        seen: set[str] = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            tweet_id = item.get("id")
            if tweet_id is not None:
                seen.add(str(tweet_id))
        return seen

    def newest_id(self) -> str | None:
        numeric_ids = [int(tweet_id) for tweet_id in self.seen_ids if tweet_id.isdigit()]
        return str(max(numeric_ids)) if numeric_ids else None

    def append_new(self, tweets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        new_tweets = [tweet for tweet in tweets if str(tweet.get("id", "")) not in self.seen_ids]
        new_tweets.sort(key=tweet_sort_key)
        if not new_tweets:
            return []
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            for tweet in new_tweets:
                fh.write(json.dumps(tweet, ensure_ascii=False, sort_keys=True) + "\n")
                self.seen_ids.add(str(tweet["id"]))
        return new_tweets


class XApiClient:
    """Tiny X API v2 client for username lookup and user posts."""

    def __init__(self, bearer_token: str, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=20)
        if response.status_code >= 400:
            raise XApiError(f"X API HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        if "errors" in data and not data.get("data"):
            raise XApiError(f"X API error: {data['errors']}")
        return data

    def user_id_for_username(self, username: str) -> str:
        data = self._get(f"{X_API_BASE_URL}/users/by/username/{username}")
        try:
            return str(data["data"]["id"])
        except KeyError as exc:
            raise XApiError(f"No user data returned for @{username}") from exc

    def latest_tweets(
        self,
        user_id: str,
        since_id: str | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "max_results": max(5, min(max_results, 100)),
            "tweet.fields": "created_at,author_id,conversation_id,referenced_tweets,lang,public_metrics",
        }
        if since_id:
            params["since_id"] = since_id
        tweets: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        while True:
            data = self._get(f"{X_API_BASE_URL}/users/{user_id}/tweets", params=dict(params))
            tweets.extend(data.get("data") or [])
            token = (data.get("meta") or {}).get("next_token")
            if not token:
                return tweets
            if token in seen_tokens:
                raise XApiError("Repeated pagination token; refusing to advance stored cursor")
            seen_tokens.add(token)
            params["pagination_token"] = token


class XTweetsMonitor:
    """Poll one username and append newly seen posts to disk."""

    def __init__(self, config: XMonitorConfig) -> None:
        self.config = config
        self.username = normalize_username(config.username)
        self.client = XApiClient(config.bearer_token)
        self.store = TweetJsonlStore(config.output_dir / f"{self.username}.jsonl")
        self.user_id: str | None = None

    def tick(self) -> list[dict[str, Any]]:
        if self.user_id is None:
            self.user_id = self.client.user_id_for_username(self.username)
        tweets = self.client.latest_tweets(
            self.user_id,
            since_id=self.store.newest_id(),
            max_results=self.config.max_results,
        )
        return self.store.append_new(tweets)

    def run_forever(self) -> None:
        print(f"Monitoring X posts for @{self.username}")
        print(f"Saving to: {self.store.path}\n")
        while True:
            try:
                saved = self.tick()
                if saved:
                    print(f"saved {len(saved)} new tweet(s); newest id={saved[-1]['id']}")
            except Exception as exc:
                print("ERROR:", exc)
            time.sleep(self.config.interval_seconds)


def config_from_env(username: str) -> XMonitorConfig:
    load_dotenv()
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        raise RuntimeError("Missing X_BEARER_TOKEN in .env")
    output_dir = Path(os.getenv("X_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    interval = int(os.getenv("X_POLL_INTERVAL", "60"))
    max_results = int(os.getenv("X_MAX_RESULTS", "5"))
    return XMonitorConfig(
        username=normalize_username(username),
        bearer_token=bearer_token.strip(),
        output_dir=output_dir,
        interval_seconds=interval,
        max_results=max_results,
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Save latest X/Twitter posts for a username to local JSONL.")
    parser.add_argument("username", nargs="?", default=os.getenv("X_USERNAME"), help="X username, with or without @")
    args = parser.parse_args()
    if not args.username:
        parser.error("username is required, e.g. python X_Monitor.py elonmusk")
    XTweetsMonitor(config_from_env(args.username)).run_forever()


if __name__ == "__main__":
    main()
