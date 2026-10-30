import { queryRoute } from '../services/route.js'
import { normalizeIcao } from '../utils/validator.js'

/**
 * /航路 <DEP> <ARR> - 查询航路
 */
export async function handleRoute(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length < 2) {
    send('使用方法：/航路 ZSPD ZBAA')
    return
  }

  const dep = normalizeIcao(args[0])
  const arr = normalizeIcao(args[1])

  if (!dep || !arr) {
    send('ICAO 代码必须为 4 位字母数字。')
    return
  }

  const text = await queryRoute(dep, arr)
  send(text)
}
