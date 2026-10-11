"""Lista Protocol USDF -> USD1 borrowable liquidity monitor."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from lovlymonitors.common import get_beijing_time, retry
from lovlymonitors.notifications.telegram import TelegramNotifier

MOOLAH_ABI = [
    {
        "name": "market",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"type": "bytes32"}],
        "outputs": [
            {"type": "uint128"},
            {"type": "uint128"},
            {"type": "uint128"},
            {"type": "uint128"},
            {"type": "uint128"},
            {"type": "uint128"},
        ],
    },
]

ERC20_DECIMALS_ABI = [
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"type": "uint8"}],
    }
]


def to_human_amount(value: int, decimals: int) -> Decimal:
    """Convert a token integer amount into a human decimal amount."""
    return Decimal(value) / (Decimal(10) ** decimals)


@dataclass(frozen=True)
class ListaUSD1Config:
    bsc_rpc: str = "https://bsc-dataseed.binance.org/"
    moolah_address: str = "0x8F73b65B4caAf64FBA2aF91cC5D4a2A1318E5D8C"
    usd1_address: str = "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
    market_id_hex: str = "b060b526bd2fc99150cff9d6f7e7fab88d5d67e35cf262215f986d62a2fba99e"
    threshold: Decimal = Decimal("10000")
    interval_seconds: int = 60
    heartbeat_interval_seconds: int = 60 * 60


class ListaUSD1Monitor:
    """Stateful monitor loop for Lista USD1 liquidity alerts."""

    def __init__(self, config: ListaUSD1Config, notifier: TelegramNotifier) -> None:
        self.config = config
        self.notifier = notifier
        self.last_above = False
        self.last_heartbeat_ts = 0.0

        from web3 import Web3

        self.web3 = Web3(Web3.HTTPProvider(config.bsc_rpc))
        if not self.web3.is_connected():
            raise RuntimeError("RPC connection failed")

        self.moolah = self.web3.eth.contract(
            address=Web3.to_checksum_address(config.moolah_address),
            abi=MOOLAH_ABI,
        )
        self.usd1_decimals = (
            self.web3.eth.contract(
                address=Web3.to_checksum_address(config.usd1_address),
                abi=ERC20_DECIMALS_ABI,
            )
            .functions.decimals()
            .call()
        )
        self.market_id = bytes.fromhex(config.market_id_hex)

    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_market_data(self) -> Any:
        """Fetch market data with retry."""
        return self.moolah.functions.market(self.market_id).call()

    @retry(max_attempts=3, delay=1, backoff=2)
    def send_telegram_message(self, message: str) -> bool:
        """Send Telegram message with retry."""
        return self.notifier.send_message(message)

    def to_human(self, value: int) -> Decimal:
        return to_human_amount(value, self.usd1_decimals)

    def tick(self) -> None:
        """Run one monitor iteration."""
        market = self.fetch_market_data()
        supply = self.to_human(market[0])
        borrow = self.to_human(market[2])
        available = supply - borrow

        timestamp = get_beijing_time()
        now = time.time()

        if now - self.last_heartbeat_ts >= self.config.heartbeat_interval_seconds:
            heartbeat = (
                "🫀 <b>USD1 Monitor Alive</b>\n\n"
                f"• 当前可借：{available:,.2f} USD1\n"
                f"• 时间：{timestamp}"
            )
            self.send_telegram_message(heartbeat)
            self.last_heartbeat_ts = now

        is_above = available >= self.config.threshold
        if is_above and not self.last_above:
            message = (
                "✅ <b>USD1 可借额度触发</b>\n\n"
                "• 抵押物：USDF\n"
                f"• 可借 USD1：<b>{available:,.2f}</b>\n"
                f"• 阈值：{self.config.threshold:,.0f}\n"
                f"• 时间：{timestamp}"
            )
            ok = self.send_telegram_message(message)
            if ok:
                print(f"[{timestamp}] Telegram sent: {available:,.2f} USD1")
            else:
                print("Telegram send failed:", self.notifier.last_error)

        self.last_above = is_above

    def run_forever(self) -> None:
        print("Monitoring: USDF → USD1 borrowable liquidity (Telegram enabled)")
        print(f"Threshold: {self.config.threshold} USD1\n")
        while True:
            try:
                self.tick()
            except Exception as exc:
                print(f"[{get_beijing_time()}] ERROR:", exc)
            time.sleep(self.config.interval_seconds)


def build_notifier_from_env(project_root: Path) -> TelegramNotifier:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_GROUP")
    if not bot_token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP in .env")
    return TelegramNotifier(bot_token, chat_id)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    notifier = build_notifier_from_env(project_root)
    ListaUSD1Monitor(ListaUSD1Config(), notifier).run_forever()


if __name__ == "__main__":
    main()
