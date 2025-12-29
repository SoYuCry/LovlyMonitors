# pip install web3 requests python-dotenv

import time
import os
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
from utils.telegram_notify import TelegramNotifier

# =======================
# Env / Telegram
# =======================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_GROUP")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP in .env")

notifier = TelegramNotifier(BOT_TOKEN, CHAT_ID)

# =======================
# Config
# =======================

HEARTBEAT_INTERVAL = 60 * 60   # 1 hour
last_heartbeat_ts = 0

BSC_RPC = "https://bsc-dataseed.binance.org/"
MOOLAH  = Web3.to_checksum_address(
    "0x8F73b65B4caAf64FBA2aF91cC5D4a2A1318E5D8C"
)

USD1 = Web3.to_checksum_address(
    "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
)
USDF = Web3.to_checksum_address(
    "0x5A110fC00474038f6c02E89C707D638602EA44B5"
)

MARKET_ID = bytes.fromhex(
    "b060b526bd2fc99150cff9d6f7e7fab88d5d67e35cf262215f986d62a2fba99e"
)

THRESHOLD = Decimal("10000")
INTERVAL  = 60

# =======================
# Web3 init
# =======================

w3 = Web3(Web3.HTTPProvider(BSC_RPC))
assert w3.is_connected(), "RPC connection failed"

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

ERC20_ABI = [
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"type": "uint8"}],
    }
]

moolah = w3.eth.contract(address=MOOLAH, abi=MOOLAH_ABI)

usd1_decimals = (
    w3.eth.contract(address=USD1, abi=ERC20_ABI)
    .functions.decimals()
    .call()
)

def to_human(x: int) -> Decimal:
    return Decimal(x) / (Decimal(10) ** usd1_decimals)

# =======================
# Main loop
# =======================

print("Monitoring: USDF → USD1 borrowable liquidity (Telegram enabled)")
print(f"Threshold: {THRESHOLD} USD1\n")

last_above = False

while True:
    try:
        # ---- fetch on-chain state first ----
        m = moolah.functions.market(MARKET_ID).call()

        supply = to_human(m[0])
        borrow = to_human(m[2])
        available = supply - borrow

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        now = time.time()

        # ---- heartbeat ----
        if now - last_heartbeat_ts >= HEARTBEAT_INTERVAL:
            hb_msg = (
                "🫀 <b>USD1 Monitor Alive</b>\n\n"
                f"• 当前可借：{available:,.2f} USD1\n"
                f"• 时间：{ts}"
            )
            notifier.send_message(hb_msg)
            last_heartbeat_ts = now

        # ---- threshold trigger ----
        is_above = available >= THRESHOLD

        if is_above and not last_above:
            msg = (
                "✅ <b>USD1 可借额度触发</b>\n\n"
                f"• 抵押物：USDF\n"
                f"• 可借 USD1：<b>{available:,.2f}</b>\n"
                f"• 阈值：{THRESHOLD:,.0f}\n"
                f"• 时间：{ts}"
            )
            ok = notifier.send_message(msg)
            if ok:
                print(f"[{ts}] Telegram sent: {available:,.2f} USD1")
            else:
                print("Telegram send failed:", notifier.last_error)

        last_above = is_above

    except Exception as exc:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR:", exc)

    time.sleep(INTERVAL)
