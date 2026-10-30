# CWFLY 飞控机器人（Python 版）

将 `d:\CWFLY\bot`（Node.js 版 OneBot 机器人）整体移植为 Python 实现，
功能与 Node 版一致：

- OneBot 反向 WebSocket 服务器（默认 `127.0.0.1:6700`，NapCat 连接）
- FSD9 协议直连（`$CH`/`$SA` 安全认证、客户端列表、实时位置、`$AX` ATIS）
- 管制上线/下线通知（含 ATIS / ATC INFO，最多等 10 秒）
- 命令：`/在线状态` `/机组查询` `/管制查询` `/机场查询` `/呼叫管制`
  `/呼叫2325` `/metar` `/taf` `/航路` `/event` `/chat` `/帮助`
- 入群欢迎（notice / group_increase）
- 用户/全局冷却限流

## 结构

```
py/
├── main.py          # 入口：WS Server + 管制上下线通知
├── config.py        # .env 配置加载
├── onebot.py        # OneBot 11 消息发送
├── fsd9.py          # FSD9 协议直连客户端（asyncio）
├── validator.py     # ICAO/呼号校验
├── rate_limit.py    # 内存限流
├── services/        # ai / airport / fsd / route / weather / http
└── commands/        # 命令分发器 + 13 个命令
```

## 运行

```bash
cd d:\CWFLY\bot
python -m pip install -r py/requirements.txt
python -m py.main
```

读取配置来自 `d:\CWFLY\bot\.env`（与 Node 版共用，含
`BOT_WS_HOST/BOT_WS_PORT/ONEBOT_ACCESS_TOKEN/FSD_HOST/FSD_PORT/...`）。

## 部署（服务器 /opt/cwfly/bot）

```bash
scp -r py/ root@server:/opt/cwfly/bot/py/
# pm2 启动
pm2 start "cd /opt/cwfly/bot && .venv/bin/python -m py.main" --name cwfly-bot-py
```

> 注：与 Node 版为同一份 `.env`；反向 WS 由 NapCat 主动连接
> `ws://127.0.0.1:6700`（token 见 `.env` 的 `ONEBOT_ACCESS_TOKEN`，已轮换为强随机值）。

## 与 Node 版的差异

- `fsd9.py` 用 asyncio 流替代 `net`/`EventEmitter`
- 事件回调：`client.on('controller:add', cb)` 等（`ready` /
  `controller:add` / `controller:remove` / `controller:atis` /
  `pilot:add` / `pilot:remove` / `client:remove`）
- HTTP 走 `requests` + `asyncio.to_thread`（`services/http.py`）
- 命令处理函数为 `async`，发送用 `await onebot.reply(...)`

## ⚠️ 关键：FSD9 `$SA` 认证（已修复）

`$SA` 的 HMAC key 必须是 challenge 十六进制**字符串本身**（`challenge.encode()`），
**不能** `bytes.fromhex(challenge)` —— 与服务器 fsd-py
（`certificate.py compute_auth_response`）算法不一致会导致认证永远失败、
收不到 `$AX` ATIS，从而没有 ATC-INFO。已在 `py/fsd9.py` 修复。

## ⚠️ 关键：要能拿到 ATC-INFO，bot 必须连上可用的 FSD 服务器

`.env` 中 `FSD_HOST=fsd.cwflysim.cn`、`FSD_PORT=6809` 指向真实服务器。
要真正验证：

- **FSD_BOT_CALLSIGN 必须唯一**：服务器上生产 Node bot 占用 `CW-BOT`，
  本地 Python bot 用 `CW-BOT` 会收到 `$ER ... Callsign in use`、被拒注册、
  无 `$PO` 回应 → 30 秒 ping 超时反复断线。已设为 `CW-BOT-PY`。
- CID/密码需在服务器 User 表中存在（`FSD_BOT_CID=0000`；`FSD_BOT_PASSWORD` 取 `.env` 值，须与 fsd-py `cert.txt` 中 CID 0000 一致，已轮换）。
- ATC-INFO 只会在**管制员发布 ATIS（$AX）**且 bot 就绪后新上线的管制推送时显示；
  启动时已在线且无 ATIS 的管制（如 ZGZU_CTR）不会在通知里带 ATC INFO（与 Node 版一致）。

## 验证脚本

- `python -m py.test_smoke` — FSD 报文解析 + 命令分发（无需服务器）
- `python -m py.test_atis_e2e` — 模拟 FSD 服务器 → 认证 → `$AX` ATIS → ATC INFO 卡片（端到端）
