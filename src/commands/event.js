/**
 * /event — 查询近期连飞活动
 */

const API_BASE = process.env.API_BASE || 'http://localhost:3000/api'

export async function handleEvent(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = event.message_type === 'group'
    ? (msg) => sendGroupMessage(ws, event.group_id, msg)
    : (msg) => sendPrivateMessage(ws, event.user_id, msg)

  try {
    const res = await fetch(`${API_BASE}/events`, { signal: AbortSignal.timeout(8000) })
    if (!res.ok) return send('查询失败，服务器异常')

    const data = await res.json()
    const events = Array.isArray(data?.data) ? data.data : []

    if (!events.length) return send('暂无近期活动')

    // 最多显示5个
    const list = events.slice(0, 5).map((e, i) => {
      const dep = e.dep || e.depIcao || '??'
      const arr = e.arr || e.arrIcao || '??'
      return `${i + 1}. ${e.title || '未命名活动'}\n   日期：${e.date || '-'}  ${dep} → ${arr}\n   状态：${e.status || '-'}`
    })

    send(`近期活动（共${events.length}个）：\n\n${list.join('\n\n')}`)
  } catch (e) {
    send('查询失败：' + (e.message || '网络错误'))
  }
}
