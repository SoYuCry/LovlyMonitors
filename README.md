# 🔍 LovlyMonitors

区块链和 DeFi 协议自动化监控工具集合。支持实时监控、Telegram 通知和自动重试。

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `.env.example` 为 `.env` 并填入配置:
```env
TELEGRAM_BOT_TOKEN=你的机器人Token
TELEGRAM_GROUP=你的群组ChatID
```

获取 Chat ID: 访问 `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` 找到 `chat.id`

### 3. 运行
```bash
python Lista_USD1.py
```

## 📊 监控列表

### Lista USD1 借贷监控 (`Lista_USD1.py`)
- **功能**: 监控 Lista Protocol 上 USDF → USD1 的可借额度
- **网络**: BSC
- **触发**: 可借额度 ≥ 10,000 USD1 时发送通知
- **心跳**: 每小时发送存活确认

## ⚙️ 配置

### 环境变量
| 变量 | 说明 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram 机器人 Token |
| `TELEGRAM_GROUP` | Telegram 群组 Chat ID |

### 内置功能
- 🔄 自动重试 (RPC 和 Telegram,最多 3 次,指数退避)
- 🕐 北京时间 (UTC+8)
- 💓 心跳监控

## 📖 后台运行

**Linux/Mac:**
```bash
nohup python Lista_USD1.py > lista_usd1.log 2>&1 &
```

**Windows:**
```powershell
Start-Process python -ArgumentList "Lista_USD1.py" -WindowStyle Hidden
```

## 📝 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

**注意**: 请妥善保管 `.env` 文件,不要提交到 Git 仓库。
