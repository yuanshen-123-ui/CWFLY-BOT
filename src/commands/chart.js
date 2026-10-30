/**
 * /chart <ICAO> — 查询机场航图
 */

const API_BASE = process.env.API_BASE || 'http://localhost:3000/api'

export async function handleChart(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = event.message_type === 'group'
    ? (msg) => sendGroupMessage(ws, event.group_id, msg)
    : (msg) => sendPrivateMessage(ws, event.user_id, msg)

  const icao = (args[0] || '').toUpperCase()
  if (!icao) return send('用法：/chart <ICAO>\n例如：/chart ZBAA')

  try {
    const res = await fetch(`${API_BASE}/charts?icao=${icao}&provider=jeppesen`, { signal: AbortSignal.timeout(12000) })
    if (!res.ok) return send('航图查询失败')

    const data = await res.json()
    const charts = data?.data?.charts || data?.data?.data || (Array.isArray(data?.data) ? data.data : [])

    if (!charts.length) return send(`未找到 ${icao} 的航图`)

    // 按类型分组
    const groups = {}
    for (const c of charts) {
      const name = (c.name || c.id || '').toLowerCase()
      let type = '其他'
      if (name.includes('sid') || name.includes('离场')) type = '离场 SID'
      else if (name.includes('star') || name.includes('进场')) type = '进场 STAR'
      else if (name.includes('iap') || name.includes('进近') || name.includes('ils') || name.includes('vor')) type = '进近 IAP'
      else if (name.includes('taxi') || name.includes('停机') || name.includes('park')) type = '停机位'
      else if (name.includes('机场') || name.includes('general') || name.includes('ref')) type = '参考'
      if (!groups[type]) groups[type] = []
      groups[type].push(c.name || c.id || '')
    }

    const lines = [`${icao} 航图（共${charts.length}张）：`]
    for (const [type, items] of Object.entries(groups)) {
      lines.push(`\n【${type}】${items.length}张`)
      items.slice(0, 3).forEach(n => lines.push(`  · ${n}`))
      if (items.length > 3) lines.push(`  ...还有${items.length - 3}张`)
    }
    lines.push('\n请在 CWFLY 平台查看完整航图')

    send(lines.join('\n'))
  } catch (e) {
    send('查询失败：' + (e.message || '网络错误'))
  }
}
