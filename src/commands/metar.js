import { formatMetar, formatTaf } from '../services/weather.js'
import { normalizeIcao } from '../utils/validator.js'

/**
 * /metar <ICAO> - 查询 METAR 报
 */
export async function handleMetar(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    send('使用方法：/metar ZSPD')
    return
  }

  const icao = normalizeIcao(args[0])
  if (!icao) {
    send('无效的 ICAO 代码：「' + args[0] + '」应为 4 位字母（如 ZSPD）。')
    return
  }

  const text = await formatMetar(icao)
  send(text)
}

/**
 * /taf <ICAO1,ICAO2,...> - 查询 TAF 报（最多 5 个）
 */
export async function handleTaf(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  if (!args || args.length === 0) {
    send('使用方法：/taf ZBAA,ZSPD')
    return
  }

  // 逐个校验，非法输入明确提示（如 2 位国家码 AD、含数字的代码）
  const rawItems = args.join(',').split(/[,，\s]+/).filter(Boolean)
  if (rawItems.length === 0) {
    send('使用方法：/taf ZBAA,ZSPD')
    return
  }
  const invalid = rawItems.filter(i => !normalizeIcao(i))
  if (invalid.length > 0) {
    send(`无效的 ICAO 代码：${invalid.join('、')}（应为 4 位字母，如 ZSPD）`)
    return
  }

  const text = await formatTaf(rawItems.slice(0, 5).join(','))
  send(text)
}
