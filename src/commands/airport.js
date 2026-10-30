import { queryAirport } from '../services/airport.js'
import { normalizeIcao } from '../utils/validator.js'

/**
 * /机场查询 <ICAO> - 查询机场信息
 */
export async function handleAirport(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    send('使用方法：/机场查询 ZSPD')
    return
  }

  const icao = normalizeIcao(args[0])
  if (!icao) {
    send('ICAO 代码必须为 4 位字母数字。')
    return
  }

  const text = await queryAirport(icao)
  send(text)
}
