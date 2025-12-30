# pip install web3 requests python-dotenv

import time
import os
from decimal import Decimal
from functools import wraps
from datetime import datetime, timezone, timedelta
from web3 import Web3
from dotenv import load_dotenv
from utils.telegram_notify import TelegramNotifier

# =======================
# Retry Decorator
# =======================

def retry(max_attempts=3, delay=2, backoff=2, exceptions=(Exception,)):
    """
    重试装饰器
    :param max_attempts: 最大重试次数
    :param delay: 初始延迟时间(秒)
    :param backoff: 延迟倍数(指数退避)
    :param exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        print(f"❌ {func.__name__} 失败,已重试 {max_attempts} 次: {e}")
                        raise
                    print(f"⚠️  {func.__name__} 失败 (尝试 {attempt}/{max_attempts}), {current_delay}秒后重试: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

# =======================
# Timezone Helper
# =======================

def get_beijing_time() -> str:
    """获取北京时间 (UTC+8)"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

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
# Retry-wrapped functions
# =======================

@retry(max_attempts=3, delay=2, backoff=2)
def fetch_market_data():
    """获取市场数据(带重试)"""
    return moolah.functions.market(MARKET_ID).call()

@retry(max_attempts=3, delay=1, backoff=2)
def send_telegram_message(message: str) -> bool:
    """发送Telegram消息(带重试)"""
    return notifier.send_message(message)

# =======================
# Main loop
# =======================

print("Monitoring: USDF → USD1 borrowable liquidity (Telegram enabled)")
print(f"Threshold: {THRESHOLD} USD1\n")

last_above = False

while True:
    try:
        # ---- fetch on-chain state first (with retry) ----
        m = fetch_market_data()

        supply = to_human(m[0])
        borrow = to_human(m[2])
        available = supply - borrow

        ts = get_beijing_time()
        now = time.time()

        # ---- heartbeat ----
        if now - last_heartbeat_ts >= HEARTBEAT_INTERVAL:
            hb_msg = (
                "🫀 <b>USD1 Monitor Alive</b>\n\n"
                f"• 当前可借：{available:,.2f} USD1\n"
                f"• 时间：{ts}"
            )
            send_telegram_message(hb_msg)
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
            ok = send_telegram_message(msg)
            if ok:
                print(f"[{ts}] Telegram sent: {available:,.2f} USD1")
            else:
                print("Telegram send failed:", notifier.last_error)

        last_above = is_above

    except Exception as exc:
        print(f"[{get_beijing_time()}] ERROR:", exc)

    time.sleep(INTERVAL)
