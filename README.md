# CWFLY-BOT · QQ 机器人

CWFLY 社区的 **QQ 群机器人**，通过 OneBot v11 协议接入（实测环境为 **NapCat**），提供群管理、航班/机场/气象/航路查询、在线状态播报、管制呼叫、活动通知与 AI 问答。

仓库同时包含 **JavaScript 实现（`src/`，生产使用）** 与 **Python 实现（`py/`，功能对齐）** 两套代码。

---

## 一、功能与命令

| 命令 | 功能 | 说明 |
|---|---|---|
| `/help` | 帮助 | 列出全部命令与用法 |
| `/metar <ICAO>` | 气象 | METAR 报文（主站 API / 公开源） |
| `/airport <ICAO>` | 机场资料 | 跑道、频率、基本资料 |
| `/online` | 在线状态 | FSD 当前在线机组/管制列表 |
| `/pilot <呼号>` | 机组查询 | 计划与实时位置 |
| `/controller <席位>` | 管制查询 | 在线管制信息 |
| `/route <起> <降>` | 航路 | 航路规划/推荐（主站或本地算法） |
| `/chart <ICAO>` | 航图 | 机场航图链接/资源 |
| `/event` | 活动 | 近期连飞活动 |
| `/ai <问题>` | AI 问答 | OpenAI 兼容接口（模型可配） |
| `/call`（`callController`） | 呼叫管制 | 在群内提醒在线管制 |
| `groupRequest` | 入群处理 | 入群欢迎与审核 |
| `welcome` | 欢迎语 | 新成员欢迎、规则提示 |

> 命令前缀与权限可在 `src/commands/index.js` 中调整；管理命令仅 `CONTROL_GROUP_ID` / `BOT_ADMIN_QQ` 可用。

---

## 二、技术栈与结构

| 目录 | 语言 | 说明 |
|---|---|---|
| `index.js` | JS | 入口：NapCat WebSocket 接入、事件分发、命令路由 |
| `src/commands/` | JS | 14 个命令实现（ai、airport、callController、chart、controllerQuery、event、groupRequest、help、metar、onlineStatus、pilotQuery、route、welcome） |
| `src/services/` | JS | 服务层：ai、airport、fsd、fsd9（FSD 协议客户端）、route、weather |
| `src/utils/` | JS | 工具（格式化、限频、日志等） |
| `fsd9.js` | JS | FSD 协议客户端（历史版本，保留兼容） |
| `py/` | Python | 与 JS 对齐的 Python 版（`main.py`、`onebot.py`、`commands/`、`services/`） |
| `test/` | JS/Py | `fsd9.test.js`、`test_smoke.py`、`test_atis_e2e.py` |
| `data/` | - | 运行期缓存（机场数据、下载）；不入库 |
| `start-py.ps1` | PS1 | Windows 下启动 Python 版 |

机器人以 **CID 0000（呼号 `CW-BOT`）** 连接 FSD 服务器：用于读取在线列表、发送系统消息、拉取计划/ATIS。

---

## 三、环境变量

复制 `.env.example` 为 `.env`（**不要提交真实值**）：

| 分类 | 变量 | 说明 |
|---|---|---|
| OneBot | `BOT_WS_HOST` / `BOT_WS_PORT` | NapCat 上报的 WebSocket 地址（如 `127.0.0.1:6700`） |
| OneBot | `ONEBOT_ACCESS_TOKEN` | NapCat 的 access token |
| OneBot | `BOT_SELF_ID` | 机器人 QQ 号 |
| 主站 | `CWFLY_API_URL` | 主站 API（`http://127.0.0.1:3000/api`） |
| FSD | `FSD_HOST` / `FSD_PORT` | FSD 服务器地址（`127.0.0.1:6809`） |
| FSD | `FSD_BOT_CALLSIGN` / `FSD_BOT_CID` | 机器人 FSD 身份（`CW-BOT` / `0000`） |
| FSD | `FSD_BOT_PASSWORD` | 机器人 FSD 口令（**必须从环境变量注入**） |
| 数据库 | `DB_HOST/PORT/USER/PASSWORD/NAME` | 直连 MySQL（部分查询/统计） |
| AI | `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` / `AI_MODELS` | OpenAI 兼容接口与模型列表 |
| 群组 | `ALLOWED_GROUP_IDS` / `CONTROL_GROUP_ID` / `NOTIFY_GROUP_ID` | 允许服务的群、管理群、通知群 |
| 群组 | `BOT_ADMIN_QQ` | 机器人管理员 QQ |
| 其他 | `DOWNLOAD_DIR` / `AIRPORT_CACHE_FILE` | 下载目录、机场数据缓存文件 |

---

## 四、快速开始

```bash
cp .env.example .env      # 填写 NapCat 地址/token、主站 API、DB、FSD、AI Key
npm install
npm start                 # 生产启动
npm run dev               # 开发（热重载）
```

前置条件：
1. 已安装并登录 **NapCat**（OneBot v11 实现），WebSocket 端口与 `.env` 一致；
2. FSD 服务器可达，且 CID 0000 的 FSD 口令与 `.env` 中 `FSD_BOT_PASSWORD` 一致；
3. 主站 API 可达（`CWFLY_API_URL`）。

### Python 版

```bash
cd bot 目录
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python main.py            # 或 .\start-py.ps1
```

---

## 五、部署与运维

- 进程：PM2 `cwfly-bot`（`pm2 restart cwfly-bot`）
- 日志：`~/.pm2/logs/cwfly-bot-*.log`；关键行 `[FSD9] Connected to …`、`Auth: Token`
- NapCat 掉线/换号：更新 `BOT_SELF_ID` 与 `ONEBOT_ACCESS_TOKEN`，重启机器人
- 机器人 FSD 认证失败：核对 `FSD_BOT_PASSWORD` 与 FSD 侧 `User.fsdPasswordHash`
- 群内无响应：检查 `ALLOWED_GROUP_IDS` 是否包含该群、NapCat 是否在线

---

## 六、安全说明

- 所有凭据（NapCat token、FSD 口令、AI Key、DB 口令）**只放在 `.env`**，仓库仅提交 `.env.example`
- 代码中的口令默认值一律为空（`process.env.X || ''`），避免把默认口令带进公开仓库
- 管理类命令需同时满足管理群 + 管理员 QQ，避免被任意群成员调用

---

## 七、相关仓库

| 仓库 | 内容 |
|---|---|
| [CWFLY-WEB](https://github.com/yuanshen-123-ui/CWFLY-WEB) | 主站 API（航班/机场/气象数据源） |
| [CWFLY-FSD](https://github.com/yuanshen-123-ui/CWFLY-FSD) | FSD 服务器（机器人以 CID 0000 接入） |
| [CWFLY-ATC](https://github.com/yuanshen-123-ui/CWFLY-ATC) | 管制中心 |
| [CWFLY-DOCS](https://github.com/yuanshen-123-ui/CWFLY-DOCS) | 文档站（含机器人命令说明） |

> 本仓库由 CWFLY 主仓库于 2026-10-30 拆分而来，初始提交为当时快照（不含历史）。
