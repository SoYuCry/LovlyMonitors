# LovlyMonitors

监控 Lista Protocol 的 USD1 可借额度，以及指定 X/Twitter 用户的新推文。

## 安装与配置

```bash
pip install -r requirements.txt
```

复制 `.env.example` 为项目根目录的 `.env`，填入所需配置：

```env
TELEGRAM_BOT_TOKEN=你的机器人Token
TELEGRAM_GROUP=你的ChatID
X_BEARER_TOKEN=你的X_API_Bearer_Token
```

Lista 监控需要 Telegram 配置；X 监控需要 X Bearer Token。真实 `.env` 已被 Git 忽略，不要提交密钥。

## Lista USD1 监控

```bash
python Lista_USD1.py
```

监控 BSC 上 USDF 抵押借出 USD1 的可用额度，达到默认 10,000 USD1 阈值时发送 Telegram 通知，并定期发送心跳。

## X/Twitter 监控

```bash
python X_Monitor.py username
```

用户名也可写为 `@username`，或在 `.env` 中设置 `X_USERNAME` 后不传命令行参数。从项目根目录启动。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `X_BEARER_TOKEN` | 必填 | X API v2 Bearer Token |
| `X_USERNAME` | 无 | 未传命令行用户名时使用 |
| `X_OUTPUT_DIR` | `data/x_tweets` | JSONL 保存目录 |
| `X_POLL_INTERVAL` | `60` | 轮询间隔，单位秒 |
| `X_MAX_RESULTS` | `5` | 每页条数，限制在 5–100 |

推文保存至 `<输出目录>/<用户名>.jsonl`，启动时读取已有 ID 去重。每轮按 `since_id` 获取新推文并读取全部分页，再统一保存；任一分页失败时不推进本地游标，下轮重试。首次运行也会读取接口提供的全部分页，可能产生多次 API 请求；历史范围和访问权限受 X API 限制。

X 监控目前只保存到本地，不发送 Telegram 通知。

## 代码与测试

`lovlymonitors/monitors/` 包含两个监控实现，`lovlymonitors/common.py` 提供时间与重试工具，`lovlymonitors/notifications/telegram.py` 提供 Telegram 通知。保留 `Lista_USD1.py` 与 `utils.telegram_notify` 兼容入口。

```bash
python -m unittest discover -s tests
```

测试使用模拟 API，不需要真实密钥。更新记录见 [CHANGELOG.md](CHANGELOG.md)。
