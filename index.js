/**
 * CWFLY 飞控机器人 - OneBot 反向 WebSocket 入口
 *
 * 职责：
 * 1. 启动 WebSocket Server
 * 2. 验证 NapCat Token
 * 3. 接收 OneBot 事件
 * 4. 交给命令路由
 */

import 'dotenv/config'
import { isNotifySkipped } from './utils/notifyFilter.js'
import { WebSocketServer } from 'ws'
import { dispatch } from './commands/index.js'
import { getFSD9Client } from './services/fsd9.js'
import { sendGroupMessage } from './utils/onebot.js'

const WS_HOST = process.env.BOT_WS_HOST || '127.0.0.1'
const WS_PORT = Number(process.env.BOT_WS_PORT || 6700)
const ACCESS_TOKEN = process.env.ONEBOT_ACCESS_TOKEN || ''

const wss = new WebSocketServer({
  host: WS_HOST,
  port: WS_PORT
})

wss.on('connection', (ws, request) => {
  // Token 验证
  const token = request.headers.authorization
    ?.replace(/^Bearer\s+/i, '')

  if (ACCESS_TOKEN && token !== ACCESS_TOKEN) {
    console.error(`[OneBot] Token rejected from ${request.socket.remoteAddress}`)
    ws.close(1008, 'Unauthorized')
    return
  }

  console.log(`[OneBot] Connection from ${request.socket.remoteAddress}`)

  // 首个连接稳定后启用管制上下线推送（跳过启动时的 FSD 在线快照）
  if (!botReady) {
    setTimeout(() => {
      botReady = true
      console.log('[Bot] Ready, 管制上下线通知已启用')
    }, 2000)
  }

  ws.on('message', async (raw) => {
    try {
      const event = JSON.parse(raw.toString())
      await dispatch(ws, event)
    } catch (error) {
      console.error('[OneBot] Parse error:', error.message)
    }
  })

  ws.on('close', () => {
    console.log('[OneBot] Connection closed')
  })

  ws.on('error', (err) => {
    console.error('[OneBot] WebSocket error:', err.message)
  })
})

// 管制等级映射（FSD rating -> 等级字符串）
const RATING_MAP = {
  1: 'OBS', 2: 'S1', 3: 'S2', 4: 'S3', 5: 'C1', 6: 'C2', 7: 'C3',
  8: 'I1', 9: 'I2', 10: 'I3', 11: 'SUP', 12: 'ADM'
}

function ratingLabel(rating) {
  return RATING_MAP[rating] || `R${rating}`
}

// 频率整数(如 125750) -> "125.750 MHz"
function formatFrequency(freq) {
  if (!freq) return '未知'
  return `${(freq / 1000).toFixed(3)} MHz`
}

// 秒时间戳 -> UTC 时间字符串
function formatUtc(sec) {
  if (!sec) return ''
  return new Date(sec * 1000).toISOString().replace('T', ' ').replace('Z', ' UTC')
}

// 秒时间戳 -> "UTC HH:MM / CST HH:MM"（CST = UTC+8）
function formatTimeShort(sec) {
  const d = new Date(sec * 1000)
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mm = String(d.getUTCMinutes()).padStart(2, '0')
  const cst = new Date(sec * 1000 + 8 * 3600 * 1000)
  const chh = String(cst.getUTCHours()).padStart(2, '0')
  const cmm = String(cst.getUTCMinutes()).padStart(2, '0')
  return `UTC ${hh}:${mm} / CST ${chh}:${cmm}`
}

// 服务时长（秒）-> "X 时 Y 分"
function formatDuration(startSec) {
  const totalMin = Math.max(0, Math.floor((Date.now() / 1000 - startSec) / 60))
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return `${h} 时 ${m} 分`
}

function buildControllerCard(controller, type) {
  const callsign = controller?.callsign || ''
  const realname = controller?.realname || ''
  const cid = controller?.cid || ''
  const level = ratingLabel(controller?.rating)
  const freq = formatFrequency(controller?.frequency)
  const startSec = controller?.starttime || Math.floor(Date.now() / 1000)

  if (type === 'offline') {
    return [
      `[${callsign} 离线通知]`,
      `管制员: ${cid} ${callsign} ${realname}`.trim(),
      `下线时间: ${formatTimeShort(startSec)}`,
      `提供服务时长: ${formatDuration(startSec)}`,
      `请范围内机组守听 ${freq}`,
      '祝飞行愉快~'
    ].join('\n')
  }

  // ATC INFO：管制员发布的 ATIS 航站情报（有则显示，无则不显示）
  const atis = (controller?.atis || '').trim()
  const atcInfo = atis ? atis.split('\n').map(l => l.trim()).filter(Boolean) : []

  const lines = [
    `[${callsign} 上线通知]`,
    `管制员：CID ${cid} ${realname}`,
    `管制等级：${level}`,
    `联系频率：${freq}`,
    `上线时间：${formatUtc(startSec)} / ${new Date(startSec * 1000).toLocaleTimeString('zh-CN', { hour12: false })} 本地`
  ]
  if (atcInfo.length) {
    lines.push('')
    lines.push('ATC INFO')
    lines.push(...atcInfo)
  }
  lines.push('')
  lines.push('请范围内机组自主联系')
  lines.push('祝联飞顺利~')
  return lines.join('\n')
}

