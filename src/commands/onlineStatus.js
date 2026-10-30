import { formatOnlineStatus } from '../services/fsd.js'

/**
 * /在线状态 - 显示 FSD 在线概览
 */
export async function handleOnlineStatus(ws, event) {
  const text = await formatOnlineStatus()
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')

  if (event.message_type === 'group') {
    sendGroupMessage(ws, event.group_id, text)
  } else {
    sendPrivateMessage(ws, event.user_id, text)
  }
}
