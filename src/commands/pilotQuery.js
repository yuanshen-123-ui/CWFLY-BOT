import { formatPilotQuery, formatPilotList } from '../services/fsd.js'
import { isValidCallsign } from '../utils/validator.js'

/**
 * /机组查询 [呼号]
 * 有呼号时精确查询，无呼号时返回列表
 */
export async function handlePilotQuery(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const target = event.message_type === 'group' ? event.group_id : event.user_id
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    const text = await formatPilotList()
    send(text)
    return
  }

  const callsign = args[0].trim().toUpperCase()
  if (!isValidCallsign(callsign)) {
    send('呼号格式无效（2-12 位字母数字）。')
    return
  }

  const text = await formatPilotQuery(callsign)
  send(text)
}
