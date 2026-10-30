import { formatControllerQuery, formatControllerList } from '../services/fsd.js'
import { isValidCallsign } from '../utils/validator.js'

/**
 * /管制查询 [呼号]
 */
export async function handleControllerQuery(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    const text = await formatControllerList()
    send(text)
    return
  }

  const callsign = args[0].trim().toUpperCase()
  if (!isValidCallsign(callsign)) {
    send('呼号格式无效。')
    return
  }

  const text = await formatControllerQuery(callsign)
  send(text)
}
