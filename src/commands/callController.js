import { getFsdStatus } from '../services/fsd.js'
import { checkUserCooldown, checkGlobalCooldown } from '../utils/rateLimit.js'

/**
 * /呼叫管制 - 发送管制呼叫到管制群
 * 限制：同一 QQ 5 分钟冷却，全群 1 分钟冷却
 */
export async function handleCallController(ws, event, args) {
  const { sendGroupMessage } = await import('../utils/onebot.js')

  // 仅群聊可用
  if (event.message_type !== 'group') {
    sendGroupMessage?.(ws, event.user_id, '/呼叫管制 仅支持群聊。')
    return
  }

  const userId = String(event.user_id)
  const groupId = String(event.group_id)
  const controlGroupId = process.env.CONTROL_GROUP_ID

  if (!controlGroupId) {
    sendGroupMessage(ws, groupId, '管制群未配置（CONTROL_GROUP_ID）。')
    return
  }

  // 用户冷却 5 分钟
  const userWait = checkUserCooldown(`call:${userId}`, 300)
  if (userWait) {
    sendGroupMessage(ws, groupId, `您 ${userWait} 秒后才能再次呼叫管制。`)
    return
  }

  // 全群冷却 1 分钟
  const globalWait = checkGlobalCooldown(`call:group:${groupId}`, 60)
  if (globalWait) {
    sendGroupMessage(ws, groupId, `本群 ${globalWait} 秒前刚呼叫过管制。`)
    return
  }

  // 获取当前 FSD 在线状态
  let onlineInfo = ''
  try {
    const data = await getFsdStatus()
    const controllers = data.controllers || []
    if (controllers.length > 0) {
      const ctrlList = controllers.map(c => c.callsign).join('、')
      onlineInfo = `\n当前在线管制：${ctrlList}\n（已在 FSD 在线，无需呼叫）`
    }
  } catch {
    onlineInfo = '\nFSD 状态服务暂时不可用。'
  }

  const nickname = event.sender?.nickname || event.sender?.card || `用户${userId}`
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const message = [
    '管制呼叫',
    `请求人：${nickname}（${userId}）`,
    `来源群：${event.group_id}`,
    `时间：${time}`,
    '请在线管制员查看 FSD 状态并响应。',
    onlineInfo
  ].join('\n')

  // 发送到管制群
  sendGroupMessage(ws, controlGroupId, message)

  // 回复请求群
  sendGroupMessage(ws, groupId, '呼叫已发送到管制群，请等待管制员响应。')
}

/**
 * /呼叫2325 - 呼叫指定管制员 2325（私聊到其 QQ 3284715587）
 * 限制：同一 QQ 5 分钟冷却，全群 1 分钟冷却
 */
export async function handleCall2325(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')

  // 仅群聊可用
  if (event.message_type !== 'group') {
    sendPrivateMessage?.(ws, event.user_id, '/呼叫2325 仅支持群聊。')
    return
  }

  const userId = String(event.user_id)
  const groupId = String(event.group_id)
  const targetQq = process.env.CALL_2325_QQ || '3284715587'

  // 用户冷却 5 分钟
  const userWait = checkUserCooldown(`call2325:${userId}`, 300)
  if (userWait) {
    sendGroupMessage(ws, groupId, `您 ${userWait} 秒后才能再次呼叫管制员 2325。`)
    return
  }

  // 全群冷却 1 分钟
  const globalWait = checkGlobalCooldown(`call2325:group:${groupId}`, 60)
  if (globalWait) {
    sendGroupMessage(ws, groupId, `本群 ${globalWait} 秒前刚呼叫过管制员 2325。`)
    return
  }

  const nickname = event.sender?.nickname || event.sender?.card || `用户${userId}`
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const extra = args && args.length ? `\n请求内容：${args.join(' ')}` : ''
  const message = [
    '管制呼叫（2325）',
    `请求人：${nickname}（${userId}）`,
    `来源群：${event.group_id}`,
    `时间：${time}`,
    `请管制员 2325 响应。${extra}`
  ].join('\n')

  // 私聊发送给 2325
  sendPrivateMessage(ws, targetQq, message)

  // 回复请求群
  sendGroupMessage(ws, groupId, '呼叫已发送给管制员 2325，请等待响应。')
}
