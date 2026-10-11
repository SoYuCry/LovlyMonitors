# 更新日志

## [未发布]

- 新增 X/Twitter 用户推文监控，支持本地 JSONL 保存、ID 去重和完整分页读取。
- 分页失败时不推进本地游标，避免跳过尚未保存的推文。
- 支持从 `.env` 读取默认用户名 `X_USERNAME`。
- 将 Lista 监控、Telegram 通知和公共工具拆分为模块，保留旧入口。
- 修复中文文档中的问号乱码。

## [1.1.0] - 2025-12-30

### ✨ 新增
- 北京时间支持 (UTC+8)
- 自动重试机制 (RPC 和 Telegram,最多 3 次,指数退避)
- 项目文档 (README.md, CHANGELOG.md)

### 🔧 改进
- 提取 `fetch_market_data()` 和 `send_telegram_message()` 函数
- 使用 `@retry` 装饰器实现重试逻辑
- 优化错误日志格式

---

## [1.0.0] - 2025-12-30

### ✨ 新增
- Lista USD1 借贷监控 (`Lista_USD1.py`)
  - 监控 USDF → USD1 可借额度
  - Telegram 通知 (阈值触发 + 心跳)
  - BSC 网络支持

### 📦 依赖
- `web3`, `requests`, `python-dotenv`

---

**标签说明**: ✨ 新增 | 🔧 改进 | 🐛 修复 | 📝 文档
