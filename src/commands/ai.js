import { normalAi } from '../services/ai.js'
import { formatOnlineStatus } from '../services/fsd.js'

/**
 * /chat <内容> - 专业飞行助手 AI
 * 在线人数类问题 → 直接返回 FSD 真实在线状态；其余走 AI
 */
export async function handleNormalAi(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    send('使用方法：/chat 什么是 PBN？')
    return
  }

  const message = args.join(' ').slice(0, 1000)

  // 在线人数类问题：直接返回真实 FSD 在线状态
  const onlinePatterns = [
    /(在线|线上).*(人数|多少|几个|几个|几人|机组|管制|飞行员|状态)/,
    /(人数|多少|几个).*(在线|线上)/,
    /谁在(线|飞)|有哪些(人|机组|管制).*(在|飞)/,
    /现在.*(有人|几个人|多少人).*(在飞|在线)/,
    /(在线|线上).*(情况|状态)/,
    /(机组|管制).*(几个|多少)/
  ]
  if (onlinePatterns.some(p => p.test(message))) {
    send(await formatOnlineStatus())
    return
  }

  const reply = await normalAi(message)
  send(reply)
}