// 是否已就绪（等待 OneBot 连接建立后再推送，避免启动时快照刷屏 + 空连接发送）
let botReady = false

// 等待 ATIS 的控制器（上线通知延迟，最多等 10 秒让 ATIS 到达）
const pendingOnline = new Map() // callsign -> { controller, timer }

function announceControllerOnline(controller) {
  if (isNotifySkipped(controller)) {
    console.log(`[Bot] 免播报名单，跳过上线通知 ${controller.callsign} (cid=${controller.cid})`)
    return
  }
  const groupId = process.env.NOTIFY_GROUP_ID || process.env.CONTROL_GROUP_ID
  if (!botReady || !groupId || !controller?.callsign) return
  const key = controller.callsign.toUpperCase()

  // 已带 ATIS：直接推送
  if (controller.atis) {
    pushOnline(controller)
    return
  }

  // 等待 ATIS：若已有待发，先取消旧定时器
  if (pendingOnline.has(key)) {
    clearTimeout(pendingOnline.get(key).timer)
  }
  // 最多等 10 秒；即使没有 ATIS 也推送（ATCPOS 频率同样需要等待）
  const timer = setTimeout(() => {
    pendingOnline.delete(key)
    pushOnline(controller)
  }, 10000)
  pendingOnline.set(key, { controller, timer })
}

function pushOnline(controller) {
  const groupId = process.env.NOTIFY_GROUP_ID || process.env.CONTROL_GROUP_ID
  if (!groupId || !controller?.callsign) return
  const text = buildControllerCard(controller, 'online')
  let sent = 0
  for (const ws of wss.clients) {
    try {
      sendGroupMessage(ws, groupId, text)
      sent++
    } catch {}
  }
  console.log(`[Bot] 上线通知已推送 ${controller.callsign} → group=${groupId} clients=${sent}`)
}

// 收到 ATIS 时，若该管制员正在等待上线通知，立即推送
function onControllerAtis({ callsign }) {
  const key = (callsign || '').toUpperCase()
  const pending = pendingOnline.get(key)
  if (!pending) return
  clearTimeout(pending.timer)
  pendingOnline.delete(key)
  pushOnline(pending.controller)
}

function announceControllerOffline(controller) {
  if (isNotifySkipped(controller)) {
    console.log(`[Bot] 免播报名单，跳过下线通知 ${controller.callsign} (cid=${controller.cid})`)
    return
  }
  const groupId = process.env.NOTIFY_GROUP_ID || process.env.CONTROL_GROUP_ID
  if (!botReady || !groupId || !controller?.callsign) return
  const key = controller.callsign.toUpperCase()
  // 取消该管制员待发的上线通知
  if (pendingOnline.has(key)) {
    clearTimeout(pendingOnline.get(key).timer)
    pendingOnline.delete(key)
  }
  const text = buildControllerCard(controller, 'offline')
  let sent = 0
  for (const ws of wss.clients) {
    try {
      sendGroupMessage(ws, groupId, text)
      sent++
    } catch {}
  }
  console.log(`[Bot] 下线通知已推送 ${controller.callsign} → group=${groupId} clients=${sent}`)
}

wss.on('listening', () => {
  // 预连接 FSD9，确保 /在线状态、/机组查询 等立即可用
  const client = getFSD9Client()
  client.on('controller:add', announceControllerOnline)
  client.on('controller:remove', announceControllerOffline)
  client.on('controller:atis', onControllerAtis)
  console.log(`
  ╔═══════════════════════════════════╗
  ║     CWFLY 飞控机器人 v1.0         ║
  ╠═══════════════════════════════════╣
  ║  WS Server: ${WS_HOST}:${WS_PORT}          ║
  ║  Auth: ${ACCESS_TOKEN ? 'Token' : 'No Token'}               ║
  ║  Groups: ${process.env.ALLOWED_GROUP_IDS || '(none)'}  ║
  ╚═══════════════════════════════════╝
  `)
})

wss.on('error', (err) => {
  console.error('[OneBot] Server error:', err.message)
  process.exit(1)
})

// 优雅退出
process.on('SIGINT', () => {
  console.log('\n[OneBot] Shutting down...')
  wss.close(() => process.exit(0))
})

process.on('SIGTERM', () => {
  wss.close(() => process.exit(0))
})
