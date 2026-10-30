/**
 * 输入校验工具
 */

/**
 * 标准化 ICAO 机场代码（4 位纯字母，不允许数字/符号）
 * @param {string} value
 * @returns {string|null}
 */
export function normalizeIcao(value) {
  if (!value || typeof value !== 'string') return null
  const code = value.trim().toUpperCase()
  return /^[A-Z]{4}$/.test(code) ? code : null
}

/**
 * 校验呼号（大小写不敏感字母数字，最长 12 字符）
 * @param {string} value
 * @returns {boolean}
 */
export function isValidCallsign(value) {
  if (!value || typeof value !== 'string') return false
  return /^[a-zA-Z0-9]{2,12}$/.test(value.trim())
}

/**
 * 截断字符串并添加省略号
 * @param {string} str
 * @param {number} maxLen
 * @returns {string}
 */
export function truncate(str, maxLen = 1000) {
  if (!str) return ''
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str
}

/**
 * 安全拆分逗号分隔的 ICAO 列表
 * @param {string} input
 * @param {number} maxItems
 * @returns {string[]}
 */
export function splitIcaoList(input, maxItems = 5) {
  if (!input) return []
  const items = input.split(/[,，\s]+/).filter(Boolean).slice(0, maxItems)
  return items.map(normalizeIcao).filter(Boolean)
}

/**
 * 是否为允许的群
 * @param {string|number} groupId
 * @returns {boolean}
 */
export function isAllowedGroup(groupId) {
  const allowed = process.env.ALLOWED_GROUP_IDS
  if (!allowed) return false
  return allowed.split(',').map(s => s.trim()).includes(String(groupId))
}
