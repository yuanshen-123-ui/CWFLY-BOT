// 免播报名单：名单内的管制员上线/下线时，机器人不推送群通知
// 配置方式（bot/.env）：
//   NOTIFY_SKIP_CIDS=5966,1234        # 按 CID
//   NOTIFY_SKIP_CALLSIGNS=ZBAA_APP    # 按呼号（不区分大小写）
const skipCids = new Set(
  String(process.env.NOTIFY_SKIP_CIDS || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
)

const skipCallsigns = new Set(
  String(process.env.NOTIFY_SKIP_CALLSIGNS || '')
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
)

/** 该管制员是否在免播报名单内 */
export function isNotifySkipped(controller) {
  if (!controller) return false
  const cid = String(controller.cid ?? '').trim()
  const callsign = String(controller.callsign ?? '').trim().toUpperCase()
  if (cid && skipCids.has(cid)) return true
  if (callsign && skipCallsigns.has(callsign)) return true
  return false
}

export default { isNotifySkipped }
