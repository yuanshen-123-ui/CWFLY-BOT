/**
 * 简单的内存限流器
 * 支持用户级和全局级冷却
 */

const userBuckets = new Map()
const globalBuckets = new Map()

/**
 * 检查用户是否超过冷却时间
 * @param {string} key - 唯一键（如 "cmd:userId"）
 * @param {number} cooldown - 冷却秒数
 * @returns {number|null} 剩余秒数，null 表示允许
 */
export function checkUserCooldown(key, cooldown) {
  const now = Date.now()
  const entry = userBuckets.get(key)
  if (entry && now - entry < cooldown * 1000) {
    return Math.ceil(cooldown - (now - entry) / 1000)
  }
  userBuckets.set(key, now)
  return null
}

/**
 * 检查全局冷却
 * @param {string} key - 全局键
 * @param {number} cooldown - 冷却秒数
 * @returns {number|null} 剩余秒数
 */
export function checkGlobalCooldown(key, cooldown) {
  const now = Date.now()
  const entry = globalBuckets.get(key)
  if (entry && now - entry < cooldown * 1000) {
    return Math.ceil(cooldown - (now - entry) / 1000)
  }
  globalBuckets.set(key, now)
  return null
}

/**
 * 清理过期的冷却记录（每 5 分钟调用一次）
 */
export function cleanCooldowns() {
  const now = Date.now()
  for (const [key, time] of userBuckets) {
    if (now - time > 300_000) userBuckets.delete(key)
  }
  for (const [key, time] of globalBuckets) {
    if (now - time > 300_000) globalBuckets.delete(key)
  }
}

// 每 5 分钟自动清理
setInterval(cleanCooldowns, 300_000)
