/**
 * 命令路由
 * 严格前缀匹配，长命令在前避免误匹配
 */

import { handleOnlineStatus } from './onlineStatus.js'
import { handlePilotQuery } from './pilotQuery.js'
import { handleControllerQuery } from './controllerQuery.js'
import { handleMetar, handleTaf } from './metar.js'
import { handleRoute } from './route.js'
import { handleAirport } from './airport.js'
import { handleNormalAi } from './ai.js'
import { handleCallController, handleCall2325 } from './callController.js'
import { handleHelp } from './help.js'
import { handleEvent } from './event.js'
import { handleGroupIncrease } from './welcome.js'
import { handleGroupRequest } from './groupRequest.js'


import { isAllowedGroup } from '../utils/validator.js'
import { checkUserCooldown } from '../utils/rateLimit.js'

/** 命令定义：主命令 + 中英文别名 */
const routes = [
  { cmd: '/在线状态', aliases: ['/online'], handler: handleOnlineStatus, cooldown: 3 },
  { cmd: '/机组查询', aliases: ['/pilot', '/pilotquery'], handler: handlePilotQuery, cooldown: 2 },
  { cmd: '/管制查询', aliases: ['/controller', '/atc'], handler: handleControllerQuery, cooldown: 2 },
  { cmd: '/机场查询', aliases: ['/airport'], handler: handleAirport, cooldown: 2 },
  { cmd: '/呼叫管制', aliases: ['/call', '/callcontroller'], handler: handleCallController, cooldown: 3 },
  { cmd: '/呼叫2325', aliases: ['/call2325'], handler: handleCall2325, cooldown: 3 },
  { cmd: '/metar', aliases: ['/气象', '/气象报文'], handler: handleMetar, cooldown: 2 },
  { cmd: '/taf', aliases: ['/预报'], handler: handleTaf, cooldown: 2 },
  { cmd: '/航路', aliases: ['/route'], handler: handleRoute, cooldown: 3 },
  { cmd: '/event', aliases: ['/活动'], handler: handleEvent, cooldown: 3 },
  { cmd: '/chat', aliases: ['/聊天'], handler: handleNormalAi, cooldown: 5 },
  { cmd: '/帮助', aliases: ['/help'], handler: handleHelp, cooldown: 1 },
]

/**
 * 分发消息事件到命令处理函数
 * @param {import('ws').WebSocket} ws
 * @param {object} event - OneBot 事件对象
 */
export async function dispatch(ws, event) {
  // 处理请求事件（群入群申请自动审核）
  if (event.post_type === 'request') {
    if (event.request_type === 'group') {
      try {
        await handleGroupRequest(ws, event)
      } catch (error) {
        console.error('[GroupRequest] error:', error.message)
      }
    }
    return
  }

  // 处理通知事件（入群欢迎等）
  if (event.post_type === 'notice') {
    if (event.notice_type === 'group_increase') {
      try {
        handleGroupIncrease(ws, event)
      } catch (error) {
        console.error('[Welcome] error:', error.message)
      }
    }
    return
  }

  // 仅处理消息事件
  if (event.post_type !== 'message') return

  // 群消息检查白名单
  if (event.message_type === 'group' && !isAllowedGroup(event.group_id)) return

  const userId = String(event.user_id)

  // --- @机器人 检测 ---
  if (Array.isArray(event.message)) {
    const atIndex = event.message.findIndex(
      seg => seg.type === 'at' && seg.data?.qq === process.env.BOT_SELF_ID
    )
    if (atIndex !== -1) {
      // 提取 @ 之后的所有文本
      const afterAt = event.message.slice(atIndex + 1)
        .filter(seg => seg.type === 'text')
        .map(seg => seg.data?.text || '')
        .join('')
        .trim()

      if (afterAt) {
        const wait = checkUserCooldown(`cmd:@bot:${userId}`, 5)
        if (!wait) {
          try {
            await handleNormalAi(ws, event, [afterAt])
          } catch (err) {
            console.error('[Command] @bot error:', err.message)
            const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
            const send = event.message_type === 'group'
              ? (msg) => sendGroupMessage(ws, event.group_id, msg)
              : (msg) => sendPrivateMessage(ws, event.user_id, msg)
            send('执行出错，请稍后重试。')
          }
        }
        return
      }
    }
  }

  // 提取纯文本
  const text = extractPlainText(event)
  if (!text) return

  // 严格以空白拆分，第一个字段作为命令
  const parts = text.trim().split(/\s+/)
  const command = parts[0]
  const args = parts.slice(1)

  // 匹配命令（主命令或中英文别名）
  for (const route of routes) {
    if (command === route.cmd || (route.aliases && route.aliases.includes(command))) {
      // 检查冷却
      const wait = checkUserCooldown(`cmd:${route.cmd}:${userId}`, route.cooldown)
      if (wait) return  // 冷却中，静默忽略

      try {
        await route.handler(ws, event, args)
      } catch (err) {
        console.error(`[Command] ${route.cmd} error:`, err.message)
        const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
        const send = event.message_type === 'group'
          ? (msg) => sendGroupMessage(ws, event.group_id, msg)
          : (msg) => sendPrivateMessage(ws, event.user_id, msg)
        send('命令执行出错，请稍后重试。')
      }
      return
    }
  }
}

/**
 * 从 OneBot 事件中提取纯文本内容
 * @param {object} event
 * @returns {string|null}
 */
function extractPlainText(event) {
  const msg = event.message
  if (typeof msg === 'string') return msg

  if (Array.isArray(msg)) {
    return msg
      .filter(seg => seg.type === 'text')
      .map(seg => seg.data?.text || '')
      .join('')
      .trim() || null
  }

  return null
}
