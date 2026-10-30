# CWFLY-BOT

CWFLY 社区 **QQ 机器人**（OneBot v11 / NapCat 接入），负责群管理、航班查询、机组提醒与 FSD 状态播报。

## 功能
- 群消息管理（关键词、广告检测、入群欢迎）
- 航班/机场/气象查询（对接主站 API 与 FSD）
- FSD 在线状态播报、机组上下线提醒
- AI 对话（OpenAI 兼容接口，可配置模型）
- 管理指令：绑定、禁言、公告推送

## 快速开始
```bash
cp .env.example .env      # 填写 NapCat 地址/token、主站 API、数据库、FSD、AI Key
npm install
npm start                 # 或 npm run dev
```

## 目录
```
src/        JS 机器人主体（服务、命令、事件）
py/         Python 侧工具（fsd9 协议辅助）
test/       本地验证脚本
index.js    入口
```

## 环境变量
见 `.env.example`：`BOT_WS_*`（NapCat）、`ONEBOT_ACCESS_TOKEN`、`CWFLY_API_URL`、`DB_*`、
`FSD_HOST/PORT`、`FSD_BOT_*`（机器人 FSD 账号）、`AI_*`、`*_GROUP_ID`。
---
## 相关仓库

| 仓库 | 内容 |
|---|---|
| [CWFLY-WEB](https://github.com/yuanshen-123-ui/CWFLY-WEB) | 网站前后端（Vue3 + Express/Prisma） |
| [CWFLY-FSD](https://github.com/yuanshen-123-ui/CWFLY-FSD) | FSD 服务器（Python asyncio，FSD 协议） |
| [CWFLY-ATC](https://github.com/yuanshen-123-ui/CWFLY-ATC) | 管制中心（ATC 席位/雷达/排班） |
| [CWFLY-BOT](https://github.com/yuanshen-123-ui/CWFLY-BOT) | QQ 机器人（OneBot / NapCat） |
| [CWFLY-DOCS](https://github.com/yuanshen-123-ui/CWFLY-DOCS) | 文档站（VitePress） |
| CWFLY-DEPLOY（私有） | 生产部署资产：Nginx 配置、运维脚本、SQL 迁移（私有仓库，不对外公开） | Nginx · Bash · MySQL |

> 本仓库由 CWFLY 主仓库于 2026-10-30 拆分而来，初始提交为当时快照（不含历史）。