"""Regression tests for shared monitor helpers."""

from __future__ import annotations

import re
import unittest
from decimal import Decimal
from unittest.mock import patch

from lovlymonitors.common import get_beijing_time, retry
from lovlymonitors.monitors.lista_usd1 import to_human_amount


class CommonHelperTests(unittest.TestCase):
    def test_to_human_amount_uses_token_decimals(self) -> None:
        self.assertEqual(to_human_amount(123456789, 6), Decimal("123.456789"))
        self.assertEqual(to_human_amount(10**18, 18), Decimal("1"))

    def test_retry_retries_until_success(self) -> None:
        calls = {"count": 0}

        @retry(max_attempts=3, delay=0, exceptions=(ValueError,))
        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 2:
                raise ValueError("temporary")
            return "ok"

        with patch("lovlymonitors.common.time.sleep") as sleep:
            self.assertEqual(flaky(), "ok")

        self.assertEqual(calls["count"], 2)
        sleep.assert_called_once_with(0)

    def test_retry_raises_after_max_attempts(self) -> None:
        @retry(max_attempts=2, delay=0, exceptions=(ValueError,))
        def always_fail() -> None:
            raise ValueError("broken")

        with patch("lovlymonitors.common.time.sleep"):
            with self.assertRaises(ValueError):
                always_fail()

    def test_get_beijing_time_format(self) -> None:
        self.assertRegex(get_beijing_time(), re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"))


if __name__ == "__main__":
    unittest.main()
